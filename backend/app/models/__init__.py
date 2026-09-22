"""
The seven database tables.

Importing this package registers every table with `Base`, which is what
`init_db()` relies on to create them all.
"""

from app.models.user import User, UserRole
from app.models.applicant import Applicant, EmploymentStatus
from app.models.application import LoanApplication, LoanType, ApplicationStatus
from app.models.document import Document, DocumentType
from app.models.status_history import StatusHistory
from app.models.activity_log import ActivityLog, ActorType
from app.models.edit_request import EditRequest, EditRequestStatus

__all__ = [
    "User", "UserRole",
    "Applicant", "EmploymentStatus",
    "LoanApplication", "LoanType", "ApplicationStatus",
    "Document", "DocumentType",
    "StatusHistory",
    "ActivityLog", "ActorType",
    "EditRequest", "EditRequestStatus",
]
