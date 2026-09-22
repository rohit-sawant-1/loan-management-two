"""
Schemas for edit requests (Piece 25): what a customer or staff member may
send, and what comes back.

These are the server's gate, the real check. The form checks the same things
earlier, but only so the person gets a friendly message; anything that skips
the form still has to get past these.

`extra="forbid"` on the incoming shapes means an unknown field is an error,
not something silently ignored. That matters most on `ApplicationEditBody`:
someone sending `"loan_type": "home"` or `"status": "approved"` there gets a
422, rather than a quiet chance that it slips through.
"""

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain import rules
from app.models.application import ApplicationStatus, LoanType
from app.models.edit_request import EditRequestStatus
from app.schemas.common import UtcDateTime, clean_free_text


class EditRequestCreate(BaseModel):
    """A customer asking to change some fields of their application, and why."""
    model_config = ConfigDict(extra="forbid")

    fields: list[str] = Field(..., min_length=1, max_length=len(rules.EDITABLE_FIELDS))
    reason: str

    @field_validator("fields")
    @classmethod
    def _check_fields(cls, value: list[str]) -> list[str]:
        unknown = [f for f in value if f not in rules.EDITABLE_FIELDS]
        if unknown:
            raise ValueError(
                f"only these can be changed: {', '.join(rules.EDITABLE_FIELDS)}"
            )
        if len(set(value)) != len(value):
            raise ValueError("each field may be listed only once")
        return value

    @field_validator("reason")
    @classmethod
    def _check_reason(cls, value: str) -> str:
        return clean_free_text(value, rules.EDIT_REASON_MIN, rules.EDIT_REASON_MAX, "reason")


class ApproveBody(BaseModel):
    """Staff saying yes. A note is welcome but not required."""
    model_config = ConfigDict(extra="forbid")

    note: str | None = None

    @field_validator("note")
    @classmethod
    def _check_note(cls, value: str | None) -> str | None:
        # A box left empty, or only spaces, means "no note".
        if value is None or not value.strip():
            return None
        return clean_free_text(value, 1, rules.EDIT_NOTE_MAX, "note")


class RefuseBody(BaseModel):
    """Staff saying no. The customer is owed a reason, so the note is required."""
    model_config = ConfigDict(extra="forbid")

    note: str

    @field_validator("note")
    @classmethod
    def _check_note(cls, value: str) -> str:
        return clean_free_text(value, rules.EDIT_NOTE_MIN, rules.EDIT_NOTE_MAX, "note")


class ApplicationEditBody(BaseModel):
    """
    The customer saving their approved edit. Each field is optional because
    they only send the ones staff unlocked. The bounds are the same ones
    `CreateApplicationSchema` uses, all read from `rules.py`. The tighter
    per-loan-type limits are checked in the service, exactly as on create.
    """
    model_config = ConfigDict(extra="forbid")

    amount_requested: float | None = Field(default=None, ge=rules.AMOUNT_MIN, le=rules.AMOUNT_MAX)
    tenure_months: int | None = Field(default=None, ge=rules.TENURE_MIN, le=rules.TENURE_MAX)
    purpose: str | None = None

    @field_validator("purpose")
    @classmethod
    def _check_purpose(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_free_text(value, rules.PURPOSE_MIN, rules.PURPOSE_MAX, "purpose")

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.amount_requested is None and self.tenure_months is None and self.purpose is None:
            raise ValueError("send at least one of amount_requested, tenure_months, purpose")
        return self

    def changed_fields(self) -> dict:
        """Only the fields actually sent, as {name: new value}."""
        return {name: value for name, value in self.model_dump().items() if value is not None}


class EditRequestResponse(BaseModel):
    """One request, with enough about its application for the staff table."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    requested_by: str
    fields: list[str]
    reason: str
    status: EditRequestStatus
    decided_by: str | None = None
    decided_at: UtcDateTime | None = None
    decision_note: str | None = None
    created_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None

    # Read from the row's properties (see `app/models/edit_request.py`).
    applicant_name: str | None = None
    loan_type: LoanType | None = None
    application_status: ApplicationStatus | None = None

    @field_validator("fields", mode="before")
    @classmethod
    def _parse_fields(cls, value):
        # Stored as a JSON string in the database; sent out as a real list.
        return json.loads(value) if isinstance(value, str) else value


class EditRequestListResponse(BaseModel):
    """Same shape as the applications list: items plus paging."""
    items: list[EditRequestResponse]
    total_count: int
    page: int
    limit: int
