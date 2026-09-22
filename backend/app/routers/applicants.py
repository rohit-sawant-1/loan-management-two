"""
Addresses for borrower profiles. Mounted at /api/v1/applicants by main.py.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_staff, require_staff_view
from app.models.user import User
from app.schemas.applicant import ApplicantResponse, CreateApplicantSchema
from app.services import applicant_service
from app.services.activity_service import request_meta
from app.services.errors import EmailAlreadyRegistered, Forbidden, NotFound

router = APIRouter()


class ApplicantListResponse(BaseModel):
    items: list[ApplicantResponse]
    total_count: int
    page: int
    limit: int


@router.post("", response_model=ApplicantResponse, status_code=status.HTTP_201_CREATED)
def create_applicant(
    data: CreateApplicantSchema,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    """Staff create a borrower profile on a customer's behalf."""
    try:
        return applicant_service.create_applicant(
            db, data, created_by=user.email, created_by_role=user.role.value,
            meta=request_meta(request),
        )
    except EmailAlreadyRegistered as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)


@router.get("", response_model=ApplicantListResponse)
def list_applicants(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_view),
):
    items, total = applicant_service.list_applicants(db, page=page, limit=limit)
    return ApplicantListResponse(items=items, total_count=total, page=page, limit=limit)


@router.get("/me", response_model=ApplicantResponse)
def my_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The logged-in applicant's own borrower profile. Declared before /{applicant_id} so 'me' is not read as an id."""
    applicant = applicant_service.get_own_profile(db, user)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No borrower profile is linked to this login")
    return applicant


@router.get("/{applicant_id}", response_model=ApplicantResponse)
def get_applicant(
    applicant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Staff see anyone. An applicant sees only themselves."""
    try:
        return applicant_service.get_applicant_for_viewer(db, applicant_id, user)
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Forbidden as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
