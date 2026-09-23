"""
The database connection.

Three things live here, and the tests import two of them by name:
  - `Base`: the parent class every table model inherits from
  - `get_db`: hands a database session to each request, then closes it
  - `init_db`: creates the tables on first start
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# `check_same_thread=False` is required for SQLite when a web server handles
# several requests at once. Without it SQLite refuses connections from any
# thread other than the one that opened the file.
#
# We deliberately do NOT turn on SQLite's foreign-key checking. Two of the
# trainer's tests insert rows that point at an applicant who does not exist,
# and would fail if SQLite enforced the link. See TRAPS-AND-DECISIONS T-03.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

# A "session" is one conversation with the database. Each request gets its own.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Every model class inherits from this so SQLAlchemy knows it is a table.
Base = declarative_base()


def get_db():
    """
    Give the request a session, and always close it afterwards, even if the
    request failed. FastAPI calls this for every endpoint that asks for a db.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any tables that do not exist yet. Safe to call every startup."""
    # Importing the models package registers every table with Base.
    from app import models  # noqa: F401  (imported for its side effect)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    _drop_baked_in_timestamps()
    _install_database_checks()


def _add_missing_columns() -> None:
    """
    `create_all` only creates tables that do not exist yet — it never adds a
    column to a table that is already there. `loan_app.db` and `test.db` were
    both created before Piece 19 added three columns to `loan_applications`,
    so without this they would silently keep the old shape and every read of
    the new columns would raise "no such column". SQLite's `ALTER TABLE ...
    ADD COLUMN` is safe to run more than once because we check first.
    """
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(loan_applications)"))}
        new_columns = {
            "eligibility_passed": "BOOLEAN",
            "eligibility_summary": "TEXT",
            "eligibility_checked_at": "DATETIME",
        }
        for name, sql_type in new_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE loan_applications ADD COLUMN {name} {sql_type}"))

        # Piece 31: a document created after a real file exists points at
        # its stored_files row; a name-only document (the trainer's
        # original route) simply has no file_id. Only meaningful once
        # stored_files exists too, which create_all has already made by
        # the time this runs.
        existing_doc_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(documents)"))}
        if "file_id" not in existing_doc_cols:
            conn.execute(text("ALTER TABLE documents ADD COLUMN file_id INTEGER"))
        conn.commit()


def _drop_baked_in_timestamps() -> None:
    """
    A one-time repair of rows written before the timezone fix.

    `build_summary_text` used to open the stored assessment with a line reading
    "Eligibility assessed at submission on ... UTC." The same instant is also
    stored properly in `eligibility_checked_at`, which the browser renders in
    the reader's own timezone — so the application card showed one event at two
    times five and a half hours apart. The text no longer writes that line, but
    every application submitted before today still has it stored, and a stored
    string does not fix itself when the code that wrote it changes.

    So: strip that first line, and only that first line, from rows that have it.
    A plain string operation with a `LIKE` guard, not a rewrite of the
    assessment — the rest of the text is the bank's permanent record of what its
    rules said and must not be touched. Does nothing on a database that has none
    (a fresh one, or a second startup), so it is safe on every boot.
    """
    with engine.connect() as conn:
        conn.execute(text(
            """
            UPDATE loan_applications
               SET eligibility_summary =
                   substr(eligibility_summary,
                          instr(eligibility_summary, ' UTC.') + 7)
             WHERE eligibility_summary LIKE 'Eligibility assessed at submission on % UTC.%'
            """
        ))
        conn.commit()


def _install_database_checks() -> None:
    """
    Piece 25: give `loan_applications` the database's own checks, even when
    the table was created long before this piece existed.

    A brand-new table gets them the moment it is created (see the listener at
    the bottom of `app/models/application.py`), but `loan_app.db` already has
    this table, so `create_all` skips it and the listener never fires. This
    covers that case. The triggers are rebuilt on every startup, so they always
    carry today's numbers from `rules.py`. See `app/db_checks.py`.
    """
    from app.db_checks import (
        install_app_setting_checks, install_loan_application_checks, install_stored_file_checks,
    )

    with engine.begin() as conn:
        install_loan_application_checks(conn)
        # Piece 28: only a setting the app knows about may be stored.
        install_app_setting_checks(conn)
        # Piece 31: nature and storage_zone can never be changed once set.
        install_stored_file_checks(conn)
