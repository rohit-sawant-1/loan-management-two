"""
The System Administrator's own reads (Piece 27).

For now it's just the list of accounts. Piece 28 adds the system settings here.
"""

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain import rules
from app.models.document import Document
from app.models.stored_file import StoredFile, StoredFileNature
from app.models.user import User
from app.services import activity_service, storage

logger = structlog.get_logger()


def list_users(db: Session) -> tuple[list[User], dict[str, int]]:
    """Every login, oldest first, and how many there are of each role."""
    users = db.query(User).order_by(User.id).all()

    # Every role is present, even at zero, so the screen never has to guess
    # which keys exist. The dashboard follows the same rule.
    counts = {role: 0 for role in rules.ROLES}
    for role, count in db.query(User.role, func.count(User.id)).group_by(User.role).all():
        counts[role.value] = count
    return users, counts


def purge_test_documents(db: Session, *, user, meta: dict | None = None) -> int:
    """
    Piece 32: delete every document the server marked TEST — its encrypted
    file, its `stored_files` row, and the `documents` row pointing at it.

    `nature` can never be changed once set (the database trigger in
    `db_checks.install_stored_file_checks` refuses it), so this is the only
    way a TEST document ever leaves the system. REAL and UNDECLARED
    documents are never touched.
    """
    stored_files = db.query(StoredFile).filter(StoredFile.nature == StoredFileNature.test).all()
    count = len(stored_files)

    for stored in stored_files:
        db.query(Document).filter(Document.file_id == stored.id).delete()
        storage.delete(stored.storage_zone.value, stored.stored_name)
        db.delete(stored)

    activity_service.record(
        db, action="test_documents_purged", actor_id=user.email, actor_role=user.role.value,
        entity_type="stored_file", details={"count": count},
        **(meta or {}),
    )
    db.commit()
    logger.info("test_documents_purged", count=count, purged_by=user.email)
    return count
