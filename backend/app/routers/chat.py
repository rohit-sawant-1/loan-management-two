"""
The one chat address for the whole assistant.

**This endpoint is deliberately the only chat door in the product, and it does
not change as the phases are added.** The mentor's instruction was one chat box
rather than three — a policy question, a data question and an instruction should
all go to the same place, and the assistant should work out for itself what kind
of question it just received.

So the front-end talks to `POST /api/v1/chat` and always will. What sits behind
it grows:

    Phase 2        the RAG chain, answering policy questions from the manual
    Phase 3 (now)  a tool-using agent that can also read live application data
    Phase 4        the same agent, with its tools served over MCP
    Phase 5        the multi-agent reviewer for "assess application 7"

Each phase replaces the brain behind this door. No screen has to be rewritten,
and the demo shows one assistant getting steadily more capable instead of three
disconnected chatbots.

The `mode` field in the reply says which brain answered. It is what lets the
screen show "answered from the user manual" versus "read from live data", and
it is genuinely useful in a demo: it makes the routing visible instead of
magic.
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

import llm_provider
from app.database import get_db
from app.domain import rules
from app.utils.finance import format_rupees
from app.utils.text import readable_list
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource, ChatToolCall
from app.services import activity_service, pending_actions, review_request
from app.services.loan_api_client import acting_as

logger = structlog.get_logger()

router = APIRouter()

# The tool that reads the user manual. When the agent used it, the answer is
# grounded in the manual, so the screen can still show the extracts underneath.
POLICY_TOOL = "search_loan_policy"

# LangChain records a step called `_Exception` whenever the model wrote a
# malformed step and had to be asked to correct itself. That is real and worth
# logging, but it is not something the agent *did* — showing "_Exception" in a
# customer's list of how their answer was worked out looks like a crash. It is
# dropped from what the screen sees.
INTERNAL_STEPS = {"_Exception"}

# One agent per role, built on first use and reused. Building one sets up the
# model, the tools and the ReAct prompt — cheap, but not free, and it would
# otherwise happen on every single message.
#
# Keyed by role rather than shared, because staff and customers genuinely get
# different tools now: a customer's agent must not even have a way to propose
# changing a record. One agent for everyone would mean either handing customers
# the write tools or denying them to staff.
_agents: dict[str | None, object] = {}


def get_agent(role: str | None = None):
    """The shared agent executor for this role, built on first use."""
    if role not in _agents:
        from agent.agent import build_agent

        _agents[role] = build_agent(role)
    return _agents[role]


# What the screen calls a Phase 5 answer. The mode tells it which brain
# answered, and `Assistant.jsx` already has a slot for this one.
REVIEW_MODE = "review"


def _review_answer(state: dict) -> str:
    """
    The chat bubble for a finished review: the verdict, the figures it rests on,
    then the paragraph the decision maker wrote.

    The verdict and every number here were computed in plain Python from
    `app/domain/rules.py` (D-19). The AI wrote only the closing paragraph, so a
    dead quota changes the wording of this answer and never the decision in it.

    Only called when the review actually ran. On a data-collection failure the
    risk and compliance dicts are still empty, and the caller returns before
    reaching here — which is why this reads them directly rather than guarding
    every lookup.
    """
    risk = state["risk_assessment"]
    compliance = state["compliance_check"]

    lines = [
        f"Application {state['application_id']} — {state['final_decision']}",
        "",
        # The score is a float, but "90/100" reads better than "90.0/100" and
        # the decimal carries no meaning anyone acts on.
        f"Risk score {risk['overall_risk_score']:.0f}/100 "
        f"(credit risk: {risk['credit_risk_level']}, "
        f"employment risk: {risk['employment_risk']})",
        f"Estimated EMI {format_rupees(risk['emi_amount'])} a month · "
        f"debt-to-income ratio {risk['debt_to_income_ratio']:.0%}",
        f"Compliance: {'passed' if compliance['compliance_passed'] else 'not passed'}",
    ]

    missing = compliance.get("missing_documents") or []
    if missing:
        lines.append(f"Still missing: {readable_list(missing)}")

    if state["reasoning"]:
        lines.extend(["", state["reasoning"]])

    return "\n".join(lines)


def _review_steps(state: dict) -> list[ChatToolCall]:
    """
    The four agents' own messages, shaped as the same `tools_used` list the
    screen already knows how to draw.

    This is the reason no new response field was needed: "how this was worked
    out" is already a numbered list of steps on that screen, and a four-agent
    pipeline is exactly that — data collected, risk assessed, compliance
    checked, decision made, in the order they ran.
    """
    return [
        ChatToolCall(tool=message.get("agent", "agent"),
                     tool_input=str(message.get("message", ""))[:200])
        for message in state.get("messages", [])
    ]


def _tool_calls(intermediate_steps) -> list[ChatToolCall]:
    """
    Turn the agent's own record of what it did into something the screen can
    show. Each step is a pair: the action it took, and what came back. We only
    want the action's name and input — the observation can be long, and it is
    already folded into the answer.
    """
    calls = []
    for step in intermediate_steps:
        action = step[0]
        name = getattr(action, "tool", "unknown")
        if name in INTERNAL_STEPS:
            continue
        calls.append(ChatToolCall(
            tool=name,
            tool_input=str(getattr(action, "tool_input", ""))[:200],
        ))
    return calls


def _policy_sources(calls: list[ChatToolCall]) -> list[ChatSource]:
    """
    The manual extracts behind an agent answer.

    The agent's policy tool returns only a sentence, not the extracts it came
    from, so we ask the retriever again for the same query the agent used. That
    is one extra vector-store lookup and no extra AI call, and it keeps the
    "check the AI" panel working now that the agent answers policy questions
    rather than the chain answering them directly.
    """
    queries = [c.tool_input for c in calls if c.tool == POLICY_TOOL and c.tool_input]
    if not queries:
        return []

    try:
        from rag.rag_chain import get_chain

        _chain, retriever = get_chain()
        documents = retriever.invoke(queries[0])
    except Exception:                                          # noqa: BLE001
        # Sources are a nice-to-have. Never fail an answered question over them.
        logger.warning("chat_sources_unavailable", operation="chat_sources")
        return []

    return [
        ChatSource(
            chunk_id=d.metadata.get("chunk_id"),
            source=d.metadata.get("source"),
            excerpt=d.page_content.strip()[:600],
        )
        for d in documents
    ]


def _answer_with_rag(question: str) -> tuple[str, list[ChatSource]]:
    """
    Phase 2's brain, kept as the fallback.

    If the agent cannot run at all — the model is rate-limited, the ReAct loop
    gives up — the person still gets a real answer from the manual rather than
    an error. The reply says `mode="rag"` when this happens, so the screen tells
    the truth about which brain answered.
    """
    from rag.rag_chain import answer_question, get_chain

    chain, retriever = get_chain()
    result = answer_question(question, chain, retriever)
    return result["answer"], [
        ChatSource(chunk_id=s["chunk_id"], source=s["source"], excerpt=s["excerpt"][:600])
        for s in result["sources"]
    ]


@router.post("", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Ask the assistant something.

    Anyone signed in may ask. What comes back is limited by who is asking: the
    agent's tools call the Phase 1 API inside `acting_as()`, so they run as the
    person who typed the question. A customer asking "show me application 5"
    gets a 403 from the API itself unless it is their own — the same rule the
    browser already obeys, not a second one written for the AI (T-75).
    """
    started = time.perf_counter()
    question = body.message.strip()

    if not question:
        return ChatResponse(
            answer="Ask me something about loans, and I will answer from the bank's manual.",
            mode="empty",
            sources=[],
            duration_ms=0.0,
        )

    # Is this person answering a "reply YES to go ahead"? Checked before the
    # agent is involved at all, and deliberately so: the confirmed change runs
    # from the arguments recorded when it was proposed, so the model never gets
    # a second chance to decide which application it meant.
    waiting = pending_actions.peek(user.email)
    if waiting is not None:
        if pending_actions.looks_like_yes(question):
            pending_actions.clear(user.email)
            with acting_as(user.email, user.role.value):
                worked, sentence = pending_actions.run(waiting)

            # Point the row at the record that was actually changed, not at
            # "chat". Someone auditing application 3 wants this row to show up
            # against application 3 — filing it under a conversation with no
            # number is both useless to them and what produced "Chat #null" on
            # the activity page.
            touched = waiting["arguments"].get("application_id")

            activity_service.record(
                db, action="chat_action_confirmed",
                actor_id=user.email, actor_role=user.role.value,
                entity_type="application" if touched else "chat",
                entity_id=touched,
                # `outcome` carries the reason a refusal happened, not just
                # that one did. "Blocked by a permission rule" and "the API was
                # unreachable" are the same `worked: false` otherwise, and an
                # auditor asking why the AI tried to disburse a loan deserves
                # the actual answer.
                details={"tool": waiting["tool"], "arguments": waiting["arguments"],
                         "worked": worked,
                         "outcome": sentence[:200]},
                **activity_service.request_meta(request),
            )
            db.commit()

            return ChatResponse(
                answer=sentence,
                mode="action",
                sources=[],
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                tools_used=[ChatToolCall(tool=waiting["tool"],
                                         tool_input=str(waiting["arguments"])[:200])],
            )

        if pending_actions.looks_like_no(question):
            pending_actions.clear(user.email)
            return ChatResponse(
                answer="Cancelled — nothing was changed.",
                mode="action",
                sources=[],
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

        # Anything else is a new instruction, not an answer. The old proposal is
        # dropped rather than left waiting, so a later stray "yes" cannot land
        # on something they have already moved on from.
        pending_actions.clear(user.email)

    # A full four-agent underwriting review, asked for by name.
    #
    # Deliberately a phrase rather than a tool the model may pick. A review is
    # two AI calls and about ten seconds; letting a model decide when to spend
    # that would mean "what happened to application 7" runs one some days and
    # not others. See `app/services/review_request.py` for the whole argument.
    #
    # Placed after the pending-action block on purpose. A review typed while a
    # change is awaiting confirmation should drop that change first, and the
    # block above already does exactly that for every other new instruction —
    # so this branch inherits that behaviour instead of restating it.
    review_id = review_request.review_target(question)
    if review_id is not None:
        if user.role.value not in rules.STAFF_ROLES:
            # Refused before the graph runs, so it costs no AI call. The review
            # prints the literal word REJECT, and showing that to a customer for
            # an application no human has rejected would be a commitment the
            # bank has not made.
            return ChatResponse(
                answer="A full underwriting review is a tool for bank staff. I can "
                       "tell you the status of your own application and what it "
                       "still needs — just ask.",
                mode=REVIEW_MODE,
                sources=[],
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

        # Imported here rather than at the top of the file: this pulls in
        # LangGraph and all four agents, and every other route would pay that
        # import cost for a feature it never touches.
        from multi_agent.graph import evaluate_loan_application

        # Runs as the person asking, so the review reads exactly the data they
        # are allowed to read (T-75). Blocks for five to fifteen seconds, which
        # is fine: this handler is `def`, not `async def`, so FastAPI runs it in
        # a worker thread and the server keeps answering everything else.
        with acting_as(user.email, user.role.value):
            state = evaluate_loan_application(review_id)

        if state.get("errors"):
            # Not an AI failure, so `ai_status` stays `ai_ok` and the amber
            # notice stays quiet. A missing application or a refused permission
            # has nothing to do with the model, and saying "the AI has reached
            # today's limit" about a typo'd number would be a lie. The API
            # client already writes these sentences for people to read.
            answer = "I could not run the review. " + state["errors"][0]
            steps: list[ChatToolCall] = []
        else:
            answer = _review_answer(state)
            steps = _review_steps(state)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)

        activity_service.record(
            db, action="chat_review",
            actor_id=user.email, actor_role=user.role.value,
            # Filed against the application itself, not against "chat", so the
            # review shows up on that application's own timeline (T-91).
            entity_type="application", entity_id=int(review_id),
            details={
                "decision": state.get("final_decision") or "not reached",
                "risk_score": (state.get("risk_assessment") or {}).get("overall_risk_score"),
                "compliance_passed": (state.get("compliance_check") or {}).get("compliance_passed"),
                "agents_run": [m.get("agent") for m in state.get("messages", [])],
                "errors": state.get("errors", [])[:2],
            },
            **activity_service.request_meta(request),
        )
        db.commit()

        logger.info("chat_review_answered", operation="chat_answered",
                    application_id=review_id, mode=REVIEW_MODE,
                    decision=state.get("final_decision"),
                    errors=state.get("errors", []),
                    duration_ms=duration_ms)

        return ChatResponse(
            answer=answer,
            mode=REVIEW_MODE,
            sources=[],
            duration_ms=duration_ms,
            tools_used=steps,
        )

    mode = "agent"
    tools_used: list[ChatToolCall] = []
    ai_status = llm_provider.AI_OK

    try:
        from agent.agent import run_agent

        # Everything inside this block calls the loan API as the person asking,
        # and any change the agent proposes is recorded against them.
        with acting_as(user.email, user.role.value), pending_actions.owned_by(user.email):
            result = run_agent(question, get_agent(user.role.value))

        answer = result.get("output") or ""
        tools_used = _tool_calls(result.get("intermediate_steps", []))
        sources = _policy_sources(tools_used)

        if not answer.strip():
            # The agent ran but produced nothing useful. Fall back rather than
            # showing a blank bubble.
            raise ValueError("agent returned an empty answer")

    except Exception as exc:                                   # noqa: BLE001
        # Which kind of failure this was, so the person is told something
        # specific rather than "the AI failed" (D-20). Note we classify the
        # agent's error even though the RAG fallback below may well succeed:
        # if a spent quota pushed us down to the local model, that is worth
        # saying, because the answer really will be shorter and plainer.
        ai_status = llm_provider.classify_failure(exc)
        logger.warning("chat_agent_failed", operation="chat_agent_failed",
                       question=question[:200], error=str(exc)[:300],
                       ai_status=ai_status)
        mode = "rag"
        tools_used = []

        # The agent may have proposed a change before it fell over. The person
        # is about to get a manual answer that says nothing about it, so a
        # "yes" later would confirm something they were never actually shown.
        pending_actions.clear(user.email)

        try:
            answer, sources = _answer_with_rag(question)
        except Exception as rag_exc:                           # noqa: BLE001
            # Both brains are down. Before this, that raised and the person got
            # a 500 with no explanation — the worst possible moment for the
            # product to look broken rather than degraded. Now the chat says
            # plainly that no AI is available and the rest of the app is fine.
            ai_status = llm_provider.classify_failure(rag_exc)
            logger.error("chat_all_brains_failed", operation="chat_agent_failed",
                         question=question[:200], error=str(rag_exc)[:300],
                         ai_status=ai_status)
            mode = "unavailable"
            sources = []
            answer = llm_provider.message_for(ai_status)

    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    activity_service.record(
        db, action="chat_message",
        actor_id=user.email, actor_role=user.role.value,
        # No entity_type on purpose. A question is not about one numbered
        # record — it may touch several or none — so the activity page shows a
        # dash, which is honest. Claiming a type with no number behind it is
        # what printed "Chat #null" (T-91).
        entity_type=None,
        details={"question": question[:200], "mode": mode,
                 "sources": len(sources),
                 "tools": [c.tool for c in tools_used],
                 "ai_status": ai_status},
        **activity_service.request_meta(request),
    )
    db.commit()

    logger.info("chat_answered", operation="chat_answered",
                question=question[:200], mode=mode,
                sources=len(sources),
                tools_used=[c.tool for c in tools_used],
                ai_status=ai_status,
                duration_ms=duration_ms)

    # The notice is quiet on a normal answer, and quiet again when the answer
    # *is* the notice — when every brain failed there is nothing else to say,
    # and showing the same sentence twice in a row looks like a glitch.
    notice = "" if ai_status == llm_provider.AI_OK else llm_provider.message_for(ai_status)
    if notice == answer:
        notice = ""

    return ChatResponse(
        answer=answer,
        mode=mode,
        sources=sources,
        duration_ms=duration_ms,
        tools_used=tools_used,
        ai_status=ai_status,
        ai_notice=notice,
    )
