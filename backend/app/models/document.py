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

    application = relationship("LoanApplication", back_populates="documents")
    stored_file = relationship("StoredFile")

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
