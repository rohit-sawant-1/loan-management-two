"""
Addresses for loan applications. Mounted at /api/v1/applications by main.py.

Paths here never end in "/" (T-02). Static paths must be declared before
"/{application_id}" so FastAPI does not mistake them for an id.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_staff
from app.domain import rules
from app.models.user import User
from app.schemas.application import (
    ApplicationListResponse, ApplicationResponse, ApplicationSummary,
    CreateApplicationSchema, StatusUpdateRequest,
)
from app.schemas.edit_request import ApplicationEditBody
from app.services import application_service, edit_request_service
from app.services.activity_service import request_meta
from app.services.errors import Forbidden, NotFound, RuleViolation

router = APIRouter()


def _http(e: Exception) -> HTTPException:
    """Turn a service error into the right HTTP answer."""
    if isinstance(e, NotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    if isinstance(e, Forbidden):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
    if isinstance(e, RuleViolation):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)
    raise e


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    data: CreateApplicationSchema,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        application = application_service.create_application(
            db, data, user=user, meta=request_meta(request)
        )
    except (NotFound, Forbidden, RuleViolation) as e:
        raise _http(e)
    # Reload with relationships so the response carries the first history row.
    return application_service.get_application(db, application.id, viewer=user)


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    status_filter: str | None = Query(None, alias="status"),
    loan_type: str | None = Query(None),
    from_date: date | None = Query(None, description="Submitted on or after, YYYY-MM-DD"),
    to_date: date | None = Query(None, description="Submitted on or before, YYYY-MM-DD"),
    search: str | None = Query(None, max_length=100,
                               description="Part of an applicant's name or email, or an application number"),
    sort_by: str = Query("submitted_at", description="Column to sort by"),
    order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # The user story says a bad filter value is a 400, not FastAPI's usual 422 (T-18).
    if status_filter is not None and status_filter not in rules.STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{status_filter}'. Allowed: {', '.join(rules.STATUSES)}",
        )
    if loan_type is not None and loan_type not in rules.LOAN_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid loan_type '{loan_type}'. Allowed: {', '.join(rules.LOAN_TYPES)}",
        )
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="from_date must not be after to_date")
    # Sorting is refused the same way a bad status is, so the whole endpoint
    # answers with one kind of error rather than two (T-18).
    if sort_by not in application_service.SORT_COLUMNS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot sort by '{sort_by}'. Allowed: {', '.join(application_service.SORT_COLUMNS)}",
        )
    if order not in application_service.SORT_ORDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid order '{order}'. Allowed: asc, desc")

    items, total = application_service.list_applications(
        db, viewer=user, status=status_filter, loan_type=loan_type,
        from_date=from_date, to_date=to_date, search=search,
        sort_by=sort_by, order=order, page=page, limit=limit,
    )
    summaries = [
        ApplicationSummary(
            id=a.id, applicant_id=a.applicant_id,
            applicant_name=a.applicant.name if a.applicant else None,
            loan_type=a.loan_type, amount_requested=a.amount_requested,
            tenure_months=a.tenure_months, status=a.status, submitted_at=a.submitted_at,
        )
        for a in items
    ]
    return ApplicationListResponse(items=summaries, total_count=total, page=page, limit=limit)


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return application_service.get_application(db, application_id, viewer=user)
    except (NotFound, Forbidden) as e:
        raise _http(e)


@router.patch("/{application_id}", response_model=ApplicationResponse)
def edit_application(
    application_id: int,
    data: ApplicationEditBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Piece 25: the customer saves an edit that bank staff approved. Only the
    fields they were approved to change, only once, and only while the
    application is still submitted or under review. Everything else is refused.
    """
    try:
        application = edit_request_service.apply_edit(
            db, application_id, data, user=user, meta=request_meta(request)
        )
    except (NotFound, Forbidden, RuleViolation) as e:
        raise _http(e)
    # Reload with relationships so the response carries history and documents.
    return application_service.get_application(db, application.id, viewer=user)


@router.patch("/{application_id}/status")
def update_status(
    application_id: int,
    data: StatusUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    try:
        application = application_service.update_status(
            db, application_id, data.new_status, data.remarks, user=user, meta=request_meta(request)
        )
    except NotFound as e:
        raise _http(e)
    except Forbidden as e:
        raise _http(e)
    except RuleViolation as e:
        # The user story wants a 400 here, with "Invalid status transition" in the message.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    return {
        "message": "Status updated successfully",
        "application_id": application.id,
        "status": application.status.value,
    }
