"""
The two document addresses that don't belong to one application (Piece 31).

`router` is mounted at /api/v1/files by main.py — a real file's bytes.
`unverified_router` is mounted at /api/v1/documents — the staff queue,
same idea as /api/v1/edit-requests being its own router next to the
per-application ones (Piece 25).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_staff_view
from app.models.user import User
from app.schemas.document import DocumentResponse, UnverifiedDocumentsResponse
from app.services import document_service
from app.services.activity_service import request_meta
from app.services.errors import Forbidden, NotFound

router = APIRouter()
unverified_router = APIRouter()


@router.get("/{file_id}")
def view_file(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    The owner, staff or the admin may view a stored file's actual bytes.
    Streamed with headers that stop a browser from doing anything with it
    except show or download it — never execute it, never guess a different
    type for it.
    """
    try:
        stored, data = document_service.get_file_for_view(
            db, file_id, viewer=user, meta=request_meta(request)
        )
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Forbidden as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)

    safe_name = stored.display_name.encode("ascii", "ignore").decode("ascii") or "document"
    return Response(
        content=data,
        media_type=stored.content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Disposition": f'inline; filename="{safe_name}"',
        },
    )


@unverified_router.get("/unverified", response_model=UnverifiedDocumentsResponse)
def unverified_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_view),
):
    """Every document nobody has verified yet, across every application — the "Documents to check" page."""
    items, total = document_service.unverified_documents(db, page=page, limit=limit)
    return UnverifiedDocumentsResponse(
        items=[DocumentResponse.model_validate(d) for d in items],
        total_count=total, page=page, limit=limit,
    )
