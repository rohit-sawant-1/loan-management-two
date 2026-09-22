"""
Addresses for the System Administrator (Piece 27). Mounted at /api/v1/admin.

Admin only. Everything here only reads, for now. Piece 28 adds the settings.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.schemas.admin import AdminUserListResponse
from app.schemas.auth import UserResponse
from app.services import admin_service

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
