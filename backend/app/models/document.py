"""
The `documents` table: a piece of paperwork attached to an application.

Phase 1 stored only the file name, not the file itself. Piece 31 adds real
uploads: `file_id` points at the `stored_files` row that holds the actual
(encrypted) bytes, but it is nullable, because the trainer's original
name-only route is untouched and still writes a `Document` with no file
behind it at all.
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.domain import document_kinds


class DocumentType(str, enum.Enum):
    id_proof = "id_proof"
    income_proof = "income_proof"
    bank_statement = "bank_statement"
    property_docs = "property_docs"
    employment_letter = "employment_letter"
    # Added: the manual requires it for auto loans (D-04).
    vehicle_quotation = "vehicle_quotation"
    # Piece 31: new, optional, not required for any loan type (see rules.py).
    photograph = "photograph"
    signature = "signature"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer, ForeignKey("loan_applications.id"), nullable=False, index=True
    )
    doc_type = Column(Enum(DocumentType), nullable=False)
    file_name = Column(String(255), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    # False until a loan officer checks it.
    verified = Column(Boolean, nullable=False, default=False)
    # Piece 31. Nullable: a name-only document has no file behind it at all.
    # A database that already had a `documents` table before this piece
    # existed gets this column from database.py's _add_missing_columns
    # instead — the same pattern Piece 19 used for the eligibility columns.
    # SQLite's own foreign-key checking stays off project-wide (T-03), so
    # declaring it here is for clarity and the relationship below, not
    # enforcement.
    file_id = Column(Integer, ForeignKey("stored_files.id"), nullable=True)
    # Piece 32d. Set when a newer copy replaces this one. The row is never
    # deleted — it simply stops counting anywhere (checklist, Documents to
    # check, the application detail). Both empty means "current".
    replaced_by_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    replaced_at = Column(DateTime(timezone=True), nullable=True)

    application = relationship("LoanApplication", back_populates="documents")
    stored_file = relationship("StoredFile")
    # Piece 33: the details typed in for this document. Usually one; a
    # discarded attempt (the wrong kind picked, say) stays alongside the new one.
    extractions = relationship(
        "DocumentExtraction", back_populates="document",
        cascade="all, delete-orphan", order_by="DocumentExtraction.id",
    )

    # --- Read-only conveniences for DocumentResponse -----------------------
    # A name-only document (no file_id) has no stored_file, so every one of
    # these is simply None for it — the response schema's fields are all
    # optional for exactly that reason.

    @property
    def size_bytes(self) -> int | None:
        return self.stored_file.size_bytes if self.stored_file else None

    @property
    def original_size_bytes(self) -> int | None:
        return self.stored_file.original_size_bytes if self.stored_file else None

    @property
    def content_type(self) -> str | None:
        return self.stored_file.content_type if self.stored_file else None

    @property
    def nature(self) -> str | None:
        return self.stored_file.nature.value if self.stored_file else None

    # --- Piece 33: the document's details -----------------------------------

    @property
    def current_extraction(self):
        """The latest attempt at this document's details that wasn't thrown away."""
        live = [e for e in self.extractions if e.status != "discarded"]
        return live[-1] if live else None

    @property
    def kind(self) -> str | None:
        extraction = self.current_extraction
        return extraction.declared_kind if extraction else None

    @property
    def extraction_id(self) -> int | None:
        extraction = self.current_extraction
        return extraction.id if extraction else None

    @property
    def details_confirmed(self) -> bool:
        extraction = self.current_extraction
        return extraction is not None and extraction.status == "confirmed"

    @property
    def needs_details(self) -> bool:
        """
        True for a real file of a type that has kinds (ID proof, income proof,
        bank statement) whose details aren't confirmed yet. Such a document
        doesn't count towards the checklist until they are. A name-only
        document never needs details: there is no file to read them from, so
        it counts exactly as it always has (the seed data, the trainer's tests).
        """
        doc_type = getattr(self.doc_type, "value", self.doc_type)
        return (
            self.file_id is not None
            and doc_type in document_kinds.TYPES_WITH_KINDS
            and not self.details_confirmed
        )

    @property
    def detail_summary(self) -> str | None:
        """For a confirmed document: its kind and one telling detail, e.g. "Aadhaar card · XXXX XXXX 1234"."""
        if not self.details_confirmed:
            return None
        extraction = self.current_extraction
        kind = document_kinds.get_kind(extraction.declared_kind)
        key = document_kinds.SUMMARY_FIELD.get(extraction.declared_kind)
        value = next((f.value for f in extraction.fields if f.field_key == key), None)
        return f"{kind.label} · {value}" if value else kind.label
