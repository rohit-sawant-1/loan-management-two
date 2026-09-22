"""
The `application_edit_requests` table: a customer asking to change their
application, and what the bank staff decided (Piece 25, D-28).

One row is one request. It moves through the statuses in
`rules.EDIT_REQUEST_STATUSES`: pending, then approved or refused, and an
approved one becomes completed once the customer saves. If the application's
status moves on first, the request becomes closed.

**The database checks its own rules here.** This table is brand new, so its
CHECK rules can sit inside the table definition, unlike `loan_applications`,
which needs triggers (see `app/db_checks.py`). Every number comes from
`rules.py`.
"""

import enum

from sqlalchemy import CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.db_checks import quoted_list
from app.domain import rules


class EditRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    refused = "refused"
    completed = "completed"
    closed = "closed"


class EditRequest(Base):
    __tablename__ = "application_edit_requests"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id"), nullable=False, index=True)

    # What the customer asked for.
    requested_by = Column(String(150), nullable=False)       # the customer's email
    fields = Column(Text, nullable=False)                     # JSON list, e.g. ["amount_requested"]
    reason = Column(String(rules.EDIT_REASON_MAX), nullable=False)

    # Indexed because the staff page filters by it ("show me what's waiting").
    status = Column(
        Enum(EditRequestStatus),
        nullable=False,
        default=EditRequestStatus.pending,
        index=True,
    )

    # What the staff member decided. Empty until someone decides.
    decided_by = Column(String(150), nullable=True)           # staff email
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(String(rules.EDIT_NOTE_MAX), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)   # when the edit was saved

    application = relationship("LoanApplication", back_populates="edit_requests")

    __table_args__ = (
        CheckConstraint(
            f"status IN ({quoted_list(rules.EDIT_REQUEST_STATUSES)})",
            name="ck_edit_request_status",
        ),
        # A JSON list with at least one field in it. "[]" is an empty list.
        CheckConstraint("fields LIKE '[%]' AND fields <> '[]'", name="ck_edit_request_fields"),
        CheckConstraint(
            f"length(trim(reason)) BETWEEN {rules.EDIT_REASON_MIN} AND {rules.EDIT_REASON_MAX}",
            name="ck_edit_request_reason",
        ),
        CheckConstraint(
            f"decision_note IS NULL OR length(decision_note) <= {rules.EDIT_NOTE_MAX}",
            name="ck_edit_request_note_length",
        ),
        # A refusal must always say why.
        CheckConstraint(
            f"status <> 'refused' OR length(trim(coalesce(decision_note, ''))) >= {rules.EDIT_NOTE_MIN}",
            name="ck_edit_request_refusal_note",
        ),
    )

    # --- Read-only conveniences for the staff table ---------------------------
    # The response schema reads these by name. The service loads the
    # application and applicant in the same query, so reading them here does
    # not cost one extra query per row.

    @property
    def applicant_name(self) -> str | None:
        return self.application.applicant.name if self.application and self.application.applicant else None

    @property
    def loan_type(self):
        return self.application.loan_type if self.application else None

    @property
    def application_status(self):
        return self.application.status if self.application else None
