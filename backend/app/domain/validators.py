"""
The checks behind each document field (Piece 33). Plain Python, no AI.

Every check takes what the person typed and either returns the value to
store, cleaned up, or raises ValueError with a message the screen can show
next to that one field. A field marked `masked` in document_kinds.py is cut
down here, before anything is stored: the full Aadhaar number never reaches
the database (T-114).

The Verhoeff checksum is how the last digit of every Aadhaar number is
worked out from the other eleven. One wrong or swapped digit makes it fail,
which catches most typing mistakes. It proves the number is well-formed,
not that it belongs to anyone.
"""

import re
from datetime import date
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Verhoeff checksum
# ---------------------------------------------------------------------------

# The two standard Verhoeff tables: _D multiplies, _P permutes a digit by its
# position. Nothing here is ours to tune; these are the published values.
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6), (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4), (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2), (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_valid(digits: str) -> bool:
    """True when the last digit is the right Verhoeff check digit for the rest."""
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def verhoeff_check_digit(digits: str) -> str:
    """The check digit to put after `digits`. Used by the tests to build a valid number."""
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return str(_INV[c])


# ---------------------------------------------------------------------------
# One function per check name used in document_kinds.py
# ---------------------------------------------------------------------------

_NAME = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,99}$")
_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &.,'()/\-]{1,149}$")
_ADDRESS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.\-/#'()&:]{9,299}$")
_PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_MONEY = re.compile(r"^\d{1,9}(\.\d{1,2})?$")
_EARLIEST = date(2000, 1, 1)     # nothing on these documents is older than this
_MAX_MONTHLY_PAY = 10_000_000    # ₹1 crore a month: past this it is a typing mistake
_GENDERS = {"female": "Female", "male": "Male", "transgender": "Transgender"}


def _squash(value: str) -> str:
    """Trim, and turn any run of spaces or line breaks into one space."""
    return re.sub(r"\s+", " ", value).strip()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError("Enter a date as YYYY-MM-DD") from None


def check_name(value: str) -> str:
    value = _squash(value)
    if not _NAME.match(value):
        raise ValueError("Letters, spaces, dots, apostrophes and hyphens only (2 to 100 characters)")
    return value


def check_text(value: str) -> str:
    value = _squash(value)
    if not _TEXT.match(value):
        raise ValueError("2 to 150 characters: letters, numbers and & . , ' ( ) / - only")
    return value


def check_address(value: str) -> str:
    value = _squash(value)
    if not _ADDRESS.match(value):
        raise ValueError("10 to 300 characters: letters, numbers and , . - / # ' ( ) & : only")
    return value


def check_date_of_birth(value: str) -> str:
    born = _parse_date(value)
    today = date.today()
    if born > today:
        raise ValueError("A date of birth can't be in the future")
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    if not 18 <= age <= 100:
        raise ValueError("The age on the document must be between 18 and 100")
    return born.isoformat()


def check_past_date(value: str) -> str:
    when = _parse_date(value)
    if when > date.today():
        raise ValueError("This date can't be in the future")
    if when < _EARLIEST:
        raise ValueError("This date is too far in the past")
    return when.isoformat()


def check_month(value: str) -> str:
    value = value.strip()
    if not re.match(r"^\d{4}-\d{2}$", value):
        raise ValueError("Enter a month as YYYY-MM")
    try:
        first_day = date.fromisoformat(f"{value}-01")
    except ValueError:
        raise ValueError("Enter a month as YYYY-MM") from None
    if first_day > date.today() or first_day < _EARLIEST:
        raise ValueError("This month is not a plausible pay month")
    return value


def check_money(value: str) -> str:
    value = value.replace(",", "").strip()
    if not _MONEY.match(value) or float(value) <= 0:
        raise ValueError("Enter an amount in rupees, more than 0")
    if float(value) > _MAX_MONTHLY_PAY:
        raise ValueError("That amount is too large for one month's pay")
    return f"{float(value):.2f}"


def check_gender(value: str) -> str:
    stored = _GENDERS.get(value.strip().lower())
    if stored is None:
        raise ValueError("Female, Male or Transgender")
    return stored


def check_aadhaar(value: str) -> str:
    """Valid Aadhaar number → only its last 4 digits are returned, masked."""
    digits = re.sub(r"[\s\-]", "", value)
    if not re.match(r"^\d{12}$", digits):
        raise ValueError("An Aadhaar number has 12 digits")
    if digits[0] in "01":
        raise ValueError("An Aadhaar number never starts with 0 or 1")
    if not verhoeff_valid(digits):
        raise ValueError("This isn't a valid Aadhaar number. Check each digit")
    return f"XXXX XXXX {digits[-4:]}"


def check_pan(value: str) -> str:
    pan = value.strip().upper()
    if not _PAN.match(pan):
        raise ValueError("A PAN is 5 letters, 4 digits, then 1 letter, like ABCPE1234F")
    if pan[3] != "P":
        # The 4th letter says who holds the PAN; P is an individual person.
        raise ValueError("A person's PAN has P as its 4th letter")
    return pan


def check_account(value: str) -> str:
    """Valid account number → only its last 4 digits are returned, masked."""
    digits = re.sub(r"[\s\-]", "", value)
    if not re.match(r"^\d{9,18}$", digits):
        raise ValueError("An account number has 9 to 18 digits")
    return f"XXXX{digits[-4:]}"


CHECKS = {
    "name": check_name,
    "text": check_text,
    "address": check_address,
    "date_of_birth": check_date_of_birth,
    "past_date": check_past_date,
    "month": check_month,
    "money": check_money,
    "gender": check_gender,
    "aadhaar": check_aadhaar,
    "pan": check_pan,
    "account": check_account,
}


# ---------------------------------------------------------------------------
# Comparing with the profile (a warning, never a block)
# ---------------------------------------------------------------------------

def name_similarity(a: str, b: str) -> float:
    """0 to 1: how alike two names are, ignoring case, spacing and word order."""
    def norm(s: str) -> str:
        return " ".join(sorted(_squash(s).lower().replace(".", " ").split()))
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


# Below this, the name on the document is flagged as not matching the profile.
NAME_MATCH_THRESHOLD = 0.8
