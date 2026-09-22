"""
Addresses for documents. Mounted at /api/v1/applications by main.py, so the
full addresses are /api/v1/applications/{id}/documents and below.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_business_actor, require_staff
from app.models.user import User
from app.schemas.document import (
    CreateDocumentSchema, DocumentListResponse, DocumentResponse, DocumentUploadBody,
)
from app.services import document_service
from app.services.activity_service import request_meta
from app.services.errors import Forbidden, NotFound

router = APIRouter()


def _http(e: Exception) -> HTTPException:
    if isinstance(e, NotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    if isinstance(e, Forbidden):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    raise e


@router.post(
    "/{application_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_document(
    application_id: int,
    body: DocumentUploadBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_business_actor),
):
    # The trainer's schema carries application_id; build it from the address plus the body.
    data = CreateDocumentSchema(
        application_id=application_id, doc_type=body.doc_type, file_name=body.file_name
    )
    try:
        return document_service.add_document(db, data, user=user, meta=request_meta(request))
    except (NotFound, Forbidden) as e:
        raise _http(e)


@router.get("/{application_id}/documents", response_model=DocumentListResponse)
def list_documents(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        items, required, missing = document_service.list_documents(db, application_id, viewer=user)
    except (NotFound, Forbidden) as e:
        raise _http(e)
    return DocumentListResponse(items=items, required=required, missing=missing)


@router.patch("/{application_id}/documents/{document_id}/verify", response_model=DocumentResponse)
def verify_document(
    application_id: int,
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    try:
        return document_service.verify_document(
            db, application_id, document_id, user=user, meta=request_meta(request)
        )
    except (NotFound, Forbidden) as e:
        raise _http(e)
