"""
The `stored_files` table: what a real uploaded document actually is, once
it has passed through the pipeline in `file_service.py` (Piece 31).

One row is one file. `documents.file_id` points here when a document has a
real file behind it; a name-only document (the trainer's original route)
simply has no `file_id`, and this table has no row for it.

**Two facts about a row, once it exists, never change again:** `nature`
(is this confidently demo material?) and `storage_zone` (which of the two
folders it actually lives in). Both are set once, at upload time, by the
server — never by whoever uploaded it — and a database trigger refuses any
`UPDATE` that tries to move either one. A different answer means a fresh
upload, not an edit. Because this table is brand new, its ordinary validity
rules (is `nature` even one of the allowed values?) sit inside the table
definition as plain `CheckConstraint`s, the same as Piece 25's
`application_edit_requests`. The immutability rule is different: SQLite's
inline `CHECK` can only look at a row's own new values, never compare them
to what the row used to say, so that one has to be a trigger — see
`app/db_checks.py`'s `install_stored_file_checks`.
"""

import enum

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Enum, ForeignKey, Integer, String, event,
)
from sqlalchemy.sql import func

from app.database import Base
from app.db_checks import install_stored_file_checks, quoted_list
from app.domain import rules


class StoredFileNature(str, enum.Enum):
    test = "test"
    real = "real"
    undeclared = "undeclared"


class StorageZone(str, enum.Enum):
    safe = "safe"
    sensitive = "sensitive"


class StoredFile(Base):
    __tablename__ = "stored_files"

    id = Column(Integer, primary_key=True, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id"), nullable=True)

    # The random name the bytes are actually saved under (a UUID plus
    # extension) — never the name the person's browser sent, and never
    # shown to them either. `display_name` is what the screen shows.
    stored_name = Column(String(80), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)

    # What the REBUILT file is, not what was uploaded — a PDF stays a PDF,
    # every image becomes a JPEG.
    content_type = Column(String(40), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    original_size_bytes = Column(Integer, nullable=False)
    pages = Column(Integer, nullable=True)     # PDFs only
    width = Column(Integer, nullable=True)     # images only
    height = Column(Integer, nullable=True)

    # Of the ORIGINAL bytes, not the rebuilt ones — see file_service.sha256_of.
    sha256 = Column(String(64), nullable=False, index=True)

    nature = Column(Enum(StoredFileNature), nullable=False)
    storage_zone = Column(Enum(StorageZone), nullable=False)

    # When the uploader ticked the one consent checkbox. Always set — the
    # form requires it before any upload, whatever the file turns out to be.
    consent_at = Column(DateTime(timezone=True), nullable=False)

    uploaded_by = Column(String(150), nullable=False)   # email
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        CheckConstraint(
            f"nature IN ({quoted_list(rules.STORED_FILE_NATURES)})",
            name="ck_stored_file_nature",
        ),
        CheckConstraint(
            f"storage_zone IN ({quoted_list(rules.STORAGE_ZONES)})",
            name="ck_stored_file_storage_zone",
        ),
        CheckConstraint(
            f"content_type IN ({quoted_list(rules.REBUILT_CONTENT_TYPES)})",
            name="ck_stored_file_content_type",
        ),
        CheckConstraint("size_bytes > 0 AND original_size_bytes > 0", name="ck_stored_file_sizes"),
    )


# Whenever this table is freshly created — a new database, or every test
# run — add the immutability trigger straight away. An existing database
# gets it from `init_db()` instead. Same pattern as `loan_applications`
# (Piece 25) and `app_settings` (Piece 28).
@event.listens_for(StoredFile.__table__, "after_create")
def _add_database_checks(target, connection, **kw):
    install_stored_file_checks(connection)
