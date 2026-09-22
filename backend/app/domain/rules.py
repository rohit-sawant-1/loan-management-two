"""
Every business rule of the loan system, in one place.

This file is the single source of truth for loan rules. Phase 1 validation,
the Phase 2 manual, the Phase 3 and 4 tools, and the Phase 5 agents all read
from here. Nobody types a limit or a status transition anywhere else.

Design rule: this file imports NOTHING from the rest of the app. No database,
no models, no FastAPI. Only plain Python. That keeps it importable from any
phase without pulling in the web server.

The enums in app/models use these exact string values, so a status enum
compares equal to the strings here.

Sources for the numbers are noted next to each group. "D-xx" refers to a
decision in TRAPS-AND-DECISIONS.md.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

LOAN_TYPES: tuple[str, ...] = ("personal", "home", "auto")

STATUSES: tuple[str, ...] = (
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "disbursed",
)

# Six document types. The trainer listed five; "vehicle_quotation" was added
# because the manual requires it for auto loans (D-04).
DOCUMENT_TYPES: tuple[str, ...] = (
    "id_proof",
    "income_proof",
    "bank_statement",
    "property_docs",
    "employment_letter",
    "vehicle_quotation",
)

EMPLOYMENT_STATUSES: tuple[str, ...] = ("salaried", "self_employed", "unemployed")

# Who can log in. Matches manual Section 2 (D-06, D-07).
ROLES: tuple[str, ...] = ("applicant", "loan_officer", "branch_manager", "admin")

# Roles counted as "bank staff".
#
# The admin is deliberately NOT in here (Piece 27). This set decides who gets
# the chatbot's write tools and who may run a four-agent review, so adding the
# admin would let a view-only role change loans through the chat. The admin's
# view access comes from its own guards in dependencies.py instead.
STAFF_ROLES: frozenset[str] = frozenset({"loan_officer", "branch_manager"})

# The System Administrator (Piece 27): sees the whole system, administers it,
# and has no loan-business authority.
ADMIN_ROLE: str = "admin"

# What a brand-new user gets when registering through the staff address (D-07).
DEFAULT_STAFF_ROLE: str = "loan_officer"

# ---------------------------------------------------------------------------
# The status machine
# ---------------------------------------------------------------------------
# submitted -> under_review -> approved -> disbursed
#                         \-> rejected
# Forward only. "rejected" and "disbursed" are dead ends.

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    "submitted": frozenset({"under_review"}),
    "under_review": frozenset({"approved", "rejected"}),
    "approved": frozenset({"disbursed"}),
    "rejected": frozenset(),
    "disbursed": frozenset(),
}

# Transitions only a branch manager may perform (manual Section 2, D-06).
# Stored as (from, to) pairs.
MANAGER_ONLY_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {("approved", "disbursed")}
)


def _v(x) -> str:
    """
    Accept an enum member or a plain string, give back the plain string.
    Needed because in Python 3.11, str(ApplicationStatus.submitted) is
    "ApplicationStatus.submitted", not "submitted". The tests pass enum
    members, the API passes strings; this makes both work.
    """
    return x.value if hasattr(x, "value") else str(x)


def is_valid_transition(current, new) -> bool:
    """True if an application may move from `current` to `new`."""
    return _v(new) in VALID_TRANSITIONS.get(_v(current), frozenset())


def requires_manager(current, new) -> bool:
    """True if this particular move needs the branch manager role."""
    return (_v(current), _v(new)) in MANAGER_ONLY_TRANSITIONS


# ---------------------------------------------------------------------------
# Loan amounts (rupees)
# ---------------------------------------------------------------------------
# Global bounds from the Phase 1 spec. Per-type caps from the manual and D-03.

AMOUNT_MIN: int = 10_000
AMOUNT_MAX: int = 10_000_000  # 1 crore, applies to every loan type

AMOUNT_LIMITS: dict[str, int] = {
    "personal": 2_500_000,   # 25 lakh, manual Section 5
    "home": 10_000_000,      # 1 crore, D-03 (trainer's Phase 5 said 5 crore; we chose 1)
    "auto": 5_000_000,       # 50 lakh, matches the trainer's Phase 5 figure
}


def amount_limit(loan_type) -> int:
    """Maximum amount for this loan type."""
    return AMOUNT_LIMITS[_v(loan_type)]


# ---------------------------------------------------------------------------
# Tenure (months)
# ---------------------------------------------------------------------------
# Global bounds from the Phase 1 spec. Per-type ranges from manual Section 5
# (D-02). The per-type range is the one that actually applies; the global
# bound only exists so the schema matches the trainer's spec.

TENURE_MIN: int = 6
TENURE_MAX: int = 360

TENURE_LIMITS: dict[str, tuple[int, int]] = {
    "personal": (12, 60),
    "home": (12, 360),
    "auto": (12, 84),
}


def tenure_range(loan_type) -> tuple[int, int]:
    """(minimum, maximum) months allowed for this loan type."""
    return TENURE_LIMITS[_v(loan_type)]


# ---------------------------------------------------------------------------
# Purpose (free text on the application)
# ---------------------------------------------------------------------------
# Counted after leading and trailing spaces are removed, so "   " is empty.

PURPOSE_MIN: int = 3
PURPOSE_MAX: int = 500


# ---------------------------------------------------------------------------
# Eligibility (manual Section 5)
# ---------------------------------------------------------------------------

CREDIT_SCORE_MIN: int = 300   # CIBIL scores run 300 to 900
CREDIT_SCORE_MAX: int = 900

MIN_CIBIL_SCORE: dict[str, int] = {
    "personal": 650,
    "home": 700,
    "auto": 600,
}

MIN_ANNUAL_INCOME: dict[str, int] = {
    "personal": 240_000,   # 20,000 a month
    "home": 480_000,       # 40,000 a month
    "auto": 180_000,       # 15,000 a month
}

# (minimum age, maximum age) at the time of applying.
AGE_LIMITS: dict[str, tuple[int, int]] = {
    "personal": (21, 60),
    "home": (21, 70),
    "auto": (21, 65),
}

# A home loan must be fully repaid before the borrower turns this age.
# So a 55-year-old cannot take a 30-year home loan.
HOME_LOAN_MUST_END_BEFORE_AGE: int = 70

# ---------------------------------------------------------------------------
# Affordability (D-14)
# ---------------------------------------------------------------------------
# Total monthly EMIs may not exceed this share of monthly income. Applies to
# all three loan types. Real banks use 40% to 65% depending on income; 50% is
# the most common rule. See LEARNING-NOTES.md.

EMI_MAX_SHARE_OF_INCOME: float = 0.50

# Used when estimating an EMI before the real rate is known. The Phase 5 risk
# assessor also assumes 12%.
DEFAULT_ANNUAL_INTEREST_RATE: float = 12.0

# If an applicant has not told us their existing EMIs, assume this share of
# their income already goes to other loans (the Phase 5 spec's assumption).
ASSUMED_EXISTING_OBLIGATION_SHARE: float = 0.10

# ---------------------------------------------------------------------------
# Employment (manual Section 11 FAQ, D-16)
# ---------------------------------------------------------------------------
# Minimum time in the current job or business, in years.

MIN_YEARS_WITH_EMPLOYER: dict[str, float] = {
    "salaried": 0.5,        # six months with the current employer
    "self_employed": 2.0,   # two years of business history
}

# Phase 5 treats a salaried applicant as low employment risk from this many
# years onward.
LOW_RISK_EMPLOYMENT_YEARS: float = 2.0

# ---------------------------------------------------------------------------
# Required documents (manual Section 4, D-04)
# ---------------------------------------------------------------------------

_BASE_DOCS: frozenset[str] = frozenset({"id_proof", "income_proof", "bank_statement"})

REQUIRED_DOCUMENTS: dict[str, frozenset[str]] = {
    "personal": _BASE_DOCS,
    "home": _BASE_DOCS | {"property_docs", "employment_letter"},
    "auto": _BASE_DOCS | {"vehicle_quotation"},
}


def required_documents(loan_type) -> frozenset[str]:
    """The document types this loan type must have."""
    return REQUIRED_DOCUMENTS[_v(loan_type)]


def missing_documents(loan_type: str, uploaded_types) -> list[str]:
    """
    Which required documents have not been uploaded yet.
    `uploaded_types` is any collection of document type strings.
    Returned sorted so the order is stable in tests and on screen.
    """
    uploaded = {_v(t) for t in uploaded_types}
    return sorted(required_documents(_v(loan_type)) - uploaded)


# ---------------------------------------------------------------------------
# Phase 5 risk scoring (D-10, T-13, T-14)
# ---------------------------------------------------------------------------
# The Risk Assessor starts at 100 and subtracts points. The Decision Maker
# then applies the bands below.

RISK_SCORE_START: int = 100

RISK_DEDUCTIONS: dict[str, int] = {
    "credit_high": 30,        # CIBIL below 650, or no score
    "credit_medium": 10,      # CIBIL 650 to 749
    "employment_high": 15,    # unemployed
    "employment_medium": 10,  # salaried under 2 years, or self-employed
    "emi_unaffordable": 20,   # EMI over the 50% share
}

# CIBIL bands used by the Risk Assessor.
CIBIL_LOW_RISK_FROM: int = 750    # 750 and above: low risk
CIBIL_MEDIUM_RISK_FROM: int = 650  # 650 to 749: medium risk; below 650: high

# Decision bands. Approve only when strictly above 70 (D-10). Everything
# between 40 and 70 inclusive is "ask for more information".
RISK_APPROVE_ABOVE: int = 70
RISK_REJECT_BELOW: int = 40

DECISIONS: tuple[str, ...] = ("APPROVE", "REJECT", "REQUEST_MORE_INFO")


# ---------------------------------------------------------------------------
# Editing an application after submission (Piece 25, D-28)
# ---------------------------------------------------------------------------
# The trainer's original rule was "cannot be modified after submission". The
# trainer later asked for this change. A customer now asks to edit, bank staff
# approve or refuse, and only then can the customer change the fields they
# asked for — once.

# Only while nobody has made a decision on the loan yet (A1, settled 2026-09-22).
# Once approved, the approval rests on the figures, so they cannot move.
EDITABLE_STATUSES: frozenset[str] = frozenset({"submitted", "under_review"})

# Loan type is deliberately not here: a different type is a different loan,
# with different limits and documents, so it needs a new application.
EDITABLE_FIELDS: tuple[str, ...] = ("amount_requested", "tenure_months", "purpose")

# Where a request can be in its life.
#   pending   -> waiting for staff
#   approved  -> staff said yes; the customer may now save one edit
#   refused   -> staff said no, with a note saying why
#   completed -> the customer saved the edit; editing is locked again
#   closed    -> the application's status moved on before the edit was used
EDIT_REQUEST_STATUSES: tuple[str, ...] = ("pending", "approved", "refused", "completed", "closed")

# A request that is still "live". Only one of these per application at a time.
OPEN_EDIT_REQUEST_STATUSES: frozenset[str] = frozenset({"pending", "approved"})

# Lengths, counted after trimming spaces.
EDIT_REASON_MIN: int = 10
EDIT_REASON_MAX: int = 1000
EDIT_NOTE_MIN: int = 10     # a refusal must say why
EDIT_NOTE_MAX: int = 1000   # also the cap on an optional approval note


def is_editable(status) -> bool:
    """True if an application in this status may have an edit requested or saved."""
    return _v(status) in EDITABLE_STATUSES
