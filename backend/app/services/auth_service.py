"""
The logic behind register, sign up, and log in.

Decision D-07 (Option A):
  - `register_staff` is the trainer's register address. It creates bank staff.
    Managers and the administrator are seeded, never self-registered, so this
    refuses those roles.
  - `signup_applicant` is for customers. One call creates both the login row
    and the borrower profile, linked (T-23).
"""

import structlog
from sqlalchemy.orm import Session

from app.domain import rules
from app.models.applicant import Applicant
from app.models.user import User, UserRole
from app.schemas.auth import ApplicantSignupRequest, RegisterRequest
from app.services import activity_service
from app.services.errors import EmailAlreadyRegistered, InvalidCredentials, RuleViolation
from app.utils.auth import create_access_token, hash_password, verify_password

logger = structlog.get_logger()

# Used when someone tries to log in with an email that does not exist. We
# still run a password check against this dummy hash so that a wrong email
# and a wrong password take the same amount of time. Otherwise an attacker
# could time the response to learn which emails are registered.
_DUMMY_HASH = hash_password("not-a-real-password-1A")


def _email_taken(db: Session, email: str) -> bool:
    email = email.lower()
    return (
        db.query(User).filter(User.email == email).first() is not None
        or db.query(Applicant).filter(Applicant.email == email).first() is not None
    )


def register_staff(db: Session, data: RegisterRequest, *, meta: dict | None = None) -> User:
    """Create a bank staff account. Default role is loan officer."""
    role = data.role or UserRole(rules.DEFAULT_STAFF_ROLE)
    if role == UserRole.applicant:
        raise RuleViolation("Customers sign up at /auth/register-applicant")
    if role == UserRole.branch_manager:
        raise RuleViolation("Manager accounts are created by the bank, not by registration")
    # T-115: without this, anyone could register themselves as the administrator.
    if role == UserRole.admin:
        raise RuleViolation("Administrator accounts are created by the bank, not by registration")

    email = data.email.lower()
    if _email_taken(db, email):
        raise EmailAlreadyRegistered("An account with this email already exists")

    user = User(name=data.name, email=email, hashed_password=hash_password(data.password), role=role)
    db.add(user)
    db.flush()

    activity_service.record(
        db, action="staff_registered", actor_id=email, actor_role=role.value,
        entity_type="user", entity_id=user.id, **(meta or {}),
    )
    db.commit()
    db.refresh(user)
    logger.info("staff_registered", user_email=email, role=role.value)
    return user


def signup_applicant(db: Session, data: ApplicantSignupRequest, *, meta: dict | None = None) -> User:
    """Create a customer login and their borrower profile in one go."""
    email = data.email.lower()
    if _email_taken(db, email):
        raise EmailAlreadyRegistered("An account with this email already exists")

    user = User(
        name=data.name, email=email,
        hashed_password=hash_password(data.password), role=UserRole.applicant,
    )
    db.add(user)
    db.flush()

    applicant = Applicant(
        user_id=user.id,
        name=data.name, email=email, phone=data.phone,
        credit_score=data.credit_score, annual_income=data.annual_income,
        employment_status=data.employment_status,
        date_of_birth=data.date_of_birth,
        years_with_employer=data.years_with_employer,
        existing_monthly_emi=data.existing_monthly_emi,
    )
    db.add(applicant)
    db.flush()

    activity_service.record(
        db, action="applicant_signed_up", actor_id=email, actor_role=UserRole.applicant.value,
        entity_type="applicant", entity_id=applicant.id, **(meta or {}),
    )
    db.commit()
    db.refresh(user)
    logger.info("applicant_signed_up", user_email=email, applicant_id=applicant.id)
    return user


def authenticate(db: Session, email: str, password: str, *, meta: dict | None = None) -> tuple[User, str]:
    """
    Check a login. Returns (user, token) on success. Raises InvalidCredentials
    on failure, with a message that never says whether it was the email or
    the password.
    """
    email = email.lower()
    user = db.query(User).filter(User.email == email).first()

    # Always do one password check, real or dummy, so timing gives nothing away.
    ok = verify_password(password, user.hashed_password if user else _DUMMY_HASH)

    if user is None or not ok or not user.is_active:
        activity_service.record(
            db, action="login_failed", actor_id=email,
            details={"reason": "bad_credentials" if user else "unknown_email"},
            **(meta or {}),
        )
        db.commit()
        logger.warning("auth_failure", reason="invalid_credentials", email=email)
        raise InvalidCredentials("Invalid email or password")

    token = create_access_token(email=user.email, role=user.role.value)
    activity_service.record(
        db, action="login_succeeded", actor_id=user.email, actor_role=user.role.value,
        entity_type="user", entity_id=user.id, **(meta or {}),
    )
    db.commit()
    logger.info("login_succeeded", user_email=user.email, role=user.role.value)
    return user, token
