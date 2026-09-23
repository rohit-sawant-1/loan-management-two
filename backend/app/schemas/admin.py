"""
Schemas for the System Administrator's screens (Piece 27).
"""

from pydantic import BaseModel

from app.schemas.auth import UserResponse


class AdminUserListResponse(BaseModel):
    # Each account uses the same shape as GET /auth/me: id, name, email, role,
    # is_active, created_at. The password hash is never in it.
    items: list[UserResponse]
    total_count: int
    # Every role, even at zero: {"applicant": 6, "loan_officer": 1, ...}
    counts_by_role: dict[str, int]


class PurgeTestDocumentsBody(BaseModel):
    """Piece 32: the admin has to type the exact phrase, not just tick a box."""
    confirm: str


class PurgeTestDocumentsResponse(BaseModel):
    purged_count: int
