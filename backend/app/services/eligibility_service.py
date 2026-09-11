"""
"Would this loan be allowed?" — asked by the form before submitting (D-01).

Advisory only. It never blocks a submission; it explains problems and
suggests a fix where it can. Every threshold comes from the rules file.
"""

import structlog
from sqlalchemy.orm import Session

from app.domain import rules
from app.models.applicant import Applicant, EmploymentStatus
from app.models.user import User, UserRole
from app.schemas.application import (
    EligibilityCheckRequest, EligibilityCheckResponse, EligibilityRuleCheck,
)
from app.services import activity_service
from app.services.errors import Forbidden, NotFound
from app.utils.text import readable
from app.utils.dates import age_on
from app.utils.finance import (
    calculate_emi, format_rupees, max_affordable_emi, max_principal_for_emi,
)

logger = structlog.get_logger()

_rupees = format_rupees   # Indian grouping: ₹25,00,000 not ₹2,500,000


class Assessment:
    """
    The result of running every eligibility rule once, for one applicant and
    one requested loan. Both the advisory `check()` endpoint and the
    permanent record stored at submission (Piece 19) are built from this, so
    the two can never quietly disagree with each other.
    """
    def __init__(self):
        self.rule_checks: list[EligibilityRuleCheck] = []
        self.problems: list[str] = []
        self.estimated_emi: float = 0.0
        self.affordable_emi: float = 0.0
        self.suggested_amount: float | None = None
        self.suggested_tenure: int | None = None

    @property
    def eligible(self) -> bool:
        return not self.problems

    def _row(self, label: str, passed: bool, detail: str | None = None):
        self.rule_checks.append(EligibilityRuleCheck(label=label, passed=passed, detail=detail))
        if not passed and detail:
            self.problems.append(detail)


def assess(applicant: Applicant, loan_type: str, amount: float, tenure: int) -> Assessment:
    """
    Runs every rule the manual lists (Section 5) against one applicant and
    one requested loan, in the fixed order the summary card shows: tenure,
    amount, income, credit score, employment, age, affordability.
    """
    result = Assessment()
    suggested_amount: float | None = None
    suggested_tenure: int | None = None

    # ---- Tenure, per loan type (D-02) ----
    lo, hi = rules.tenure_range(loan_type)
    tenure_ok = lo <= tenure <= hi
    result._row(
        f"Tenure within {lo}-{hi} months for a {loan_type} loan", tenure_ok,
        None if tenure_ok else f"A {loan_type} loan must run between {lo} and {hi} months.",
    )
    if not tenure_ok:
        suggested_tenure = min(max(tenure, lo), hi)

    # ---- Amount, per loan type (D-03) ----
    cap = rules.amount_limit(loan_type)
    amount_ok = amount <= cap
    result._row(
        f"Amount within the {_rupees(cap)} {loan_type} loan limit", amount_ok,
        None if amount_ok else f"A {loan_type} loan cannot exceed {_rupees(cap)}.",
    )
    if not amount_ok:
        suggested_amount = float(cap)

    # ---- Income (manual Section 5) ----
    min_income = rules.MIN_ANNUAL_INCOME[loan_type]
    income_ok = applicant.annual_income >= min_income
    result._row(
        f"Annual income at or above {_rupees(min_income)}", income_ok,
        None if income_ok else (
            f"A {loan_type} loan needs an annual income of at least {_rupees(min_income)}; "
            f"the profile shows {_rupees(applicant.annual_income)}."
        ),
    )

    # ---- Credit score (manual Section 5 and FAQ) ----
    min_cibil = rules.MIN_CIBIL_SCORE[loan_type]
    if applicant.credit_score is None:
        # Only personal loans strictly require a CIBIL score on file.
        credit_ok = loan_type != "personal"
        detail = None if credit_ok else (
            "Personal loans need a CIBIL score. Applicants without one may be "
            "considered for a home or auto loan instead."
        )
        result._row(f"CIBIL score at or above {min_cibil}", credit_ok, detail)
    else:
        credit_ok = applicant.credit_score >= min_cibil
        result._row(
            f"CIBIL score at or above {min_cibil}", credit_ok,
            None if credit_ok else (
                f"A {loan_type} loan needs a CIBIL score of at least {min_cibil}; "
                f"the profile shows {applicant.credit_score}."
            ),
        )

    # ---- Employment (manual Section 5 and FAQ, D-16) ----
    if applicant.employment_status == EmploymentStatus.unemployed:
        result._row("Employment: salaried or self-employed", False,
                    "Applicants must be salaried or self-employed.")
    else:
        need = rules.MIN_YEARS_WITH_EMPLOYER.get(applicant.employment_status.value)
        have = applicant.years_with_employer
        what = "with the current employer" if applicant.employment_status == EmploymentStatus.salaried else "of business history"
        if need is None or have is None:
            result._row(f"Employment: {applicant.employment_status.value}, length on file", True)
        else:
            emp_ok = have >= need
            result._row(
                f"Employment: {applicant.employment_status.value}, {have:g} years {what}", emp_ok,
                None if emp_ok else f"Needs at least {int(round(need * 12))} months {what}; the profile shows {have:g} years.",
            )

    # ---- Age (manual Section 5, D-05) ----
    if applicant.date_of_birth is not None:
        age = age_on(applicant.date_of_birth)
        min_age, max_age = rules.AGE_LIMITS[loan_type]
        age_ok = min_age <= age <= max_age
        label = f"Age {age} within {min_age}-{max_age}"
        if not age_ok:
            result._row(label, False, f"A {loan_type} loan is available from age {min_age} to {max_age}; the applicant is {age}.")
        elif loan_type == "home":
            months_left = (rules.HOME_LOAN_MUST_END_BEFORE_AGE - age) * 12
            end_ok = tenure <= months_left
            result._row(
                f"{label}, and the loan ends before age {rules.HOME_LOAN_MUST_END_BEFORE_AGE}", end_ok,
                None if end_ok else (
                    f"A home loan must be repaid before age {rules.HOME_LOAN_MUST_END_BEFORE_AGE}. "
                    f"At {age}, the longest tenure is {months_left} months."
                ),
            )
            if not end_ok:
                suggested_tenure = min(months_left, hi) if months_left >= lo else suggested_tenure
        else:
            result._row(label, True)
    else:
        result._row("Age on file", True)   # nothing to check against; not held against the applicant

    # ---- Affordability (D-14): this EMI plus existing EMIs within 50% of income ----
    rate = rules.DEFAULT_ANNUAL_INTEREST_RATE
    estimated_emi = calculate_emi(amount, rate, tenure)
    affordable = max_affordable_emi(applicant.annual_income, applicant.existing_monthly_emi)
    afford_ok = estimated_emi <= affordable
    share = int(rules.EMI_MAX_SHARE_OF_INCOME * 100)
    result._row(
        f"Affordability — estimated EMI {_rupees(estimated_emi)} within {share}% of income ({_rupees(affordable)})",
        afford_ok,
        None if afford_ok else (
            f"The estimated EMI of {_rupees(estimated_emi)} a month exceeds the {share}% of monthly "
            f"income available for loan payments ({_rupees(affordable)})."
        ),
    )
    if not afford_ok:
        if suggested_amount is None:
            ok_amount = max_principal_for_emi(affordable, rate, tenure)
            if ok_amount >= rules.AMOUNT_MIN:
                suggested_amount = round(ok_amount, -3)
        if suggested_tenure is None:
            lo, hi = rules.tenure_range(loan_type)
            for months in range(lo, hi + 1, 6):
                if calculate_emi(amount, rate, months) <= affordable:
                    suggested_tenure = months
                    break

    result.estimated_emi = estimated_emi
    result.affordable_emi = affordable
    result.suggested_amount = suggested_amount
    result.suggested_tenure = suggested_tenure
    return result


def build_summary_text(
    applicant: Applicant, loan_type: str, amount: float, tenure: int,
    result: Assessment, *, submitted_by: str | None = None,
) -> str:
    """
    The readable note stored on the application (Piece 19). Written like
    something a person would jot down, not a dump of field names.
    """
    passed_count = sum(1 for r in result.rule_checks if r.passed)
    total = len(result.rule_checks)
    verdict = "ELIGIBLE" if result.eligible else "NOT ELIGIBLE"

    # No timestamp in this text, deliberately. The moment of the assessment is
    # stored properly next to it, in `eligibility_checked_at`, which is a real
    # datetime field and reaches the browser as one — so the browser shows it in
    # the reader's own timezone like every other date in the app. Writing the
    # same instant into this string as a UTC wall clock meant the card printed
    # one event at two times five and a half hours apart: the paragraph above in
    # IST, the text below in UTC. One fact, one field.
    lines = [
        f"Applicant: {applicant.name} — CIBIL {applicant.credit_score if applicant.credit_score is not None else 'not on file'}, "
        f"annual income {_rupees(applicant.annual_income)}, "
        f"{readable(applicant.employment_status.value)}"
        + (f" {applicant.years_with_employer:g} years" if applicant.years_with_employer is not None else "")
        + (f", age {age_on(applicant.date_of_birth)}" if applicant.date_of_birth is not None else "") + ".",
        f"Requested: {loan_type} loan of {_rupees(amount)} over {tenure} months. "
        f"Estimated EMI {_rupees(result.estimated_emi)} a month at the indicative rate of "
        f"{rules.DEFAULT_ANNUAL_INTEREST_RATE:g}%.",
        "",
        f"Result: {verdict} — {passed_count} of {total} rules met.",
        "",
    ]
    for row in result.rule_checks:
        mark = "PASS" if row.passed else "FAIL"
        lines.append(f"  {mark}  {row.label}")
        if not row.passed and row.detail:
            lines.append(f"        {row.detail}")
    if not result.eligible and submitted_by:
        lines.append("")
        lines.append(f"Submitted anyway by {submitted_by}.")
    return "\n".join(lines)


def check(
    db: Session, data: EligibilityCheckRequest, *, viewer: User, meta: dict | None = None
) -> EligibilityCheckResponse:
    applicant = db.query(Applicant).filter(Applicant.id == data.applicant_id).first()
    if applicant is None:
        raise NotFound("Applicant not found")
    if viewer.role == UserRole.applicant and applicant.user_id != viewer.id:
        raise Forbidden("You can only check eligibility for yourself")

    loan_type = data.loan_type.value
    result = assess(applicant, loan_type, data.amount_requested, data.tenure_months)

    response = EligibilityCheckResponse(
        eligible=result.eligible,
        problems=result.problems,
        rule_checks=result.rule_checks,
        estimated_emi=result.estimated_emi,
        max_affordable_emi=result.affordable_emi,
        suggested_amount=result.suggested_amount,
        suggested_tenure_months=result.suggested_tenure,
    )

    activity_service.record(
        db, action="eligibility_checked",
        actor_id=viewer.email, actor_role=viewer.role.value,
        entity_type="applicant", entity_id=applicant.id,
        details={"loan_type": loan_type, "amount": data.amount_requested, "tenure_months": data.tenure_months,
                 "eligible": response.eligible, "problem_count": len(result.problems)},
        **(meta or {}),
    )
    db.commit()
    logger.info("eligibility_checked", applicant_id=applicant.id, loan_type=loan_type,
                eligible=response.eligible, problems=len(result.problems))
    return response
