"""
The app's own notifications (Piece 30).

**Separate from the activity log on purpose.** Nothing in this file reads or
writes the log, and nothing in `activity_service` knows this exists. The log is
the bank's record of what happened; this is a message to one person, which they
read and dismiss. Keeping them apart means a change to one cannot quietly
change the other — and it is why the tests check that the log's row count is
identical whether notifications are created or not.

**Nothing here commits.** Each function adds rows and leaves them in the
caller's transaction, so the event and the notices about it are saved together
or not at all. A notification about an edit request that was never saved would
be worse than no notification.

**Three triggers, and no others** (settled 2026-09-22): a customer asking to
edit a submitted application, a customer uploading a TEST document, and a
customer's own application changing status. Not setting changes, not ordinary
uploads, not verifications, not logins.
"""

from datetime import datetime, timezone

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain import rules
from app.models.application import LoanApplication
from app.models.notification import Notification, NotificationAudience, NotificationType
from app.models.user import User

logger = structlog.get_logger()

# How a status reads in a message: "under_review" becomes "Under review".
def _status_words(status) -> str:
    value = status.value if hasattr(status, "value") else str(status)
    return value.replace("_", " ").capitalize()


def _staff_recipients(db: Session) -> list[User]:
    """
    Every member of bank staff with a working login.

    `rules.STAFF_ROLES` is loan officers and branch managers, and deliberately
    not the administrator (Piece 27): the administrator oversees the system and
    has no loan work to do, so a queue of edit requests is not its business.
    A switched-off account gets nothing, because nobody is reading it.
    """
    return (
        db.query(User)
        .filter(User.role.in_(list(rules.STAFF_ROLES)), User.is_active.is_(True))
        .all()
    )


def _add(db: Session, *, recipient_id: int, audience: NotificationAudience,
         type_: NotificationType, title: str, body: str, link: str | None,
         entity_type: str | None = None, entity_id: int | None = None) -> Notification:
    row = Notification(
        recipient_user_id=recipient_id, audience=audience, type=type_,
        title=title, body=body, link=link,
        entity_type=entity_type, entity_id=entity_id,
    )
    db.add(row)
    return row


# ---------------------------------------------------------------------------
# The three triggers
# ---------------------------------------------------------------------------

def notify_staff_edit_requested(db: Session, edit_request) -> list[Notification]:
    """Trigger 1: a customer wants to change an application they already sent in."""
    who = edit_request.applicant_name or "A customer"
    rows = [
        _add(
            db, recipient_id=staff.id,
            audience=NotificationAudience.staff,
            type_=NotificationType.edit_requested,
            title="Edit request",
            body=f"{who} asked to change application {edit_request.application_id}.",
            link="/edit-requests",
            entity_type="edit_request", entity_id=edit_request.id,
        )
        for staff in _staff_recipients(db)
    ]
    logger.info("notifications_created", trigger="edit_requested",
                recipients=len(rows), application_id=edit_request.application_id)
    return rows


def notify_staff_test_document(db: Session, document, *, applicant_name: str | None = None) -> list[Notification]:
    """
    Trigger 2: a customer uploaded a document they declared is a TEST one.

    Built and tested here; Piece 32 is what calls it, once a document can be
    marked TEST at all.
    """
    who = applicant_name or "A customer"
    doc_type = str(getattr(document.doc_type, "value", document.doc_type)).replace("_", " ")
    rows = [
        _add(
            db, recipient_id=staff.id,
            audience=NotificationAudience.staff,
            type_=NotificationType.test_document_uploaded,
            title="TEST document uploaded",
            body=f"{who} uploaded a TEST {doc_type} on application {document.application_id}.",
            link=f"/applications/{document.application_id}",
            entity_type="document", entity_id=document.id,
        )
        for staff in _staff_recipients(db)
    ]
    logger.info("notifications_created", trigger="test_document_uploaded",
                recipients=len(rows), application_id=document.application_id)
    return rows


def notify_applicant_status(db: Session, application: LoanApplication,
                            old_status, new_status) -> list[Notification]:
    """
    Trigger 3: this customer's own application moved.

    Submitting counts as a status change, so the first message a customer gets
    is that their application is in (D9 in the piece's plan). A profile created
    by staff may have no login attached to it, and then there is nobody to tell.
    """
    applicant = application.applicant
    user_id = applicant.user_id if applicant else None
    if user_id is None:
        return []

    words = _status_words(new_status)
    if old_status is None:
        title = "Application submitted"
        body = f"Application {application.id} has been submitted."
    else:
        title = "Application updated"
        body = f"Application {application.id} is now {words}."

    row = _add(
        db, recipient_id=user_id,
        audience=NotificationAudience.applicant,
        type_=NotificationType.application_status_changed,
        title=title, body=body,
        link=f"/applications/{application.id}",
        entity_type="application", entity_id=application.id,
    )
    logger.info("notifications_created", trigger="application_status_changed",
                recipients=1, application_id=application.id, new_status=words)
    return [row]


# ---------------------------------------------------------------------------
# Reading them — always, and only, the caller's own
# ---------------------------------------------------------------------------

def list_for(db: Session, user: User, *, unread_only: bool = False,
             limit: int = 20, before_id: int | None = None) -> list[Notification]:
    """Newest first. `before_id` walks back through older ones."""
    query = db.query(Notification).filter(Notification.recipient_user_id == user.id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    if before_id is not None:
        query = query.filter(Notification.id < before_id)
    return query.order_by(Notification.id.desc()).limit(limit).all()


def unread_count(db: Session, user: User) -> int:
    """The number on the bell. Asked for often, so it counts rather than loads."""
    return (
        db.query(func.count(Notification.id))
        .filter(Notification.recipient_user_id == user.id, Notification.read_at.is_(None))
        .scalar()
    ) or 0


def mark_read(db: Session, user: User, notification_id: int) -> bool:
    """
    Mark one as read. False if it is not this person's, which the address turns
    into a 404 rather than a 403: a "forbidden" would confirm that the id
    exists and let someone map out other people's notices.
    """
    row = (
        db.query(Notification)
        .filter(Notification.id == notification_id,
                Notification.recipient_user_id == user.id)
        .first()
    )
    if row is None:
        return False
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
    db.commit()
    return True


def mark_all_read(db: Session, user: User) -> int:
    """Clear the badge. Returns how many were still unread."""
    changed = (
        db.query(Notification)
        .filter(Notification.recipient_user_id == user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: datetime.now(timezone.utc)}, synchronize_session=False)
    )
    db.commit()
    return changed
