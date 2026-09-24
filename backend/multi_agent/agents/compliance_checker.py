"""
Agent 3: are the regulatory and documentation boxes ticked.

Every rule here reads from `app.domain.rules` — the required documents per
loan type, the amount limit — rather than a second copy of those numbers
kept only in this file, so Phase 1 and Phase 5 can never quietly disagree
about what a home loan requires.

The age check is the one place this file deliberately does NOT match the
trainer's own reference code. Their skeleton reads:

    age_eligible = applicant.get("credit_score") is not None or True  # Simplified

The trailing `or True` makes the whole expression always true no matter what
came before it, and what it inspects is a credit score, not an age — see
`AI-BUILD-LOG.md`. This project added `date_of_birth` to the applicant model
specifically so a real check would not need excusing (D-05). When the date
of birth is genuinely missing, age passes by default: a bank cannot fail
someone on data it never asked for.
"""

import time
from datetime import date

import structlog
from opentelemetry import trace

from app.domain import rules
from app.utils.dates import age_on
from app.utils.finance import format_rupees
from app.utils.text import readable_list
from multi_agent.state import LoanProcessingState

logger = structlog.get_logger()
tracer = trace.get_tracer("compliance-checker")


def _check_age(applicant: dict, loan_type: str, tenure_months: int) -> bool:
    dob_raw = applicant.get("date_of_birth")
    if not dob_raw:
        return True   # nothing to check against; not held against the applicant

    dob = date.fromisoformat(str(dob_raw)[:10])
    age = age_on(dob)
    lo, hi = rules.AGE_LIMITS.get(loan_type, (21, 65))
    if not lo <= age <= hi:
        return False
    if loan_type == "home":
        months_left = (rules.HOME_LOAN_MUST_END_BEFORE_AGE - age) * 12
        if tenure_months > months_left:
            return False
    return True


def compliance_checker(state: LoanProcessingState) -> LoanProcessingState:
    """Verify regulatory and documentation compliance."""
    log = logger.bind(poc_id="POC-01", phase=5, agent="compliance_checker")
    started = time.perf_counter()

    with tracer.start_as_current_span("agent.compliance_checker.activate") as span:
        span.set_attribute("agent.name", "compliance_checker")

        application = state.get("application_data") or {}
        applicant = state.get("applicant_data") or {}
        # Piece 33: a real file whose details aren't confirmed yet doesn't
        # count, the same rule as the checklist. Name-only documents never
        # need details, so the seeded applications are judged as before.
        documents = [d for d in (state.get("documents") or []) if not d.get("needs_details")]

        loan_type = application.get("loan_type", "personal")
        amount = application.get("amount_requested", 0)
        tenure_months = application.get("tenure_months", 0)

        uploaded_types = {doc.get("doc_type") for doc in documents if doc.get("doc_type")}
        # D-32: an employment letter only for a salaried home-loan applicant.
        # No status in the data (as in the trainer's tests) keeps it required.
        missing = rules.missing_documents(loan_type, uploaded_types, applicant.get("employment_status"))
        documents_complete = not missing

        id_docs = [d for d in documents if d.get("doc_type") == "id_proof"]
        kyc_verified = any(d.get("verified", False) for d in id_docs)

        amount_within_limit = amount <= rules.amount_limit(loan_type)
        age_eligible = _check_age(applicant, loan_type, tenure_months)

        compliance_passed = documents_complete and amount_within_limit and age_eligible

        # These notes are read twice: by a person on screen, and by the model,
        # which injects them wholesale into the decision prompt
        # (`decision_maker.py`). So they carry their units and their words in
        # full — a bare "2,500,000" here is how the AI ended up writing dollars
        # (T-94), and a bare "id_proof" is how it ends up saying "id_proof" to a
        # loan officer.
        notes = []
        if missing:
            notes.append(f"Missing documents: {readable_list(missing)}")
        if not amount_within_limit:
            notes.append(f"Amount exceeds the {loan_type} loan limit of "
                         f"{format_rupees(rules.amount_limit(loan_type))}")
        if not age_eligible:
            notes.append("Applicant's age does not meet this loan type's eligibility window")
        if not kyc_verified:
            notes.append("KYC (identity) documents not yet verified")
        if any(d.get("nature") == "test" for d in documents):
            notes.append("Includes TEST documents — not genuine")

        compliance_data = {
            "documents_complete": documents_complete,
            "missing_documents": missing,
            "kyc_verified": kyc_verified,
            "amount_within_limit": amount_within_limit,
            "age_eligible": age_eligible,
            "compliance_passed": compliance_passed,
            "compliance_notes": "; ".join(notes) if notes else "All compliance checks passed",
        }

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        span.set_attribute("agent.compliance_passed", compliance_passed)
        span.set_attribute("agent.missing_docs", len(missing))
        span.set_attribute("agent.duration_ms", duration_ms)

        log.info("compliance_check_complete", operation="reasoning",
                  compliance_passed=compliance_passed, missing_docs=len(missing),
                  duration_ms=duration_ms)

        return {
            **state,
            "compliance_check": compliance_data,
            "current_agent": "compliance_checker",
            "messages": state.get("messages", []) + [{
                "agent": "compliance_checker",
                "message": (f"Compliance: {'PASSED' if compliance_passed else 'FAILED'}. "
                            f"{compliance_data['compliance_notes']}"),
            }],
        }
