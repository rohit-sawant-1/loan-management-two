"""
The `notifications` table: the app's own messages to one person (Piece 30).

**This is not the activity log, and the two never touch.** The log records
everything that happened, in the bank's own words, for someone auditing it
later. A notification is a message addressed to one person, which they read
and then it is done with. They have separate tables, separate services and
separate rules, so a change to what the bank records never quietly changes
what people are told, and the other way round.

One row is one recipient. A customer's edit request makes one row for each
member of staff, not one row with a list of names, because "read" belongs to
a person rather than to the event.

**The database keeps the audiences apart itself.** A `CHECK` rule pairs each
type with the audience it belongs to, so a staff message cannot be filed
against a customer's audience by a bug in the service. This table is brand new,
so the rule can sit inside the table definition, the same as Piece 25's
`application_edit_requests`; the pairing comes from `rules.NOTIFICATION_TYPES`
and never grows the way the settings registry does.
"""

import enum

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Enum, ForeignKey, Index, Integer, String,
)
from sqlalchemy.sql import func

from app.database import Base
from app.domain import rules


class NotificationAudience(str, enum.Enum):
    staff = "staff"
    applicant = "applicant"


class NotificationType(str, enum.Enum):
    # A customer asked to change an application they had already submitted.
    edit_requested = "edit_requested"
    # A customer uploaded a document they declared is a TEST one (Piece 32).
    test_document_uploaded = "test_document_uploaded"
    # This customer's own application moved to a new status.
    application_status_changed = "application_status_changed"


def _audience_pairing() -> str:
    """
    The SQL for "each type only with its own audience", built from the one
    list in `rules.py` rather than typed out here.
    """
    parts = []
    for audience in rules.NOTIFICATION_AUDIENCES:
        types = [t for t, a in rules.NOTIFICATION_TYPES.items() if a == audience]
        names = ", ".join(f"'{t}'" for t in types)
        parts.append(f"(audience = '{audience}' AND type IN ({names}))")
    return " OR ".join(parts)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    # Who this message is for. Always exactly one person.
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    audience = Column(Enum(NotificationAudience), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)

    # What it says. Kept short, and deliberately free of anything private:
    # no Aadhaar or PAN numbers, no account numbers, no amounts. A bell gets
    # read over somebody's shoulder on a shared screen.
    title = Column(String(120), nullable=False)
    body = Column(String(300), nullable=False)
    # Where clicking it goes, as a path inside the app, e.g. "/applications/7".
    link = Column(String(200), nullable=True)

    # What it is about, so a later piece can find every notice for one record.
    entity_type = Column(String(40), nullable=True)
    entity_id = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Null means unread. A time rather than a flag, because "when did they see
    # it?" is a question worth being able to answer.
    read_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(_audience_pairing(), name="ck_notification_audience_type"),
        CheckConstraint("length(trim(title)) > 0", name="ck_notification_title"),
        CheckConstraint("length(trim(body)) > 0", name="ck_notification_body"),
        # The bell asks "how many unread?" on every page and every 30 seconds.
        # This index answers it without reading the rows themselves.
        Index("ix_notifications_recipient_unread", "recipient_user_id", "read_at", "created_at"),
    )
