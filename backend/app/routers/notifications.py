"""
The bell's addresses (Piece 30). Mounted at /api/v1/notifications by main.py.

Any signed-in person, and **always only their own**. There is no address here
that reads anybody else's, for any role: not staff, not the manager, not the
administrator. The service filters every query by the caller's own id, which is
why `get_current_user` is the right guard even on the two that write (T-117 is
about actions on *other people's* records; marking your own message as read is
not one).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse, NotificationResponse, UnreadCountResponse,
)
from app.services import notification_service

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=50),
    before_id: int | None = Query(None, ge=1, description="Walk back through older ones"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The caller's own notifications, newest first."""
    items = notification_service.list_for(
        db, user, unread_only=unread_only, limit=limit, before_id=before_id
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        unread_count=notification_service.unread_count(db, user),
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def count_unread(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Just the number on the bell. Small on purpose: the browser asks often."""
    return UnreadCountResponse(count=notification_service.unread_count(db, user))


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_one_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not notification_service.mark_read(db, user, notification_id):
        # 404 rather than 403 on somebody else's: a "forbidden" would confirm
        # the id exists and let someone map out other people's notices.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    notification_service.mark_all_read(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
