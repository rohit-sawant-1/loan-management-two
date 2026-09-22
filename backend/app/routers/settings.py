"""
Reading the system settings. Mounted at /api/v1/settings by main.py.

Any signed-in person may read them, because the screens change with them: the
document form has to know whether real uploads are on. Only the administrator
may change one, and that address lives in `admin.py` behind `require_admin`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.settings import SettingsResponse
from app.services import settings_service

router = APIRouter()


@router.get("", response_model=SettingsResponse)
def read_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Every setting and its current value."""
    return SettingsResponse(**settings_service.get_all(db))
