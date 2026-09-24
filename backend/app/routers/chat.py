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
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import llm_provider
from app.database import get_db
from app.domain import rules
from app.utils.finance import format_rupees
from app.utils.text import readable_list
from app.dependencies import get_current_user, require_role
from app.models.document import Document
from app.models.user import User, UserRole
from app.schemas.chat import (
    ChatAttachRequest, ChatAttachResponse, ChatMessagesPage, ChatRequest, ChatResponse,
    ChatSessionOut, ChatSessionUpdate, ChatSource, ChatToolCall,
)
from app.services import (
    activity_service, chat_session_service, document_service, pending_actions, review_request,
)
from app.services.errors import Forbidden, NotFound
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

    Every lookup here is guarded, and that is a deliberate change from how this
    was first written. It used to read `state["risk_assessment"]` and its keys
    directly, on the argument that the caller returns early whenever data
    collection failed. That argument is true and it is not enough: it only
    covers the failures the graph *records*. An agent raising part-way through,
    or a state shape nobody predicted, would come through here as a `KeyError`
    and reach the customer as a 500 and a red banner across the chat.

    So a missing figure now costs us that one line of the answer rather than the
    whole answer. What this never does is invent one — an absent number is left
    out, never defaulted to zero, because a made-up figure in an underwriting
    review is far worse than a short one.
    """
    risk = state.get("risk_assessment") or {}
    compliance = state.get("compliance_check") or {}

    decision = state.get("final_decision") or "no decision reached"
    lines = [f"Application {state.get('application_id', '?')} — {decision}", ""]

    # The score is a float, but "90/100" reads better than "90.0/100" and the
    # decimal carries no meaning anyone acts on.
    score = risk.get("overall_risk_score")
    if score is not None:
        lines.append(
            f"Risk score {score:.0f}/100 "
            f"(credit risk: {risk.get('credit_risk_level', 'not assessed')}, "
            f"employment risk: {risk.get('employment_risk', 'not assessed')})"
        )

    emi, dti = risk.get("emi_amount"), risk.get("debt_to_income_ratio")
    if emi is not None and dti is not None:
        lines.append(f"Estimated EMI {format_rupees(emi)} a month · "
                     f"debt-to-income ratio {dti:.0%}")

    if "compliance_passed" in compliance:
        lines.append(f"Compliance: {'passed' if compliance['compliance_passed'] else 'not passed'}")

    missing = compliance.get("missing_documents") or []
    if missing:
        lines.append(f"Still missing: {readable_list(missing)}")

    if state.get("reasoning"):
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
    Ask the assistant something, inside a saved conversation (Piece 36).

    No `session_id` starts a new conversation; someone else's is refused as
    "not found". The answer itself is worked out exactly as before, by
    `_answer` below, and only then are the question and the answer saved.
    An empty message is answered but not saved: there's nothing to keep.
    """
    if not body.message.strip():
        return _answer(body, request, db, user)
    try:
        session = chat_session_service.open_or_start(db, user, body.session_id, body.message)
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)

    # A "reply YES to go ahead" belongs to the chat it was proposed in. Waiting
    # confirmations are kept per person, not per chat (pending_actions), so a
    # YES typed in any other chat, new or old, must not confirm it.
    waiting = pending_actions.peek(user.email)
    if waiting is not None and waiting.get("session_id") not in (None, session.id):
        pending_actions.clear(user.email)

    response = _answer(body, request, db, user)

    # If this answer just proposed a change, remember which chat it was in.
    waiting = pending_actions.peek(user.email)
    if waiting is not None and "session_id" not in waiting:
        waiting["session_id"] = session.id
    chat_session_service.save_turn(db, session, body.message.strip(), response)
    response.session_id = session.id
    return response


def _answer(body: ChatRequest, request: Request, db: Session, user: User) -> ChatResponse:
    """
    Ask the assistant something. (Before Piece 36 this was the route itself;
    it moved here unchanged, so every way of answering is saved in one place.)

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
            #
            # The administrator (Piece 27) is refused too, because a review
            # recommends a loan decision. It gets its own sentence, since "your
            # own application" means nothing to someone who has none.
            if user.role.value == rules.ADMIN_ROLE:
                answer = ("A full underwriting review is for loan officers and the "
                          "branch manager. As the administrator you can still ask "
                          "about any application's details and status.")
            else:
                answer = ("A full underwriting review is a tool for bank staff. I can "
                          "tell you the status of your own application and what it "
                          "still needs — just ask.")
            return ChatResponse(
                answer=answer,
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
        # Everything from here to the answer is wrapped, and this is the last
        # AI path in the product that was not. Phase 5's agents already fall
        # back to deterministic summaries and the briefing falls back to plain
        # figures; this branch could still raise a 500 straight through to a red
        # banner across the chat. On stage that is a refresh and a lost thread,
        # where a sentence saying the review could not be completed is simply
        # the product behaving honestly.
        #
        # Deliberately broad: the point is not to handle a specific failure, it
        # is that no failure at all gets out of here. Logged at exception level
        # so the stack trace is still ours to read afterwards.
        try:
            with acting_as(user.email, user.role.value):
                state = evaluate_loan_application(review_id)
        except Exception:                                       # noqa: BLE001
            logger.exception("chat_review_crashed", operation="chat_answered",
                             application_id=review_id, mode=REVIEW_MODE)
            state = {"application_id": review_id, "errors": [
                "Something went wrong while the review was running. "
                "The application itself is unchanged — nothing a review does "
                "alters a record."
            ]}

        if state.get("errors"):
            # Not an AI failure, so `ai_status` stays `ai_ok` and the amber
            # notice stays quiet. A missing application or a refused permission
            # has nothing to do with the model, and saying "the AI has reached
            # today's limit" about a typo'd number would be a lie. The API
            # client already writes these sentences for people to read.
            answer = "I could not run the review. " + state["errors"][0]
            steps: list[ChatToolCall] = []
        else:
            # Guarded separately from the run above on purpose. A review that
            # completed and then could not be *described* has still done its
            # work, and the numbers behind it are in the activity row written
            # a few lines below either way.
            try:
                answer = _review_answer(state)
                steps = _review_steps(state)
            except Exception:                                   # noqa: BLE001
                logger.exception("chat_review_unreadable", operation="chat_answered",
                                 application_id=review_id, mode=REVIEW_MODE)
                answer = (f"The review of application {review_id} ran, but I could not "
                          f"put the result into words. The verdict was "
                          f"{state.get('final_decision') or 'not recorded'}. "
                          f"Open the application to see the full assessment.")
                steps = []

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
                # The audit trail keeps a bounded excerpt of what the chat said,
                # not the conversation (Rohit, 2026-09-24). The full answer is
                # only in the person's own saved chat.
                "answer": answer[:500],
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
        # A complete audit trail of the chatbot (Rohit, 2026-09-24), kept as
        # bounded excerpts: the first 200 characters of the question and the
        # first 500 of the answer. The full conversation is only in the
        # person's own saved chat (Piece 36), which nobody else can open.
        details={"question": question[:200], "answer": answer[:500], "mode": mode,
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


# ---------------------------------------------------------------------------
# Piece 36: saved conversations. Each address only ever shows the caller's
# own chats; anyone else's is "not found", whoever is asking.
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return chat_session_service.list_sessions(db, user)


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagesPage)
def session_messages(
    session_id: int,
    limit: int = Query(30, ge=1, le=100),
    before_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        rows, has_more = chat_session_service.messages(db, session_id, user, limit, before_id)
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    return {"items": [chat_session_service.message_out(m) for m in rows], "has_more": has_more}


@router.patch("/sessions/{session_id}", response_model=ChatSessionOut)
def update_session(
    session_id: int,
    body: ChatSessionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Rename or archive one of your own chats."""
    try:
        return chat_session_service.update(db, session_id, user, body.title, body.archived)
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# ---------------------------------------------------------------------------
# Pieces 37 + 38: documents attached from the Assistant.
#
# The files themselves go up through the normal upload address, the same
# pipeline as the Documents card. This only records, in the customer's own
# chat, which of their documents they attached. No AI call is made, and no
# document's contents are read here, stored here, or sent anywhere.
# ---------------------------------------------------------------------------

@router.post("/attachments", response_model=ChatAttachResponse)
def attach_documents(
    body: ChatAttachRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.applicant)),
):
    """
    Customers only (staff and the admin attach from the application page).

    Retry-safe: the browser makes one `attach_key` per attachment event and
    sends the same key on every retry, so a retry after a lost answer gets the
    message that was already saved rather than a second one. Attaching the
    same documents again later is a new event with a new key.
    """
    existing = chat_session_service.find_attachment(db, body.attach_key)
    if existing is not None:
        if existing.session.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="That attachment key has already been used")
        return {"session_id": existing.session_id, "message": chat_session_service.message_out(existing)}

    # The document system's own ownership rule: 404 if the application
    # doesn't exist, 403 if it isn't the customer's.
    try:
        application = document_service._application_for(db, body.application_id, user)
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Forbidden as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)

    # Every document must be on that application and still current.
    documents = {d.id: d for d in db.query(Document).filter(Document.id.in_(body.document_ids))}
    for doc_id in body.document_ids:
        doc = documents.get(doc_id)
        if doc is None or doc.application_id != application.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"Document {doc_id} is not on application {application.id}")
        if doc.replaced_by_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"Document {doc_id} has been replaced by a newer copy")

    names = [documents[i].file_name for i in body.document_ids]
    count = len(names)
    content = (f"📎 Attached {count} document{'' if count == 1 else 's'} to application "
               f"{application.id}: {', '.join(names)}")

    try:
        session = chat_session_service.open_or_start(db, user, body.session_id, content)
    except NotFound as e:        # a foreign or unknown chat
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)

    message = chat_session_service.add_attachment(
        db, session, content, application.id, body.document_ids, body.attach_key,
    )
    # A chatbot interaction, so it's audited (Piece 36 model): which
    # application, which documents and their file names. Never contents.
    # Each upload already has its own `document_added` row.
    activity_service.record(
        db, action="chat_documents_attached",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="application", entity_id=application.id,
        details={"document_ids": body.document_ids, "file_names": names, "chat": session.id},
        **activity_service.request_meta(request),
    )
    try:
        db.commit()
    except IntegrityError:
        # Two retries of the same event arrived together: the other one won.
        db.rollback()
        existing = chat_session_service.find_attachment(db, body.attach_key)
        return {"session_id": existing.session_id, "message": chat_session_service.message_out(existing)}
    db.refresh(message)
    return {"session_id": session.id, "message": chat_session_service.message_out(message)}
