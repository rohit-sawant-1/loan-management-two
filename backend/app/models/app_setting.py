"""
The `app_settings` table: settings the administrator can change while the app
is running (Piece 28).

One row is one setting. The key is the row's own primary key, and the value is
stored as JSON text so a setting can be a yes/no today and a number or a list
later without changing the table.

**Why not `.env`?** A `.env` value belongs to one machine and only changes when
the server is restarted. A setting the admin flips in the browser has to reach
everyone immediately, so it belongs in the database with the rest of the data.

**Why the key check is a trigger, not a CHECK rule inside the table.** The
other new table (Piece 25's `application_edit_requests`) puts its rules in the
table definition, which is the simpler thing when the allowed values never
change. This list grows: Piece 31 and later add settings. A CHECK rule is baked
in when the table is created, so a database made today would refuse a setting
added next week, and SQLite cannot alter a CHECK without rebuilding the whole
table. The trigger is rebuilt from `rules.SETTINGS` on every startup, so it is
always today's list. See `app/db_checks.py`.
"""

from sqlalchemy import Column, DateTime, String, Text, event
from sqlalchemy.sql import func

from app.database import Base
from app.db_checks import install_app_setting_checks


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(64), primary_key=True)
    # JSON, so `false` is stored as the text "false" and read back as a bool.
    value = Column(Text, nullable=False)
    # Who changed it last, and when. The admin screen shows both.
    updated_by = Column(String(150), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Whenever this table is freshly created — a new database, or every test run —
# add the key check straight away. An existing database gets it from
# `init_db()` instead. The same pattern as `loan_applications` (Piece 25).
@event.listens_for(AppSetting.__table__, "after_create")
def _add_database_checks(target, connection, **kw):
    install_app_setting_checks(connection)
