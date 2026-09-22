"""
The eligibility check address. Mounted at /api/v1/applications by main.py,
giving /api/v1/applications/check-eligibility.

It is a POST with no id in the path, so it cannot be confused with the
/{application_id} addresses.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_business_actor
from app.models.user import User
from app.schemas.application import EligibilityCheckRequest, EligibilityCheckResponse
from app.services import eligibility_service
from app.services.activity_service import request_meta
from app.services.errors import Forbidden, NotFound

router = APIRouter()


@router.post("/check-eligibility", response_model=EligibilityCheckResponse)
def check_eligibility(
    data: EligibilityCheckRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_business_actor),
):
    """Would this loan be allowed? Advice, not a block."""
    try:
        return eligibility_service.check(db, data, viewer=user, meta=request_meta(request))
    except NotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except Forbidden as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.message)
