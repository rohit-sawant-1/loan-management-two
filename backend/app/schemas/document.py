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


class DocumentListResponse(BaseModel):
    """The documents on an application, plus a checklist for the screen."""
    items: list[DocumentResponse]
    required: list[str]     # what this loan type needs
    missing: list[str]      # what has not been uploaded yet


class UnverifiedDocumentsResponse(BaseModel):
    """Piece 31: the "Documents to check" page — many applications at once, so
    there is no single loan type's checklist to attach, only a page of items."""
    items: list[DocumentResponse]
    total_count: int
    page: int
    limit: int
