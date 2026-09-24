"""
Schemas for documents.

`CreateDocumentSchema` is a name the trainer's tests import (T-06).
"""


from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.document import DocumentType
from app.schemas.common import UtcDateTime, check_file_name


class CreateDocumentSchema(BaseModel):
    """What the service accepts. Test UNIT-07 builds this directly, with application_id."""
    application_id: int = Field(..., gt=0)
    # One of the six types. UNIT-07 sends "passport_copy" and expects a rejection.
    doc_type: DocumentType
    file_name: str = Field(..., min_length=1, max_length=255)

    _check_file_name = field_validator("file_name")(check_file_name)


class DocumentUploadBody(BaseModel):
    """
    What the endpoint accepts. The application id comes from the address, so
    the body is just the type and the file name. The router turns this plus
    the address into a CreateDocumentSchema for the service.
    """
    doc_type: DocumentType
    file_name: str = Field(..., min_length=1, max_length=255)

    _check_file_name = field_validator("file_name")(check_file_name)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    doc_type: DocumentType
    file_name: str
    uploaded_at: UtcDateTime | None = None
    verified: bool
    # Piece 31. All optional and all None for a name-only document — the
    # trainer's original route still returns exactly the shape it always did.
    file_id: int | None = None
    size_bytes: int | None = None
    original_size_bytes: int | None = None
    content_type: str | None = None
    nature: str | None = None
    # Piece 32d. Both None for a current document; set once a newer copy
    # has replaced it.
    replaced_by_id: int | None = None
    replaced_at: UtcDateTime | None = None


class DocumentReplaceBody(BaseModel):
    """
    Piece 32d, the name-only replace. No doc_type here on purpose: a
    replacement always keeps the type of the document it replaces.
    """
    file_name: str = Field(..., min_length=1, max_length=255)

    _check_file_name = field_validator("file_name")(check_file_name)


class DocumentListResponse(BaseModel):
    """The documents on an application, plus a checklist for the screen."""
    items: list[DocumentResponse]
    required: list[str]     # what this loan type needs
    missing: list[str]      # what has not been uploaded yet
    test_count: int = 0     # Piece 32: how many uploaded documents are TEST
    real_count: int = 0     # how many are REAL (undeclared counts as neither)
    # Piece 32d: earlier copies that were replaced. Staff and the admin only;
    # always empty for a customer. None of these count towards anything above.
    replaced: list[DocumentResponse] = []


class UnverifiedDocumentsResponse(BaseModel):
    """Piece 31: the "Documents to check" page — many applications at once, so
    there is no single loan type's checklist to attach, only a page of items."""
    items: list[DocumentResponse]
    total_count: int
    page: int
    limit: int
