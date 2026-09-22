"""
Schemas: what each request may contain, and what each response looks like.

Pydantic checks incoming data against these before any of our code runs.
Bad data gets a 422 error listing the exact problems.
"""

from app.schemas.auth import (
    RegisterRequest, ApplicantSignupRequest, LoginRequest, TokenResponse, UserResponse,
)
from app.schemas.applicant import CreateApplicantSchema, ApplicantResponse
from app.schemas.application import (
    CreateApplicationSchema, StatusUpdateRequest, StatusHistoryResponse,
    ApplicationResponse, ApplicationSummary, ApplicationListResponse,
    EligibilityCheckRequest, EligibilityCheckResponse,
)
from app.schemas.document import (
    CreateDocumentSchema, DocumentUploadBody, DocumentResponse, DocumentListResponse,
)
from app.schemas.activity import ActivityLogResponse
from app.schemas.edit_request import (
    EditRequestCreate, ApproveBody, RefuseBody, ApplicationEditBody,
    EditRequestResponse, EditRequestListResponse,
)
from app.schemas.admin import AdminUserListResponse
from app.schemas.settings import RealUploadsBody, SettingResponse, SettingsResponse
from app.schemas.notification import (
    NotificationListResponse, NotificationResponse, UnreadCountResponse,
)

__all__ = [
    "RegisterRequest", "ApplicantSignupRequest", "LoginRequest", "TokenResponse", "UserResponse",
    "CreateApplicantSchema", "ApplicantResponse",
    "CreateApplicationSchema", "StatusUpdateRequest", "StatusHistoryResponse",
    "ApplicationResponse", "ApplicationSummary", "ApplicationListResponse",
    "EligibilityCheckRequest", "EligibilityCheckResponse",
    "CreateDocumentSchema", "DocumentUploadBody", "DocumentResponse", "DocumentListResponse",
    "ActivityLogResponse",
    "EditRequestCreate", "ApproveBody", "RefuseBody", "ApplicationEditBody",
    "EditRequestResponse", "EditRequestListResponse",
    "AdminUserListResponse",
    "RealUploadsBody", "SettingResponse", "SettingsResponse",
    "NotificationListResponse", "NotificationResponse", "UnreadCountResponse",
]
