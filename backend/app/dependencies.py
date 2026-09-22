"""
"Who is calling, and are they allowed?"

Every protected endpoint asks for `get_current_user`. FastAPI runs it before
the endpoint, and if it raises, the endpoint never runs.

TRAP T-01: FastAPI's HTTPBearer answers 403 when the Authorization header is
missing. The trainer's test API-06 expects 401. So we turn off its automatic
error (`auto_error=False`) and raise the 401 ourselves.
"""

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.utils.auth import decode_access_token
from app.utils.otel_config import get_tracer

logger = structlog.get_logger()

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=reason,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Read the token, load the user, or answer 401. Wrapped in an auth.validate span."""
    with get_tracer().start_as_current_span("auth.validate") as span:
        if credentials is None:
            span.set_attribute("auth.token_valid", False)
            logger.warning("auth_failure", reason="missing_token")
            raise _unauthorized("Not authenticated")

        payload = decode_access_token(credentials.credentials)
        if payload is None or not payload.get("sub"):
            span.set_attribute("auth.token_valid", False)
            logger.warning("auth_failure", reason="invalid_or_expired_token")
            raise _unauthorized("Invalid or expired token")

        user = db.query(User).filter(User.email == payload["sub"]).first()
        if user is None or not user.is_active:
            span.set_attribute("auth.token_valid", False)
            logger.warning("auth_failure", reason="user_not_found_or_inactive", email=payload["sub"])
            raise _unauthorized("Invalid or expired token")

        span.set_attribute("auth.user_id", user.id)
        span.set_attribute("auth.token_valid", True)
        # The observability guide asks for this event on every validated token.
        logger.info("token_validated", user_email=user.email, role=user.role.value, token_valid=True)
        return user


def require_role(*roles: UserRole):
    """
    Use as `Depends(require_role(UserRole.branch_manager))`.
    Lets the user through only if their role is one of those listed.
    """
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            logger.warning("auth_forbidden", user_email=user.email, role=user.role.value,
                           needed=[r.value for r in roles])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to do this",
            )
        return user
    return _check


# Handy shortcuts. These two guard ACTIONS, so the admin is never in them.
require_staff = require_role(UserRole.loan_officer, UserRole.branch_manager)
require_manager = require_role(UserRole.branch_manager)

# Piece 27: the System Administrator. Every address is sorted into VIEW or ACT.
# The admin passes the VIEW guards below and none of the ACT ones.

# Only the admin, for the admin's own screens.
require_admin = require_role(UserRole.admin)

# "Can look at staff screens": the applicants list, the edit-request queue,
# the dashboard. Looking only; changing still needs require_staff.
require_staff_view = require_role(UserRole.loan_officer, UserRole.branch_manager, UserRole.admin)

# "Can read the audit log": the manager, and the admin who oversees the system.
require_audit_view = require_role(UserRole.branch_manager, UserRole.admin)


def require_business_actor(user: User = Depends(get_current_user)) -> User:
    """
    Anyone logged in EXCEPT the admin. Used on the actions that were open to
    every login (creating an application, adding a document, the eligibility
    check), because those used to mean "a customer or staff", and the admin is
    neither. The services still do their own owner checks after this.
    """
    if user.role == UserRole.admin:
        logger.warning("auth_forbidden", user_email=user.email, role=user.role.value,
                       reason="admin_cannot_act")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The system administrator can view records but cannot create or change them.",
        )
    return user
