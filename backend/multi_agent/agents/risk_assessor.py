"""
Agent 2: how risky is this loan.

The trainer's own reference has the LLM compute every number itself,
straight into JSON, and their own tips list warns what that costs: "JSON
parsing fails in Risk Assessor... have fallback values." For a bank
underwriting numbers a decision hangs on, that is the wrong trade. Every
number below — the EMI, the debt-to-income ratio, the credit and employment
risk tiers, the overall score — is computed the same deterministic way
Phase 1's own eligibility check works, from the same `domain/rules.py`
thresholds the whole project already agreed on (D-10, T-13, T-14). The LLM's
job is narrower and better suited to it: write the 2-3 sentence
`risk_summary` a human underwriter reads, in plain English, from numbers
that are already known to be right. If that one call fails or times out,
a short deterministic sentence takes its place — the score itself never
depends on the network.
"""

import time

import structlog
from opentelemetry import trace

from app.domain import rules
from app.utils.finance import calculate_emi, format_rupees, max_affordable_emi
from llm_provider import get_llm
from multi_agent.llm_text import text_of
from multi_agent.state import LoanProcessingState

logger = structlog.get_logger()
tracer = trace.get_tracer("risk-assessor")


def _credit_risk_level(credit_score) -> str:
    if credit_score is None or credit_score < rules.CIBIL_MEDIUM_RISK_FROM:
        return "high"
    if credit_score < rules.CIBIL_LOW_RISK_FROM:
        return "medium"
    return "low"


def _employment_risk_level(employment_status: str, years_with_employer) -> str:
    if employment_status == "unemployed":
        return "high"
    if employment_status == "salaried" and (years_with_employer or 0) >= rules.LOW_RISK_EMPLOYMENT_YEARS:
        return "low"
    return "medium"   # self-employed, or salaried under the low-risk threshold


def _overall_score(credit_risk: str, employment_risk: str, emi_affordability: str) -> float:
    score = rules.RISK_SCORE_START
    if credit_risk == "high":
        score -= rules.RISK_DEDUCTIONS["credit_high"]
    elif credit_risk == "medium":
        score -= rules.RISK_DEDUCTIONS["credit_medium"]
    if employment_risk == "high":
        score -= rules.RISK_DEDUCTIONS["employment_high"]
    elif employment_risk == "medium":
        score -= rules.RISK_DEDUCTIONS["employment_medium"]
    if emi_affordability == "no":
        score -= rules.RISK_DEDUCTIONS["emi_unaffordable"]
    return float(max(0, score))


def _fallback_summary(risk_data: dict) -> str:
    return (f"Overall risk score {risk_data['overall_risk_score']:.0f}/100. "
            f"Credit risk {risk_data['credit_risk_level']}, employment risk "
            f"{risk_data['employment_risk']}. EMI affordability: {risk_data['emi_affordability']}.")


def _llm_summary(risk_data: dict) -> str:
    """A short, plain-English summary of numbers already computed. Never raises."""
    try:
        llm = get_llm(temperature=0)
        prompt = (
            "You are a bank risk analyst. In 2-3 plain sentences, summarise this "
            f"loan applicant's risk profile for a colleague: overall risk score "
            f"{risk_data['overall_risk_score']:.0f} out of 100 (higher is better), "
            f"credit risk {risk_data['credit_risk_level']}, employment risk "
            f"{risk_data['employment_risk']}, estimated EMI "
            f"{format_rupees(risk_data['emi_amount'])} a month, which is "
            f"{'affordable' if risk_data['emi_affordability'] == 'yes' else 'not affordable'} "
            f"against their income. State the numbers plainly; do not invent anything not given."
        )
        response = llm.invoke(prompt)
        text = text_of(response.content)
        return text or _fallback_summary(risk_data)
    except Exception as exc:                                            # noqa: BLE001
        logger.warning("risk_summary_llm_failed", operation="reasoning", error=str(exc))
        return _fallback_summary(risk_data)


def risk_assessor(state: LoanProcessingState) -> LoanProcessingState:
    """Evaluate financial risk of the loan application."""
    log = logger.bind(poc_id="POC-01", phase=5, agent="risk_assessor")
    started = time.perf_counter()

    with tracer.start_as_current_span("agent.risk_assessor.activate") as span:
        span.set_attribute("agent.name", "risk_assessor")

        applicant = state.get("applicant_data") or {}
        application = state.get("application_data") or {}

        annual_income = applicant.get("annual_income") or 0.0
        monthly_income = annual_income / 12 if annual_income else 0.0
        amount = application.get("amount_requested") or 0.0
        tenure = application.get("tenure_months") or 0

        emi_amount = (calculate_emi(amount, rules.DEFAULT_ANNUAL_INTEREST_RATE, tenure)
                      if amount > 0 and tenure > 0 else 0.0)

        existing_emi = applicant.get("existing_monthly_emi")
        if existing_emi is None:
            # No figure on file: assume the manual's default share of income (D-14).
            existing_emi = monthly_income * rules.ASSUMED_EXISTING_OBLIGATION_SHARE

        dti = round((existing_emi + emi_amount) / monthly_income, 2) if monthly_income else 1.0

        # What is left of the 50% share after what they already pay out each
        # month, not the whole 50%. This is the same helper Phase 1's
        # eligibility check uses, so the form and the underwriting review can
        # no longer reach opposite verdicts on one applicant (D-27).
        room = max_affordable_emi(annual_income, existing_emi)
        emi_affordability = "yes" if emi_amount <= room else "no"

        credit_risk_level = _credit_risk_level(applicant.get("credit_score"))
        employment_risk = _employment_risk_level(
            applicant.get("employment_status", "unemployed"), applicant.get("years_with_employer")
        )
        overall_risk_score = _overall_score(credit_risk_level, employment_risk, emi_affordability)

        risk_data = {
            "debt_to_income_ratio": dti,
            "emi_amount": emi_amount,
            "emi_affordability": emi_affordability,
            "credit_risk_level": credit_risk_level,
            "employment_risk": employment_risk,
            "overall_risk_score": overall_risk_score,
        }
        risk_data["risk_summary"] = _llm_summary(risk_data)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        span.set_attribute("agent.risk_score", overall_risk_score)
        span.set_attribute("agent.duration_ms", duration_ms)

        log.info("risk_assessment_complete", operation="reasoning",
                  risk_score=overall_risk_score, credit_risk=credit_risk_level,
                  duration_ms=duration_ms)

        return {
            **state,
            "risk_assessment": risk_data,
            "current_agent": "risk_assessor",
            "messages": state.get("messages", []) + [{
                "agent": "risk_assessor",
                "message": (f"Risk score: {overall_risk_score:.0f}/100. Credit risk: "
                            f"{credit_risk_level}. EMI affordable: {emi_affordability}."),
            }],
        }
