"""
The fourteen database tables.

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
from app.models.app_setting import AppSetting
from app.models.notification import (
    Notification, NotificationAudience, NotificationType,
)
from app.models.stored_file import StoredFile, StoredFileNature, StorageZone
from app.models.extraction import DocumentExtraction, ExtractedField
from app.models.chat import ChatMessage, ChatSession

__all__ = [
    "User", "UserRole",
    "Applicant", "EmploymentStatus",
    "LoanApplication", "LoanType", "ApplicationStatus",
    "Document", "DocumentType",
    "StatusHistory",
    "ActivityLog", "ActorType",
    "EditRequest", "EditRequestStatus",
    "AppSetting",
    "Notification", "NotificationAudience", "NotificationType",
    "StoredFile", "StoredFileNature", "StorageZone",
    "DocumentExtraction", "ExtractedField",
    "ChatSession", "ChatMessage",
]
