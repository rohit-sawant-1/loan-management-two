"""
Agent 4: turn the risk score and the compliance verdict into one of three
words a loan officer can act on.

The decision itself is deterministic, using the exact bands this project
already settled on before Phase 5 was built (D-10, in `domain/rules.py`):
approve only above 70, reject below 40, everything in between asks for more
information. A missing document is fixable — REQUEST_MORE_INFO — but an
amount over the limit or an ineligible age is not, so those go straight to
REJECT even if the risk score alone would not have failed. As with the risk
assessor, the LLM's job is the `reasoning` paragraph a human reads, explained
from a decision that was already made on fixed, auditable rules — not the
decision itself.
"""

import time

import structlog
from opentelemetry import trace

from app.domain import rules
from app.utils.finance import format_rupees
from llm_provider import get_llm
from multi_agent.llm_text import text_of
from multi_agent.state import LoanProcessingState

logger = structlog.get_logger()
tracer = trace.get_tracer("decision-maker")


def _decide(risk: dict, compliance: dict) -> str:
    score = risk.get("overall_risk_score", 0) or 0
    compliance_passed = compliance.get("compliance_passed", False)
    emi_ok = risk.get("emi_affordability") == "yes"

    if not compliance_passed:
        unfixable = (not compliance.get("amount_within_limit", True)
                     or not compliance.get("age_eligible", True))
        if unfixable or score < rules.RISK_REJECT_BELOW:
            return "REJECT"
        return "REQUEST_MORE_INFO"

    if score > rules.RISK_APPROVE_ABOVE and emi_ok:
        return "APPROVE"
    if score < rules.RISK_REJECT_BELOW:
        return "REJECT"
    return "REQUEST_MORE_INFO"


def _fallback_reasoning(decision: str, risk: dict, compliance: dict) -> str:
    return (f"Decision: {decision}. Overall risk score {_score(risk.get('overall_risk_score'))}/100 "
            f"(credit risk {risk.get('credit_risk_level', 'unknown')}, employment risk "
            f"{risk.get('employment_risk', 'unknown')}, EMI affordable: "
            f"{risk.get('emi_affordability', 'unknown')}). Compliance "
            f"{'passed' if compliance.get('compliance_passed') else 'did not pass'}: "
            f"{compliance.get('compliance_notes', 'no notes recorded')}.")


def _score(value) -> str:
    """A risk score without its decimal tail: 70.0 reads better as 70."""
    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return "unknown"


def _rupees_or_unknown(amount) -> str:
    """
    An amount in rupees for the prompt, or "unknown" if there is not one.

    Kept tolerant because this runs inside the reasoning path, which is not
    allowed to fail — a missing or malformed amount should cost us a vague
    sentence, never the decision itself.
    """
    if amount is None:
        return "unknown"
    try:
        return format_rupees(float(amount))
    except (TypeError, ValueError):
        return "unknown"


def _llm_reasoning(decision: str, risk: dict, compliance: dict, application: dict) -> str:
    """The paragraph a loan officer reads explaining a decision already made. Never raises."""
    try:
        llm = get_llm(temperature=0.1)
        prompt = (
            f"You are a senior loan underwriter at a bank. The decision has already been "
            f"made by the bank's fixed underwriting rules: {decision}. Write a short, "
            f"professional paragraph (3-5 sentences) explaining this decision to the "
            f"applicant's loan officer, referencing these specific figures — do not "
            f"contradict the decision or invent numbers not given here.\n\n"
            # The amount is formatted as rupees before the model sees it. Handed
            # the bare number 4000000.0 it wrote "$4,000,000.0" — dollars, on an
            # Indian loan, with a stray decimal. A model fills in a missing unit
            # with whatever is most common in its training data, so the unit has
            # to be in the prompt rather than assumed.
            f"Loan: {application.get('loan_type', 'unknown')} loan of "
            f"{_rupees_or_unknown(application.get('amount_requested'))} over "
            f"{application.get('tenure_months', 'unknown')} months.\n"
            # "higher is better" matters: without it a model can read 70/100 as
            # seventy percent risky and invert the whole meaning. The risk
            # assessor's prompt has always said so; this one did not.
            #
            # The score is printed without its decimal tail, and affordability
            # is translated out of the stored yes/no token into words, for the
            # same reason — the model repeats whatever shape it is given (T-96).
            f"Risk assessment: overall score "
            f"{_score(risk.get('overall_risk_score'))} out of 100, where higher is "
            f"better. Credit risk {risk.get('credit_risk_level', 'unknown')}, "
            f"employment risk {risk.get('employment_risk', 'unknown')} "
            f"(low risk is good). The monthly EMI is "
            f"{'affordable' if risk.get('emi_affordability') == 'yes' else 'not affordable'} "
            f"against their income.\n"
            f"Compliance: {'passed' if compliance.get('compliance_passed') else 'did not pass'} "
            f"— {compliance.get('compliance_notes', 'no notes')}.\n\n"
            f"If the decision is REQUEST_MORE_INFO or REJECT, say plainly what is missing or "
            f"wrong. If APPROVE, note any standard conditions.\n"
            f"This is an Indian bank. All amounts are in rupees — write them as "
            f"shown above and never convert them or use a dollar sign."
        )
        response = llm.invoke(prompt)
        text = text_of(response.content)
        return text or _fallback_reasoning(decision, risk, compliance)
    except Exception as exc:                                            # noqa: BLE001
        logger.warning("decision_reasoning_llm_failed", operation="reasoning", error=str(exc))
        return _fallback_reasoning(decision, risk, compliance)


def decision_maker(state: LoanProcessingState) -> LoanProcessingState:
    """Synthesize risk and compliance into a final underwriting decision."""
    log = logger.bind(poc_id="POC-01", phase=5, agent="decision_maker")
    started = time.perf_counter()

    with tracer.start_as_current_span("agent.decision_maker.activate") as span:
        span.set_attribute("agent.name", "decision_maker")

        risk = state.get("risk_assessment") or {}
        compliance = state.get("compliance_check") or {}
        application = state.get("application_data") or {}

        decision = _decide(risk, compliance)
        reasoning = _llm_reasoning(decision, risk, compliance, application)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        span.set_attribute("agent.final_decision", decision)
        span.set_attribute("agent.duration_ms", duration_ms)

        log.info("decision_made", operation="reasoning", decision=decision,
                  application_id=state.get("application_id"), duration_ms=duration_ms)

        return {
            **state,
            "final_decision": decision,
            "reasoning": reasoning,
            "current_agent": "decision_maker",
            "messages": state.get("messages", []) + [{
                "agent": "decision_maker",
                "message": f"Final Decision: {decision}",
            }],
        }
