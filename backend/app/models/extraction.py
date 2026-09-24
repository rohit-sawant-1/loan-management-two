"""
Piece 33: the details of a document, typed in field by field.

`document_extractions` is one row per attempt at filling in a document's
details: which kind the document is, and whether the details are still
being filled in, confirmed, or thrown away. `extracted_fields` is one row per
field on it.

The name "extraction" looks ahead to Piece 34, where the machine reads the
fields out of the file itself. For now every value is typed by a person, so
`source` is always "user" and the machine-reading columns stay empty.

Both tables are brand new, so their rules sit inside the table definitions as
plain CHECK constraints, the same way as `stored_files` and
`application_edit_requests`. Two of those rules matter more than the others:
the Aadhaar number and the bank account number can only ever be stored in
their masked form. Even if the code had a bug, the database would refuse a
full Aadhaar number (T-114).
"""

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.db_checks import quoted_list
from app.domain import document_kinds, rules


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("loan_applications.id"), nullable=False, index=True)
    declared_kind = Column(String(30), nullable=False)
    # Pieces 34 and 35 fill these; they stay empty until then.
    detected_kind = Column(String(30), nullable=True)
    detection_score = Column(Float, nullable=True)
    batch_id = Column(String(40), nullable=True)
    status = Column(String(20), nullable=False, default="needs_input")
    verification_level = Column(String(30), nullable=False, default="not_verified")
    created_by = Column(String(150), nullable=False)       # email
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_by = Column(String(150), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="extractions")
    fields = relationship(
        "ExtractedField", back_populates="extraction",
        cascade="all, delete-orphan", order_by="ExtractedField.id",
    )

    __table_args__ = (
        CheckConstraint(f"status IN ({quoted_list(rules.EXTRACTION_STATUSES)})",
                        name="ck_extraction_status"),
        CheckConstraint(f"verification_level IN ({quoted_list(rules.VERIFICATION_LEVELS)})",
                        name="ck_extraction_verification_level"),
        CheckConstraint(f"declared_kind IN ({quoted_list(document_kinds.KINDS)})",
                        name="ck_extraction_declared_kind"),
        # Confirmed means someone confirmed it, at a known time.
        CheckConstraint(
            "status <> 'confirmed' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="ck_extraction_confirmed_has_who_and_when",
        ),
    )


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, index=True)
    extraction_id = Column(Integer, ForeignKey("document_extractions.id"), nullable=False, index=True)
    field_key = Column(String(40), nullable=False)
    value = Column(String(300), nullable=True)            # masked where the registry says
    machine_value = Column(String(300), nullable=True)    # Piece 34: what the machine read
    source = Column(String(20), nullable=True)
    confidence = Column(Float, nullable=True)
    state = Column(String(20), nullable=False, default="missing")
    check_note = Column(String(200), nullable=True)       # e.g. "doesn't match the profile"

    extraction = relationship("DocumentExtraction", back_populates="fields")

    __table_args__ = (
        UniqueConstraint("extraction_id", "field_key", name="uq_extracted_field_once"),
        CheckConstraint(f"state IN ({quoted_list(rules.EXTRACTED_FIELD_STATES)})",
                        name="ck_extracted_field_state"),
        CheckConstraint(f"source IS NULL OR source IN ({quoted_list(rules.EXTRACTED_FIELD_SOURCES)})",
                        name="ck_extracted_field_source"),
        # T-114: only ever the masked form, in either column.
        CheckConstraint(
            "field_key <> 'aadhaar_number' OR ("
            "(value IS NULL OR value GLOB 'XXXX XXXX [0-9][0-9][0-9][0-9]') AND "
            "(machine_value IS NULL OR machine_value GLOB 'XXXX XXXX [0-9][0-9][0-9][0-9]'))",
            name="ck_extracted_field_aadhaar_masked",
        ),
        CheckConstraint(
            "field_key <> 'account_number' OR ("
            "(value IS NULL OR value GLOB 'XXXX[0-9][0-9][0-9][0-9]') AND "
            "(machine_value IS NULL OR machine_value GLOB 'XXXX[0-9][0-9][0-9][0-9]'))",
            name="ck_extracted_field_account_masked",
        ),
    )
