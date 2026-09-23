"""
The logic behind documents on an application.
"""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain import rules
from app.models.application import LoanApplication
from app.models.document import Document, DocumentType
from app.models.stored_file import StoredFile
from app.models.user import User, UserRole
from app.schemas.common import clean_display_name
from app.schemas.document import CreateDocumentSchema
from app.services import activity_service, file_service, notification_service, storage
from app.services.errors import Forbidden, NotFound, RuleViolation

logger = structlog.get_logger()


def _application_for(db: Session, application_id: int, viewer: User) -> LoanApplication:
    """Load the application and check the viewer may touch it."""
    application = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if application is None:
        raise NotFound(f"Application {application_id} not found")
    if viewer.role == UserRole.applicant and application.applicant.user_id != viewer.id:
        raise Forbidden("You can only manage documents on your own applications")
    return application


def add_document(
    db: Session, data: CreateDocumentSchema, *, user: User, meta: dict | None = None
) -> Document:
    """
    Record a document. The same type may be added more than once; both are
    kept (user story 05). New documents start unverified.
    """
    application = _application_for(db, data.application_id, user)

    document = Document(
        application_id=application.id,
        doc_type=data.doc_type,
        file_name=data.file_name,
        verified=False,
    )
    db.add(document)
    db.flush()

    activity_service.record(
        db, action="document_added",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="document", entity_id=document.id,
        details={"application_id": application.id, "doc_type": data.doc_type.value,
                 "file_name": data.file_name},
        **(meta or {}),
    )
    db.commit()
    db.refresh(document)
    logger.info("document_added", application_id=application.id, document_id=document.id,
                doc_type=data.doc_type.value)
    return document


def list_documents(
    db: Session, application_id: int, *, viewer: User
) -> tuple[list[Document], list[str], list[str]]:
    """The documents on an application, what the loan type requires, and what is still missing."""
    application = _application_for(db, application_id, viewer)
    documents = (
        db.query(Document)
        .filter(Document.application_id == application.id)
        .order_by(Document.uploaded_at, Document.id)
        .all()
    )
    required = sorted(rules.required_documents(application.loan_type))
    missing = rules.missing_documents(application.loan_type, [d.doc_type for d in documents])
    return documents, required, missing


def _check_rate_limits(db: Session, application: LoanApplication, user: User) -> None:
    """
    Checked before the pipeline runs, not after — a rate-limited request
    should fail fast rather than pay for a rebuild (and a possible Gemini
    call) it was always going to refuse.
    """
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = db.query(func.count(StoredFile.id)).filter(
        StoredFile.uploaded_by == user.email, StoredFile.uploaded_at >= one_hour_ago
    ).scalar() or 0
    if recent >= rules.UPLOAD_RATE_LIMIT_PER_HOUR:
        raise RuleViolation(
            f"Too many uploads in the last hour (the limit is {rules.UPLOAD_RATE_LIMIT_PER_HOUR}). "
            "Try again later."
        )

    total_bytes = db.query(func.sum(StoredFile.size_bytes)).filter(
        StoredFile.applicant_id == application.applicant_id
    ).scalar() or 0
    if total_bytes >= rules.UPLOAD_RATE_LIMIT_BYTES_PER_CUSTOMER:
        cap_mb = rules.UPLOAD_RATE_LIMIT_BYTES_PER_CUSTOMER // (1024 * 1024)
        raise RuleViolation(f"This account has reached its {cap_mb} MB total limit for uploaded documents")


def add_uploaded_document(
    db: Session,
    application_id: int,
    doc_type: DocumentType,
    *,
    consent: bool,
    raw_filename: str,
    file_bytes,
    user: User,
    meta: dict | None = None,
) -> Document:
    """
    A real file, run through `file_service`'s whole safety and
    classification pipeline before anything is stored (Piece 31). One
    commit creates both the `stored_files` row and the `documents` row
    together — a document is never left pointing at a file that was never
    actually written.

    `nature` and `storage_zone` are never taken from the caller — they are
    whatever `file_service.process_upload` decided, and nothing here can
    override that.
    """
    application = _application_for(db, application_id, user)
    if not consent:
        raise RuleViolation("You must agree before a document can be stored")
    _check_rate_limits(db, application, user)

    try:
        display_name = clean_display_name(raw_filename)
    except ValueError as e:
        raise RuleViolation(str(e)) from e

    try:
        result, stored_name = file_service.process_upload(doc_type.value, file_bytes)
    except RuleViolation as e:
        # A blocked upload is worth recording even though nothing was
        # stored — an auditor asking "why did this fail" deserves the
        # actual reason, and a pattern of refusals on one account is
        # itself worth being able to see.
        activity_service.record(
            db, action="upload_blocked",
            actor_id=user.email, actor_role=user.role.value,
            entity_type="application", entity_id=application.id,
            details={"doc_type": doc_type.value, "reason": e.message},
            **(meta or {}),
        )
        db.commit()
        raise

    stored = StoredFile(
        applicant_id=application.applicant_id,
        application_id=application.id,
        stored_name=stored_name,
        display_name=display_name,
        content_type=result.content_type,
        size_bytes=result.size_bytes,
        original_size_bytes=result.original_size_bytes,
        pages=result.pages,
        width=result.width,
        height=result.height,
        sha256=result.sha256,
        nature=result.nature,
        storage_zone=result.storage_zone,
        consent_at=datetime.now(timezone.utc),
        uploaded_by=user.email,
    )
    db.add(stored)
    db.flush()   # need stored.id for the document row

    document = Document(
        application_id=application.id, doc_type=doc_type,
        file_name=display_name, file_id=stored.id, verified=False,
    )
    db.add(document)
    db.flush()

    activity_service.record(
        db, action="document_added",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="document", entity_id=document.id,
        details={
            "application_id": application.id, "doc_type": doc_type.value,
            "size_before": result.original_size_bytes, "size_after": result.size_bytes,
            "nature": result.nature,
        },
        **(meta or {}),
    )

    if result.nature == "test":
        # Piece 32, notification trigger 2: staff hear about a demo
        # document the moment it lands. Same commit as the upload, so a
        # rolled-back document never leaves a dangling notice behind.
        notification_service.notify_staff_test_document(
            db, document, applicant_name=application.applicant.name,
        )

    db.commit()
    db.refresh(document)
    logger.info("document_uploaded", application_id=application.id, document_id=document.id,
                doc_type=doc_type.value, nature=result.nature, zone=result.storage_zone)
    return document


def unverified_documents(
    db: Session, *, page: int = 1, limit: int = 20
) -> tuple[list[Document], int]:
    """Every unverified document across every application, newest first — the "Documents to check" page."""
    query = db.query(Document).filter(Document.verified.is_(False)).order_by(Document.uploaded_at.desc())
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return items, total


def get_file_for_view(
    db: Session, file_id: int, *, viewer: User, meta: dict | None = None
) -> tuple[StoredFile, bytes]:
    """
    The owner, staff or the admin may view a stored file. Every staff or
    admin view is logged — the owner looking at their own document is not,
    the same way reading your own application never is.
    """
    stored = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if stored is None:
        raise NotFound(f"File {file_id} not found")

    if viewer.role == UserRole.applicant and not _owns(db, stored, viewer):
        raise Forbidden("You can only view your own documents")

    data = storage.open_file(stored.storage_zone.value, stored.stored_name)

    if viewer.role != UserRole.applicant:
        activity_service.record(
            db, action="document_viewed",
            actor_id=viewer.email, actor_role=viewer.role.value,
            entity_type="document", entity_id=stored.id,
            details={"application_id": stored.application_id},
            **(meta or {}),
        )
        db.commit()

    return stored, data


def _owns(db: Session, stored: StoredFile, viewer: User) -> bool:
    from app.models.applicant import Applicant

    applicant = db.query(Applicant).filter(Applicant.id == stored.applicant_id).first()
    return applicant is not None and applicant.user_id == viewer.id


def verify_document(
    db: Session, application_id: int, document_id: int, *, user: User, meta: dict | None = None
) -> Document:
    """A loan officer marks a document as checked. Staff only; the router enforces that."""
    application = _application_for(db, application_id, user)
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.application_id == application.id)
        .first()
    )
    if document is None:
        raise NotFound(f"Document {document_id} not found on application {application_id}")

    document.verified = True
    activity_service.record(
        db, action="document_verified",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="document", entity_id=document.id,
        details={"application_id": application.id, "doc_type": document.doc_type.value},
        **(meta or {}),
    )
    db.commit()
    db.refresh(document)
    logger.info("document_verified", application_id=application.id, document_id=document.id,
                verified_by=user.email)
    return document
