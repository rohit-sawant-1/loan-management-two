"""
The logic behind a document's details (Piece 33).

A document with a real file, of a type that has kinds, gets an "extraction":
which kind it is (Aadhaar, PAN…) and one row per field of that kind. The
uploader types the values in, fixes anything the checks refuse, and confirms.
Only then does the document count towards the checklist.

Nothing here changes the customer's profile. A name or date of birth that
doesn't match the profile is noted beside the field as a warning; changing
the profile is Piece 24's job, with staff approval (settled 2026-09-22).
"""

from datetime import date, datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.domain import document_kinds, validators
from app.models.application import LoanApplication
from app.models.document import Document
from app.models.extraction import DocumentExtraction, ExtractedField
from app.models.user import User, UserRole
from app.services import activity_service
from app.services.errors import FieldProblems, NotFound, RuleViolation

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Creating
# ---------------------------------------------------------------------------

def check_kind_fits(kind: str, doc_type: str) -> document_kinds.DocumentKind:
    """The kind, if it really sits inside this document type. Raises otherwise."""
    found = document_kinds.get_kind(kind)
    if found is None or found.doc_type != doc_type:
        raise RuleViolation(f"'{kind}' is not a kind of {doc_type.replace('_', ' ')}")
    return found


def create_extraction(
    db: Session, document: Document, kind: str, *, user: User, reading=None,
) -> DocumentExtraction:
    """
    A fresh set of details for a document. Every field starts as "missing",
    unless `reading` (Piece 34) found it in the file's own text, in which
    case it starts filled in, as "extracted" or, if it failed its check,
    "uncertain". Doesn't commit, so an upload can create the document and
    its details in one commit (Piece 33, decision 4).
    """
    doc_type = getattr(document.doc_type, "value", document.doc_type)
    found = check_kind_fits(kind, doc_type)
    extraction = DocumentExtraction(
        document_id=document.id, application_id=document.application_id,
        declared_kind=found.key, status="needs_input", created_by=user.email,
    )
    rows = []
    for f in found.fields:
        read = reading.fields.get(f.key) if reading else None
        if read is None:
            rows.append(ExtractedField(field_key=f.key, state="missing"))
            continue
        rows.append(ExtractedField(
            field_key=f.key, value=read.value,
            # What the machine read is kept, so typing over it later is
            # recorded as a correction rather than a first entry.
            machine_value=read.value,
            source="text_layer" if read.value else None,
            confidence=read.confidence, state=read.state, check_note=read.note,
        ))
    extraction.fields = rows
    if reading is not None:
        extraction.detected_kind = reading.detected_kind
        extraction.detection_score = reading.detection_score
    db.add(extraction)
    db.flush()
    _profile_notes(db, extraction)
    return extraction


def start_for_document(
    db: Session, application_id: int, document_id: int, kind: str,
    *, user: User, meta: dict | None = None,
) -> DocumentExtraction:
    """
    The fallback path: an upload that has no details yet (uploaded before
    Piece 33, or the wrong kind was picked and then discarded).
    """
    from app.services.document_service import _application_for   # avoids a circular import

    application = _application_for(db, application_id, user)
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.application_id == application.id)
        .first()
    )
    if document is None:
        raise NotFound(f"Document {document_id} not found on application {application_id}")
    if document.replaced_by_id is not None:
        raise RuleViolation("This copy has been replaced. Fill in the newer copy's details instead")
    if document.file_id is None:
        raise RuleViolation("A document recorded by name only has no details to fill in")
    if document.current_extraction is not None:
        raise RuleViolation("This document already has its details started")

    extraction = create_extraction(db, document, kind, user=user)
    db.commit()
    return get_extraction(db, extraction.id, viewer=user)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def get_extraction(db: Session, extraction_id: int, *, viewer: User) -> DocumentExtraction:
    """
    Staff and the admin may see any; a customer only their own. Another
    customer's is "not found" rather than "forbidden", so its existence
    isn't given away.
    """
    extraction = db.query(DocumentExtraction).filter(DocumentExtraction.id == extraction_id).first()
    if extraction is None:
        raise NotFound(f"Details {extraction_id} not found")
    if viewer.role == UserRole.applicant:
        application = db.query(LoanApplication).filter(
            LoanApplication.id == extraction.application_id
        ).first()
        if application is None or application.applicant.user_id != viewer.id:
            raise NotFound(f"Details {extraction_id} not found")
    return extraction


def to_response(extraction: DocumentExtraction) -> dict:
    """The details laid out in the kind's own field order, ready for the screen."""
    kind = document_kinds.get_kind(extraction.declared_kind)
    rows = {f.field_key: f for f in extraction.fields}
    document = extraction.document
    return {
        "id": extraction.id,
        "document_id": extraction.document_id,
        "application_id": extraction.application_id,
        "kind": kind.key,
        "kind_label": kind.label,
        "doc_type": kind.doc_type,
        "file_name": document.file_name,
        "nature": document.nature,
        "status": extraction.status,
        "verification_level": extraction.verification_level,
        # Piece 34: what the text looked like, shown only if it disagrees.
        "detected_kind": extraction.detected_kind,
        "detected_label": (document_kinds.get_kind(extraction.detected_kind).label
                           if extraction.detected_kind else None),
        # Was any text found to read? False for a photo, a scan, or details
        # started again after a discard (the text is gone after the rebuild).
        "read_automatically": extraction.detected_kind is not None
        or any(f.source == "text_layer" for f in extraction.fields),
        "confirmed_by": extraction.confirmed_by,
        "confirmed_at": extraction.confirmed_at,
        "fields": [
            {
                "key": f.key, "label": f.label, "required": f.required,
                "check": f.check, "masked": f.masked,
                "value": rows[f.key].value if f.key in rows else None,
                "state": rows[f.key].state if f.key in rows else "missing",
                "source": rows[f.key].source if f.key in rows else None,
                "check_note": rows[f.key].check_note if f.key in rows else None,
            }
            for f in kind.fields
        ],
    }


# ---------------------------------------------------------------------------
# Changing
# ---------------------------------------------------------------------------

def _still_editable(extraction: DocumentExtraction) -> None:
    if extraction.status == "confirmed":
        raise RuleViolation("These details are already confirmed")
    if extraction.status == "discarded":
        raise RuleViolation("These details were discarded")
    if extraction.document.replaced_by_id is not None:
        raise RuleViolation("This copy has been replaced. Fill in the newer copy's details instead")


def _profile_notes(db: Session, extraction: DocumentExtraction) -> None:
    """
    Compare names and the date of birth with the customer's profile, and
    write a warning beside any that don't match. A warning only: people's
    names are spelt differently on different documents all the time.
    """
    application = db.query(LoanApplication).filter(LoanApplication.id == extraction.application_id).first()
    applicant = application.applicant if application else None
    for row in extraction.fields:
        # Only name and date-of-birth notes are ours to set. Any other note
        # (a Piece 34 reading note, say) is left alone, and so is a value
        # still waiting to be checked: its note says what's wrong with it.
        is_name = row.field_key in document_kinds.NAME_FIELDS
        is_dob = row.field_key == "date_of_birth"
        if not (is_name or is_dob) or row.state == "uncertain":
            continue
        row.check_note = None
        if applicant is None or row.value is None:
            continue
        if is_name:
            if validators.name_similarity(row.value, applicant.name) < validators.NAME_MATCH_THRESHOLD:
                row.check_note = "Doesn't match the name on the profile"
        elif applicant.date_of_birth and row.value != applicant.date_of_birth.isoformat():
            row.check_note = "Doesn't match the date of birth on the profile"


def update_fields(
    db: Session, extraction_id: int, values: dict[str, str | None],
    *, user: User, meta: dict | None = None,
) -> DocumentExtraction:
    """
    Check every value first, and only save if all of them pass: a half-saved
    form would be harder to follow than one that says what to fix.
    """
    extraction = get_extraction(db, extraction_id, viewer=user)
    _still_editable(extraction)
    kind = document_kinds.get_kind(extraction.declared_kind)

    problems: dict[str, str] = {}
    cleaned: dict[str, str | None] = {}
    for key, raw in values.items():
        field = document_kinds.field_of(kind, key)
        if field is None:
            problems[key] = "Not a field on this document"
            continue
        if raw is None or not raw.strip():
            cleaned[key] = None
            continue
        try:
            # Masking happens inside the check: a full Aadhaar number never
            # gets past this line.
            cleaned[key] = validators.CHECKS[field.check](raw)
        except ValueError as e:
            problems[key] = str(e)
    if problems:
        raise FieldProblems("Some details need fixing", problems)

    rows = {f.field_key: f for f in extraction.fields}
    for key, value in cleaned.items():
        row = rows[key]
        row.value = value
        if row.field_key not in document_kinds.NAME_FIELDS and row.field_key != "date_of_birth":
            row.check_note = None     # a new value replaces whatever the old note was about
        if value is None:
            row.state, row.source = "missing", None
        else:
            row.source = "user"
            # Piece 34 will fill machine_value; typing over it is a correction.
            corrected = row.machine_value is not None and row.machine_value != value
            row.state = "user_corrected" if corrected else "user_entered"

    _profile_notes(db, extraction)
    db.commit()
    db.refresh(extraction)
    return extraction


def _cross_field_problems(values: dict[str, str | None]) -> dict[str, str]:
    """Checks that need two fields at once."""
    problems = {}
    start, end = values.get("period_from"), values.get("period_to")
    if start and end and date.fromisoformat(end) < date.fromisoformat(start):
        problems["period_to"] = "The statement can't end before it starts"
    gross, net = values.get("gross_pay"), values.get("net_pay")
    if gross and net and float(net) > float(gross):
        problems["net_pay"] = "Net pay can't be more than gross pay"
    return problems


def confirm(db: Session, extraction_id: int, *, user: User, meta: dict | None = None) -> DocumentExtraction:
    """Every required field present and every check passed, then it counts."""
    extraction = get_extraction(db, extraction_id, viewer=user)
    _still_editable(extraction)
    kind = document_kinds.get_kind(extraction.declared_kind)
    values = {f.field_key: f.value for f in extraction.fields}

    problems = {f.key: "Required" for f in kind.fields if f.required and not values.get(f.key)}
    # Piece 34: a value read from the file that failed its check has to be
    # looked at and typed again before the details can be confirmed.
    for row in extraction.fields:
        if row.state == "uncertain":
            problems[row.field_key] = row.check_note or "Please check this value and type it again"
    problems.update(_cross_field_problems(values))
    if problems:
        raise FieldProblems("Some details are missing or need fixing", problems)

    extraction.status = "confirmed"
    extraction.confirmed_by = user.email
    extraction.confirmed_at = datetime.now(timezone.utc)
    # The format checks passed. That is all this level means: the document
    # is well-formed, not proven genuine (identification ≠ authenticity).
    extraction.verification_level = "consistency_checked"
    activity_service.record(
        db, action="document_details_confirmed",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="document", entity_id=extraction.document_id,
        details={"application_id": extraction.application_id, "kind": kind.key},
        **(meta or {}),
    )
    db.commit()
    db.refresh(extraction)
    logger.info("document_details_confirmed", extraction_id=extraction.id, kind=kind.key)
    return extraction


def discard(db: Session, extraction_id: int, *, user: User, meta: dict | None = None) -> DocumentExtraction:
    """
    Throw the details away, usually because the wrong kind was picked. The
    document then needs details again. Not allowed once staff have verified
    the document: by then the details are part of the record.
    """
    extraction = get_extraction(db, extraction_id, viewer=user)
    if extraction.status == "discarded":
        raise RuleViolation("These details were already discarded")
    if extraction.document.verified:
        raise RuleViolation("The document is verified, so its details can't be discarded")

    extraction.status = "discarded"
    activity_service.record(
        db, action="document_details_discarded",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="document", entity_id=extraction.document_id,
        details={"application_id": extraction.application_id, "kind": extraction.declared_kind},
        **(meta or {}),
    )
    db.commit()
    db.refresh(extraction)
    return extraction
