"""
Small checks shared by several schemas, so each rule is written once.
"""

import re
from datetime import date, datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer

# Letters, spaces, dots, apostrophes and hyphens. Covers "Priya Sharma",
# "A.C. Harish", "O'Brien". Must start with a letter.
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,99}$")

# Indian mobile: ten digits, first digit 6 to 9.
_PHONE_PATTERN = re.compile(r"^[6-9]\d{9}$")


# ---------------------------------------------------------------------------
# Sending times to the browser
# ---------------------------------------------------------------------------
# SQLite has no real timezone support: it records what CURRENT_TIMESTAMP gives,
# which is UTC, and hands it back as a plain date and time with nothing saying
# so. If we pass that straight out, a browser sees "2026-09-05T20:13:55" and
# assumes it is the reader's own local time. In India that shows every date and
# time 5 hours 30 minutes early — the wrong day, in the evening instead of the
# small hours.
#
# The fix is to say out loud that the value is UTC by ending it with "Z". The
# browser then converts it to whatever local time the reader is actually in,
# which is also what makes the app correct for someone in another country.


def _as_utc_iso(value: datetime) -> str:
    """Stamp a naive database time as UTC and write it in the standard format."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Use this instead of `datetime` on every field a response sends out.
UtcDateTime = Annotated[datetime, PlainSerializer(_as_utc_iso, return_type=str, when_used="json")]


def check_name(value: str) -> str:
    value = value.strip()
    if not _NAME_PATTERN.match(value):
        raise ValueError(
            "name must be 2 to 100 characters: letters, spaces, dots, apostrophes or hyphens"
        )
    return value


def check_phone(value: str) -> str:
    value = value.strip()
    if not _PHONE_PATTERN.match(value):
        raise ValueError("phone must be a 10-digit Indian mobile number starting with 6 to 9")
    return value


def check_password(value: str) -> str:
    # 72 is bcrypt's hard limit; anything longer is silently cut, which is worse
    # than refusing it.
    if not 8 <= len(value) <= 72:
        raise ValueError("password must be 8 to 72 characters")
    if not any(c.isupper() for c in value):
        raise ValueError("password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in value):
        raise ValueError("password must contain at least one digit")
    return value


# Invisible control characters (things like a bell or a null byte) that no
# keyboard types on purpose. Newlines and tabs are allowed, because a reason
# written in a text box can have line breaks.
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_free_text(value: str, min_len: int, max_len: int, what: str) -> str:
    """
    The one check for any box where a person writes in their own words:
    purpose, an edit reason, a staff note.

    Trims leading and trailing spaces first, then counts. Without the trim,
    "   " would pass a three-character minimum while saying nothing at all.
    """
    value = value.strip()
    if _CONTROL_CHARACTERS.search(value):
        raise ValueError(f"{what} contains characters that cannot be typed")
    if not min_len <= len(value) <= max_len:
        raise ValueError(f"{what} must be {min_len} to {max_len} characters")
    return value


# Manual Section 12: documents must be PDF, JPG or PNG.
_ALLOWED_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png")


def check_file_name(value: str) -> str:
    value = value.strip()
    if not value.lower().endswith(_ALLOWED_EXTENSIONS):
        raise ValueError("file_name must end in .pdf, .jpg, .jpeg or .png")
    # Guard against path tricks like "../../etc/passwd".
    if "/" in value or "\\" in value:
        raise ValueError("file_name must not contain folder separators")
    return value


# A real upload's display name (Piece 31): letters, digits, space, and a
# small set of punctuation a filename plausibly has. Unlike check_file_name
# above, this never trusts the extension to say what the file really is —
# file_service.detect_type reads that from the bytes instead — so this is
# purely about what is safe to store and show on screen, not what kind of
# file it claims to be.
_DISPLAY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 ._\-()]{1,100}$")


def clean_display_name(value: str) -> str:
    value = value.strip()
    if not value:
        return "document"   # a browser can send an empty filename; never store nothing
    if not _DISPLAY_NAME_PATTERN.match(value):
        raise ValueError(
            "file names may only contain letters, digits, spaces and . _ - ( ), up to 100 characters"
        )
    return value


def check_date_of_birth(value: date | None) -> date | None:
    if value is None:
        return None
    today = date.today()
    if value > today:
        raise ValueError("date_of_birth cannot be in the future")
    if value.year < 1900:
        raise ValueError("date_of_birth is not plausible")
    return value
