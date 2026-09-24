"""
Addresses for a document's details (Piece 33).

`router` is mounted at /api/v1/applications, for starting details on one
document. `details_router` is mounted at /api/v1/extractions, for everything
after that. Changes use `require_business_actor` (the customer or staff,
never the admin, T-117); reading uses `get_current_user`, so the admin can
look.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_business_actor
from app.models.user import User
from app.schemas.extraction import ExtractionResponse, FieldsUpdateBody, StartExtractionBody
from app.services import extraction_service
from app.services.activity_service import request_meta
from app.services.errors import FieldProblems, Forbidden, NotFound, RuleViolation

router = APIRouter()
details_router = APIRouter()


def _http(e: Exception) -> HTTPException:
    if isinstance(e, NotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    if isinstance(e, Forbidden):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    if isinstance(e, FieldProblems):
        # One message per field, so the form can show each beside its box.
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                             detail={"message": e.message, "fields": e.fields})
    if isinstance(e, RuleViolation):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)
    raise e


@router.post(
    "/{application_id}/documents/{document_id}/extraction",
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_details(
    application_id: int,
    document_id: int,
    body: StartExtractionBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_business_actor),
):
    try:
        extraction = extraction_service.start_for_document(
            db, application_id, document_id, body.kind, user=user, meta=request_meta(request),
        )
        return extraction_service.to_response(extraction)
    except (NotFound, Forbidden, RuleViolation) as e:
        raise _http(e)


@details_router.get("/{extraction_id}", response_model=ExtractionResponse)
def read_details(
    extraction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return extraction_service.to_response(
            extraction_service.get_extraction(db, extraction_id, viewer=user)
        )
    except NotFound as e:
        raise _http(e)


@details_router.patch("/{extraction_id}/fields", response_model=ExtractionResponse)
def save_fields(
    extraction_id: int,
    body: FieldsUpdateBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_business_actor),
):
    try:
        return extraction_service.to_response(extraction_service.update_fields(
            db, extraction_id, body.values, user=user, meta=request_meta(request),
        ))
    except (NotFound, RuleViolation) as e:
        raise _http(e)


@details_router.post("/{extraction_id}/confirm", response_model=ExtractionResponse)
def confirm_details(
    extraction_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_business_actor),
):
    try:
        return extraction_service.to_response(
            extraction_service.confirm(db, extraction_id, user=user, meta=request_meta(request))
        )
    except (NotFound, RuleViolation) as e:
        raise _http(e)


@details_router.post("/{extraction_id}/discard", response_model=ExtractionResponse)
def discard_details(
    extraction_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_business_actor),
):
    try:
        return extraction_service.to_response(
            extraction_service.discard(db, extraction_id, user=user, meta=request_meta(request))
        )
    except (NotFound, RuleViolation) as e:
        raise _http(e)
