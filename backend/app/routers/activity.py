"""
The manager's window onto the activity log (D-11). Mounted at /api/v1/activity.

Branch manager only. Reading the log never writes to it.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_audit_view
from app.models.activity_log import ActorType
from app.models.user import User
from app.schemas.activity import ActivityLogResponse
from app.services import activity_service

router = APIRouter()

# Which records can be asked about by type. Keeps the address from becoming a free-text query.
_ENTITY_TYPES = ("application", "applicant", "document", "user")


class ActivityListResponse(BaseModel):
    items: list[ActivityLogResponse]
    total_count: int
    page: int
    limit: int


@router.get("", response_model=ActivityListResponse)
def list_activity(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    actor_id: str | None = Query(None, max_length=150,
                                 description="Part of a person's email or an AI agent's name. "
                                             "Case does not matter, and it also matches who an AI acted for."),
    actor_type: ActorType | None = Query(None, description="human or ai"),
    action: str | None = Query(None, max_length=60),
    entity_type: str | None = Query(None, max_length=40),
    entity_id: int | None = Query(None, ge=1),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_audit_view),
):
    if entity_type is not None and entity_type not in _ENTITY_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"entity_type must be one of: {', '.join(_ENTITY_TYPES)}")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="from_date must not be after to_date")
    items, total = activity_service.list_activity(
        db, page=page, limit=limit, actor_id=actor_id, actor_type=actor_type, action=action,
        entity_type=entity_type, entity_id=entity_id, from_date=from_date, to_date=to_date,
    )
    return ActivityListResponse(items=items, total_count=total, page=page, limit=limit)


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[ActivityLogResponse])
def entity_history(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_audit_view),
):
    """The full story of one record, oldest first."""
    if entity_type not in _ENTITY_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"entity_type must be one of: {', '.join(_ENTITY_TYPES)}")
    return activity_service.history_for(db, entity_type, entity_id)
