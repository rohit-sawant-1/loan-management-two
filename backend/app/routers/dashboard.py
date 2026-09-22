"""
The dashboard address. Mounted at /api/v1/dashboard by main.py.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_staff_view
from app.models.user import User
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard_service
from app.services.activity_service import request_meta

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_view),
):
    """The pipeline at a glance. Zeros, not an error, when there is nothing yet."""
    return dashboard_service.summary(db, user=user, meta=request_meta(request))
