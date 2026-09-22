"""
The `loan_applications` table: one loan request.

Also defines the two enums the tests import from this exact module:
`LoanType` and `ApplicationStatus`.
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.db_checks import install_loan_application_checks


class LoanType(str, enum.Enum):
    personal = "personal"
    home = "home"
    auto = "auto"


class ApplicationStatus(str, enum.Enum):
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    disbursed = "disbursed"


class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False, index=True)

    # Indexed because the list screen filters and sorts by these.
    loan_type = Column(Enum(LoanType), nullable=False, index=True)
    amount_requested = Column(Float, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    purpose = Column(String(500), nullable=False)
    status = Column(
        Enum(ApplicationStatus),
        nullable=False,
        default=ApplicationStatus.submitted,
        index=True,
    )

    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # onupdate: the database refreshes this whenever the row changes.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Piece 19: the server's own eligibility assessment, taken at the moment
    # of submission. Since Piece 25 the one thing that replaces it is an
    # approved edit, which re-checks the new figures; the old assessment is
    # kept in that edit's activity row. All three are nullable so rows created
    # before Piece 19 existed still load fine.
    eligibility_passed = Column(Boolean, nullable=True)
    eligibility_summary = Column(Text, nullable=True)
    eligibility_checked_at = Column(DateTime(timezone=True), nullable=True)

    applicant = relationship("Applicant", back_populates="applications")

    # cascade="all, delete-orphan": when an application is deleted, its
    # documents and history rows are deleted with it. This is done by
    # SQLAlchemy, not by the database, so it works even though SQLite's
    # foreign-key checking is off (TRAPS T-03, T-04). Test DB-04 relies on it.
    documents = relationship(
        "Document", back_populates="application", cascade="all, delete-orphan"
    )
    status_history = relationship(
        "StatusHistory",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="StatusHistory.changed_at",   # oldest first, as the spec says
    )
    # Piece 25. Same cascade as above, so deleting an application also removes
    # its edit requests instead of leaving them pointing at nothing.
    edit_requests = relationship(
        "EditRequest",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="EditRequest.created_at",
    )


# Piece 25: whenever this table is freshly created (a new database, or every
# test run), add the database's own checks straight away. An existing database
# gets them from `init_db()` instead. See `app/db_checks.py` for why these are
# triggers.
@event.listens_for(LoanApplication.__table__, "after_create")
def _add_database_checks(target, connection, **kw):
    install_loan_application_checks(connection)
