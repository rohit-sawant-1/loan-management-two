"""
Schemas for the in-app notifications (Piece 30).
"""

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationAudience, NotificationType
from app.schemas.common import UtcDateTime


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    audience: NotificationAudience
    type: NotificationType
    title: str
    body: str
    link: str | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    created_at: UtcDateTime | None = None
    # Null means unread. The bell draws a dot against those.
    read_at: UtcDateTime | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    # Sent with the list so opening the panel does not need a second request.
    unread_count: int


class UnreadCountResponse(BaseModel):
    count: int
