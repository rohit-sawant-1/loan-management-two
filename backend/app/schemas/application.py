"""
Schemas for loan applications.

`CreateApplicationSchema` is a name the trainer's tests import (T-06).

The global amount and tenure bounds are checked here because test UNIT-04
expects the schema itself to reject them. The tighter per-loan-type limits
are checked in the service, where we can also explain why.
"""


from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import rules
from app.models.application import ApplicationStatus, LoanType
from app.schemas.applicant import ApplicantResponse
from app.schemas.common import UtcDateTime, clean_free_text
from app.schemas.document import DocumentResponse


class CreateApplicationSchema(BaseModel):
    applicant_id: int = Field(..., gt=0)
    loan_type: LoanType
    # Test UNIT-04 sends 5000, 15000000, -100 and 0 and expects all rejected.
    amount_requested: float = Field(..., ge=rules.AMOUNT_MIN, le=rules.AMOUNT_MAX)
    tenure_months: int = Field(..., ge=rules.TENURE_MIN, le=rules.TENURE_MAX)
    purpose: str = Field(..., min_length=rules.PURPOSE_MIN, max_length=rules.PURPOSE_MAX)

    # Piece 25: trims spaces before counting, so "   " no longer passes as a
    # purpose. A purpose that was valid before is still valid.
    @field_validator("purpose")
    @classmethod
    def _check_purpose(cls, value: str) -> str:
        return clean_free_text(value, rules.PURPOSE_MIN, rules.PURPOSE_MAX, "purpose")


class StatusUpdateRequest(BaseModel):
    new_status: ApplicationStatus
    remarks: str | None = Field(default=None, max_length=1000)


class StatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    old_status: ApplicationStatus | None
    new_status: ApplicationStatus
    changed_by: str
    changed_at: UtcDateTime | None = None
    remarks: str | None = None


class ApplicationResponse(BaseModel):
    """The full picture: the application, the borrower, every status change, every document."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    applicant_id: int
    loan_type: LoanType
    amount_requested: float
    tenure_months: int
    purpose: str
    status: ApplicationStatus
    submitted_at: UtcDateTime | None = None
    updated_at: UtcDateTime | None = None
    applicant: ApplicantResponse | None = None
    status_history: list[StatusHistoryResponse] = []
    documents: list[DocumentResponse] = []

    # Piece 19: the server's own eligibility assessment, taken at submission.
    eligibility_passed: bool | None = None
    eligibility_summary: str | None = None
    eligibility_checked_at: UtcDateTime | None = None


class ApplicationSummary(BaseModel):
    """One row in the list screen."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    applicant_id: int
    applicant_name: str | None = None
    loan_type: LoanType
    amount_requested: float
    tenure_months: int
    status: ApplicationStatus
    submitted_at: UtcDateTime | None = None


class ApplicationListResponse(BaseModel):
    """`items` is the key the trainer's test API-07 looks for."""
    items: list[ApplicationSummary]
    total_count: int
    page: int
    limit: int


class EligibilityCheckRequest(BaseModel):
    """What the form sends before submitting, to ask 'would this be allowed?' (D-01)."""
    applicant_id: int = Field(..., gt=0)
    loan_type: LoanType
    amount_requested: float = Field(..., ge=rules.AMOUNT_MIN, le=rules.AMOUNT_MAX)
    tenure_months: int = Field(..., ge=rules.TENURE_MIN, le=rules.TENURE_MAX)


class EligibilityRuleCheck(BaseModel):
    """One row of the assessment card: a rule, and whether this applicant met it."""
    label: str
    passed: bool
    detail: str | None = None   # only set when passed is False


class EligibilityCheckResponse(BaseModel):
    eligible: bool
    # Plain-language reasons, empty when eligible.
    problems: list[str] = []
    # Every rule checked, in order, so the form can show passes as well as failures.
    rule_checks: list[EligibilityRuleCheck] = []
    estimated_emi: float
    max_affordable_emi: float
    # Filled in when we can suggest a fix.
    suggested_amount: float | None = None
    suggested_tenure_months: int | None = None
