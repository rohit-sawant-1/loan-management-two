"""
Addresses for the System Administrator (Piece 27). Mounted at /api/v1/admin.

Admin only. Reading the accounts, and the one address that changes a system
setting (Piece 28). Everyone else reads settings through GET /settings.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.schemas.admin import (
    AdminUserListResponse, PurgeTestDocumentsBody, PurgeTestDocumentsResponse,
)
from app.schemas.auth import UserResponse
from app.schemas.settings import RealUploadsBody, SettingResponse
from app.services import admin_service, settings_service
from app.services.activity_service import request_meta
from app.services.errors import RuleViolation

REAL_UPLOADS = "real_uploads_enabled"
PURGE_CONFIRMATION = "DELETE TEST DOCUMENTS"

router = APIRouter()


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Every account in the system, with a count per role."""
    users, counts = admin_service.list_users(db)
    return AdminUserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total_count=len(users),
        counts_by_role=counts,
    )


@router.get("/settings/real-uploads", response_model=SettingResponse)
def read_real_uploads(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """The switch as the admin screen shows it: the value, who changed it, and when."""
    return settings_service.describe(db, REAL_UPLOADS)


@router.put("/settings/real-uploads", response_model=SettingResponse)
def set_real_uploads(
    body: RealUploadsBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Turn real document uploads on or off for the whole app.

    OFF is exactly what the app did before this piece: a document is recorded
    by its name. ON is what Piece 31's real uploads will read.
    """
    try:
        return settings_service.set_value(
            db, REAL_UPLOADS, body.enabled, user=user, meta=request_meta(request)
        )
    except RuleViolation as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)


@router.post("/test-documents/purge", response_model=PurgeTestDocumentsResponse)
def purge_test_documents(
    body: PurgeTestDocumentsBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """
    Delete every document the server marked TEST — the file, the row that
    describes it, and the document pointing at it. Typing the phrase wrong
    is the safeguard; there is no undo once this runs.
    """
    if body.confirm != PURGE_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Type "{PURGE_CONFIRMATION}" exactly to confirm.',
        )
    count = admin_service.purge_test_documents(db, user=user, meta=request_meta(request))
    return PurgeTestDocumentsResponse(purged_count=count)
