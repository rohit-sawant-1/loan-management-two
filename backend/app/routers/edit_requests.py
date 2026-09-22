"""
Addresses for edit requests (Piece 25). Two routers live here, because the
addresses sit in two places:

  `router`        mounted at /api/v1/applications, for one application's requests
      POST /{application_id}/edit-requests     the customer asks
      GET  /{application_id}/edit-requests     the owner or staff read them

  `staff_router`  mounted at /api/v1/edit-requests, staff only
      GET  ""                                  the queue, filtered by status
      POST /{request_id}/approve               say yes (a note is optional)
      POST /{request_id}/refuse                say no (a note is required)

Saving the approved edit is `PATCH /api/v1/applications/{id}`, in
`applications.py`, because it changes the application itself.

Paths never end in "/" (T-02).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_staff, require_staff_view
from app.domain import rules
from app.models.user import User
from app.schemas.edit_request import (
    ApproveBody, EditRequestCreate, EditRequestListResponse, EditRequestResponse, RefuseBody,
)
from app.services import edit_request_service
from app.services.activity_service import request_meta
from app.services.errors import Forbidden, NotFound, RuleViolation

router = APIRouter()
staff_router = APIRouter()


def _http(e: Exception) -> HTTPException:
    """Turn a service error into the right HTTP answer, the same way applications.py does."""
    if isinstance(e, NotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    if isinstance(e, Forbidden):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    if isinstance(e, RuleViolation):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)
    raise e


# --- One application's requests ----------------------------------------------

@router.post(
    "/{application_id}/edit-requests",
    response_model=EditRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_edit_request(
    application_id: int,
    data: EditRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return edit_request_service.create_request(
            db, application_id, data, user=user, meta=request_meta(request)
        )
    except (NotFound, Forbidden, RuleViolation) as e:
        raise _http(e)


@router.get("/{application_id}/edit-requests", response_model=list[EditRequestResponse])
def list_edit_requests_for_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return edit_request_service.requests_for_application(db, application_id, viewer=user)
    except (NotFound, Forbidden) as e:
        raise _http(e)


# --- The staff queue -----------------------------------------------------------

@staff_router.get("", response_model=EditRequestListResponse)
def list_edit_requests(
    status_filter: str | None = Query(None, alias="status",
                                      description="pending, approved, refused, completed or closed"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_view),
):
    # A bad filter value is a 400, the same as the applications list (T-18).
    if status_filter is not None and status_filter not in rules.EDIT_REQUEST_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{status_filter}'. Allowed: {', '.join(rules.EDIT_REQUEST_STATUSES)}",
        )
    items, total = edit_request_service.list_requests(
        db, status=status_filter, page=page, limit=limit
    )
    return EditRequestListResponse(
        items=[EditRequestResponse.model_validate(r) for r in items],
        total_count=total, page=page, limit=limit,
    )


@staff_router.post("/{request_id}/approve", response_model=EditRequestResponse)
def approve_edit_request(
    request_id: int,
    body: ApproveBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    try:
        return edit_request_service.approve(
            db, request_id, body.note, user=user, meta=request_meta(request)
        )
    except (NotFound, RuleViolation) as e:
        raise _http(e)


@staff_router.post("/{request_id}/refuse", response_model=EditRequestResponse)
def refuse_edit_request(
    request_id: int,
    body: RefuseBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    try:
        return edit_request_service.refuse(
            db, request_id, body.note, user=user, meta=request_meta(request)
        )
    except (NotFound, RuleViolation) as e:
        raise _http(e)
