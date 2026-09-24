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
    # Piece 31: new, optional, and deliberately NOT in REQUIRED_DOCUMENTS
    # below, so no loan type suddenly needs one more document than before —
    # nothing about what a customer must submit changes.
    "photograph",
    "signature",
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


def required_documents(loan_type, employment_status=None) -> frozenset[str]:
    """
    The document types this loan type must have.

    D-32: the manual (from the trainer's spec) asks for an employment letter
    on a home loan "for salaried applicants" only, since a self-employed
    person has no employer to write one. So it's dropped when the applicant's
    status is known and isn't salaried. An unknown status (None) keeps it,
    which is exactly how this worked before, so every caller that doesn't
    know the status, including the trainer's own tests, is unchanged.
    """
    required = REQUIRED_DOCUMENTS[_v(loan_type)]
    if employment_status is not None and _v(employment_status) != "salaried":
        required = required - {"employment_letter"}
    return required


def missing_documents(loan_type: str, uploaded_types, employment_status=None) -> list[str]:
    """
    Which required documents have not been uploaded yet.
    `uploaded_types` is any collection of document type strings.
    Returned sorted so the order is stable in tests and on screen.
    `employment_status`: see `required_documents` (D-32).
    """
    uploaded = {_v(t) for t in uploaded_types}
    return sorted(required_documents(_v(loan_type), employment_status) - uploaded)


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


# ---------------------------------------------------------------------------
# System settings the administrator can change (Piece 28)
# ---------------------------------------------------------------------------
# One entry per setting. This is the only list of them: the database check, the
# service, the API and the admin screen all read it, so adding a setting later
# means adding one line here and nothing else.
#
# `default` is what the app uses when nothing has been stored yet, so a fresh
# database behaves exactly as it did before this piece existed.
SETTINGS: dict[str, dict] = {
    "real_uploads_enabled": {
        "type": "bool",
        "default": False,
        "label": "Real document uploads",
        # What each position means, in the words the admin screen shows.
        "off_text": "Documents are recorded by their file name, exactly as they are now.",
        "on_text": "Customers upload the actual file. Each one is checked, rebuilt and stored encrypted, and staff can open it.",
    },
}

SETTING_KEYS: tuple[str, ...] = tuple(SETTINGS)


def setting_default(key: str):
    """What a setting is worth before anyone has changed it."""
    return SETTINGS[key]["default"]


# ---------------------------------------------------------------------------
# In-app notifications (Piece 30)
# ---------------------------------------------------------------------------
# A system entirely separate from the activity log. The log records everything
# that happened, for an auditor; a notification is a message to one person.
#
# Only three things ever produce one, settled 2026-09-22. Nothing else does:
# not setting changes, not ordinary uploads, not verifications, not logins.
NOTIFICATION_AUDIENCES: tuple[str, ...] = ("staff", "applicant")

# Which audience each kind of notification belongs to. The database enforces
# this pairing itself, so a staff message can never be filed against a
# customer's audience by mistake.
NOTIFICATION_TYPES: dict[str, str] = {
    "edit_requested": "staff",
    "test_document_uploaded": "staff",
    "application_status_changed": "applicant",
}

# The app's own notifications only: no email, no SMS, no push (settled).


# ---------------------------------------------------------------------------
# Real document uploads (Piece 31)
# ---------------------------------------------------------------------------
# Everything a document has to pass before it is stored, and what it is
# rebuilt into. Numbers are researched defaults (IBPS, NSDL PAN, UPSC, SSC,
# DigiLocker), collected once here so file_service.py never has a number
# typed twice.

# The universal cap while reading, before anything else runs.
MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024   # 5 MB

# Where a stored file can end up. "safe" is tracked by git; "sensitive"
# never is. See TRAPS-AND-DECISIONS.md, "Piece 31 — two upload folders".
STORAGE_ZONES: tuple[str, ...] = ("safe", "sensitive")

# How a stored file is classified. Set by the server, never by the person
# uploading — see the same note above for why.
STORED_FILE_NATURES: tuple[str, ...] = ("test", "real", "undeclared")

# Piece 33: the details typed in for a document. The kinds and their fields
# live in app/domain/document_kinds.py; these are the states around them.
EXTRACTION_STATUSES: tuple[str, ...] = ("needs_input", "confirmed", "discarded")
# How far a document's details have been checked. "Consistency checked" means
# the format checks passed (a valid Aadhaar checksum, say). It never means the
# document is genuine: identification is not authenticity (settled 2026-09-22).
VERIFICATION_LEVELS: tuple[str, ...] = (
    "not_verified", "consistency_checked", "cryptographically_verified", "staff_verified",
)
EXTRACTED_FIELD_STATES: tuple[str, ...] = (
    "extracted", "uncertain", "missing", "user_entered", "user_corrected",
)
# Where a value came from. Only "user" exists until Piece 34 reads documents.
EXTRACTED_FIELD_SOURCES: tuple[str, ...] = ("qr", "mrz", "text_layer", "ocr", "gemini", "user")

# The two content types the rebuild step can ever produce. A PDF stays a
# PDF; every image, whatever it arrived as, becomes a JPEG.
REBUILT_CONTENT_TYPES: frozenset[str] = frozenset({"application/pdf", "image/jpeg"})

# What Pillow decodes before it refuses on grounds of a "decompression
# bomb" — an image that claims to be far larger than any real scan or photo.
MAX_IMAGE_PIXELS: int = 50_000_000   # 50 megapixels

# A rebuilt page or photo whose pixels barely vary at all is almost
# certainly a blank scan, not a real one. Measured as the standard
# deviation of greyscale pixel values (0-255); a genuine document is never
# this flat. A plain heuristic, not a proof — worth revisiting if it ever
# refuses a real thin document.
BLANK_PAGE_STD_DEV_THRESHOLD: float = 3.0

# The PDF markers the trainer's own security guidance and common CDR
# practice both flag: anything that can run code, reach outside the file,
# or carry a payload of its own. Any match refuses the file outright.
PDF_DANGER_MARKERS: tuple[bytes, ...] = (
    b"/JavaScript", b"/JS", b"/OpenAction", b"/AA", b"/Launch",
    b"/EmbeddedFile", b"/RichMedia", b"/XFA", b"/SubmitForm", b"/GoToR",
)

# Words that mark a document as demonstration material, checked against a
# PDF's own, original text layer — read before the rebuild step redraws
# every page as a picture and destroys that layer. Case-insensitive; kept
# lower-case here so the check is a plain "in" test.
SPECIMEN_WATERMARK_PHRASES: tuple[str, ...] = (
    "specimen", "sample", "test document", "demo", "dummy",
    "for demonstration only", "not for real use",
)

# 30 uploads an hour, 100 MB total, per customer. Generous for a real
# applicant, tight enough to stop a script from filling the disk.
UPLOAD_RATE_LIMIT_PER_HOUR: int = 30
UPLOAD_RATE_LIMIT_BYTES_PER_CUSTOMER: int = 100 * 1024 * 1024

# Per-document-type standards. The server rebuilds every upload to match
# its type's row, and refuses it with a plain reason if it cannot.
# `accepted` is what the client may send; `produces` is what the rebuild
# step is allowed to turn it into (a PDF stays a PDF; an image becomes a
# JPEG, whatever it arrived as). `exact_pixels` overrides the generic
# long/short-side resize for the two fixed-format types.
UPLOAD_STANDARDS: dict[str, dict] = {
    "photograph": {
        "accepted": frozenset({"image/jpeg", "image/png"}),
        "produces": frozenset({"image/jpeg"}),
        "exact_pixels": (200, 230),     # IBPS, centre-cropped; original must be at least this
        "min_bytes": 20_000, "max_bytes": 50_000,
        "min_pages": None, "max_pages": None,
    },
    "signature": {
        "accepted": frozenset({"image/jpeg", "image/png"}),
        "produces": frozenset({"image/jpeg"}),
        "exact_pixels": (140, 60),      # IBPS
        "min_bytes": 10_000, "max_bytes": 20_000,
        "min_pages": None, "max_pages": None,
    },
    "id_proof": {
        "accepted": frozenset({"application/pdf", "image/jpeg", "image/png"}),
        "produces": frozenset({"application/pdf", "image/jpeg"}),
        "image_long_side": 1600, "image_short_side": 800, "pdf_dpi": 150,
        # An image and a PDF are held to different caps here: an image's
        # whole file must sit in this range, while a PDF is judged per page
        # instead (a ten-page id proof is unusual but not automatically too
        # big for one whole-file number to cover fairly).
        "min_bytes": 30_000, "max_bytes": 300_000,
        "max_bytes_per_pdf_page": 300_000,
        "min_pages": 1, "max_pages": 4,
    },
    "income_proof": {
        "accepted": frozenset({"application/pdf", "image/jpeg", "image/png"}),
        "produces": frozenset({"application/pdf", "image/jpeg"}),
        "image_long_side": 1600, "image_short_side": 800, "pdf_dpi": 150,
        "min_bytes": None, "max_bytes": 2_000_000,
        "min_pages": 1, "max_pages": 20,
    },
    "bank_statement": {
        "accepted": frozenset({"application/pdf"}),   # PDF only
        "produces": frozenset({"application/pdf"}),
        "image_long_side": None, "image_short_side": None, "pdf_dpi": 150,
        "min_bytes": None, "max_bytes": 3_000_000,
        "min_pages": 1, "max_pages": 30,
    },
    "property_docs": {
        "accepted": frozenset({"application/pdf", "image/jpeg", "image/png"}),
        "produces": frozenset({"application/pdf", "image/jpeg"}),
        "image_long_side": 1600, "image_short_side": 800, "pdf_dpi": 150,
        "min_bytes": None, "max_bytes": 3_000_000,
        "min_pages": 1, "max_pages": 30,
    },
    "employment_letter": {
        "accepted": frozenset({"application/pdf", "image/jpeg", "image/png"}),
        "produces": frozenset({"application/pdf", "image/jpeg"}),
        "image_long_side": 1600, "image_short_side": 800, "pdf_dpi": 150,
        "min_bytes": None, "max_bytes": 1_000_000,
        "min_pages": 1, "max_pages": 5,
    },
    "vehicle_quotation": {
        "accepted": frozenset({"application/pdf", "image/jpeg", "image/png"}),
        "produces": frozenset({"application/pdf", "image/jpeg"}),
        "image_long_side": 1600, "image_short_side": 800, "pdf_dpi": 150,
        "min_bytes": None, "max_bytes": 1_000_000,
        "min_pages": 1, "max_pages": 5,
    },
}


def upload_standard(doc_type: str) -> dict:
    """The rebuild standard for this document type, or KeyError if it has none."""
    return UPLOAD_STANDARDS[_v(doc_type)]
