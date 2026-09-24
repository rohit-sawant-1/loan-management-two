"""
Schemas for a document's details (Piece 33).

The values themselves are checked in `app/domain/validators.py`, field by
field, because which check applies depends on the document's kind. Here we
only keep the request to a sane size.
"""

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import UtcDateTime


class StartExtractionBody(BaseModel):
    """Which kind the document is, for an upload that has no details yet."""
    kind: str = Field(..., min_length=2, max_length=30)


class FieldsUpdateBody(BaseModel):
    """
    Field key → what was typed. An empty value or null clears the field.
    No document has more than a handful of fields, so 20 is a generous cap.
    """
    values: dict[str, str | None] = Field(..., max_length=20)

    @field_validator("values")
    @classmethod
    def _sane_sizes(cls, values):
        for key, value in values.items():
            if len(key) > 40:
                raise ValueError("Unknown field")
            if value is not None and len(value) > 300:
                raise ValueError(f"{key}: at most 300 characters")
        return values


class ExtractionFieldOut(BaseModel):
    key: str
    label: str
    required: bool
    check: str               # which kind of input the screen should show
    masked: bool
    value: str | None = None
    state: str
    source: str | None = None
    check_note: str | None = None


class ExtractionResponse(BaseModel):
    id: int
    document_id: int
    application_id: int
    kind: str
    kind_label: str
    doc_type: str
    file_name: str
    nature: str | None = None
    status: str
    verification_level: str
    detected_kind: str | None = None        # Piece 34
    detected_label: str | None = None
    read_automatically: bool = False
    confirmed_by: str | None = None
    confirmed_at: UtcDateTime | None = None
    fields: list[ExtractionFieldOut]
