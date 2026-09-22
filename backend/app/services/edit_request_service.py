"""
The logic behind edit requests (Piece 25, D-28).

The flow, in the order it happens:

  1. The customer asks to change some fields and says why   -> create_request
  2. A loan officer or the manager says yes or no             -> approve / refuse
  3. On a yes, the customer saves new values, once            -> apply_edit
  4. If the application's status moves on first, any open
     request is closed automatically                          -> close_open_requests

Every step writes an activity row, filed under the application's own number,
so it shows on the manager's Activity page and on that application's history.

Same pattern as the other services: add the rows, record the activity, then
one `db.commit()` at the end, so a step either happens completely or not at all.
"""

import json
from datetime import datetime, timezone
from time import perf_counter

import structlog
from sqlalchemy.orm import Session, joinedload

from app.domain import rules
from app.models.application import LoanApplication
from app.models.edit_request import EditRequest, EditRequestStatus
from app.models.user import User, UserRole
from app.schemas.edit_request import ApplicationEditBody, EditRequestCreate
from app.services import activity_service, eligibility_service
from app.services.errors import Forbidden, NotFound, RuleViolation

logger = structlog.get_logger()

# The line added to the stored eligibility text after an edit. No date in it,
# on purpose (D-22): the time lives in `eligibility_checked_at`, which the
# browser shows in the reader's own timezone.
RECHECK_LINE = "Re-checked after an approved edit"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _readable_status(status) -> str:
    """"under_review" -> "under review", for messages a person reads."""
    return rules._v(status).replace("_", " ")


def _load_application(db: Session, application_id: int) -> LoanApplication:
    application = (
        db.query(LoanApplication)
        .options(joinedload(LoanApplication.applicant))
        .filter(LoanApplication.id == application_id)
        .first()
    )
    if application is None:
        raise NotFound(f"Application {application_id} not found")
    return application


def _load_request(db: Session, request_id: int) -> EditRequest:
    """One request, with its application and applicant loaded in the same query."""
    request = (
        db.query(EditRequest)
        .options(joinedload(EditRequest.application).joinedload(LoanApplication.applicant))
        .filter(EditRequest.id == request_id)
        .first()
    )
    if request is None:
        raise NotFound(f"Edit request {request_id} not found")
    return request


def _require_owner(application: LoanApplication, user: User) -> None:
    """
    Only the customer the application belongs to may ask for or save an edit.
    Staff don't ask on a customer's behalf; they decide.
    """
    if user.role != UserRole.applicant:
        raise Forbidden("Only the customer who owns this application can ask to change it")
    if application.applicant is None or application.applicant.user_id != user.id:
        raise Forbidden("You can only change your own applications")


def _open_request(db: Session, application_id: int) -> EditRequest | None:
    """The one request still waiting or unlocked for this application, if any."""
    return (
        db.query(EditRequest)
        .filter(
            EditRequest.application_id == application_id,
            EditRequest.status.in_([EditRequestStatus(s) for s in rules.OPEN_EDIT_REQUEST_STATUSES]),
        )
        .first()
    )


def _close(db: Session, request: EditRequest, application: LoanApplication,
           *, user: User | None, meta: dict | None) -> None:
    """Close one request because the application moved on. The caller commits."""
    why = f"Closed automatically: the application moved to {_readable_status(application.status)}."
    request.status = EditRequestStatus.closed
    request.decided_at = _now()
    request.decided_by = user.email if user else None
    request.decision_note = why
    activity_service.record(
        db, action="edit_request_closed",
        actor_id=user.email if user else "system",
        actor_role=user.role.value if user else None,
        entity_type="application", entity_id=application.id,
        details={"request_id": request.id, "fields": json.loads(request.fields), "reason": why},
        **(meta or {}),
    )


def _refuse_if_moved_on(db: Session, request: EditRequest, *, user: User, meta: dict | None) -> None:
    """
    A safety net. `close_open_requests` normally closes a request the moment
    the status changes, but if one ever slips through, it is closed here
    instead of being acted on.
    """
    application = request.application
    if not rules.is_editable(application.status):
        _close(db, request, application, user=user, meta=meta)
        db.commit()
        raise RuleViolation(
            f"This application is now {_readable_status(application.status)}, "
            f"so the edit request has been closed"
        )


# ---------------------------------------------------------------------------
# 1. The customer asks
# ---------------------------------------------------------------------------

def create_request(
    db: Session,
    application_id: int,
    data: EditRequestCreate,
    *,
    user: User,
    meta: dict | None = None,
) -> EditRequest:
    started = perf_counter()
    application = _load_application(db, application_id)
    _require_owner(application, user)

    if not rules.is_editable(application.status):
        raise RuleViolation(
            f"This application is {_readable_status(application.status)} and can no longer be changed. "
            f"Changes are only possible while it is submitted or under review."
        )
    if _open_request(db, application.id) is not None:
        raise RuleViolation("There is already an open edit request for this application")

    request = EditRequest(
        application_id=application.id,
        requested_by=user.email,
        fields=json.dumps(data.fields),
        reason=data.reason,
        status=EditRequestStatus.pending,
    )
    db.add(request)
    db.flush()   # we need the request's id for the activity row

    activity_service.record(
        db, action="edit_requested",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="application", entity_id=application.id,
        details={"request_id": request.id, "fields": data.fields, "reason": data.reason},
        **(meta or {}),
    )
    db.commit()
    logger.info("edit_requested", operation="create_edit_request", application_id=application.id,
                request_id=request.id, fields=data.fields,
                duration_ms=int((perf_counter() - started) * 1000), status="success")
    return _load_request(db, request.id)


# ---------------------------------------------------------------------------
# Reading requests
# ---------------------------------------------------------------------------

def list_requests(
    db: Session,
    *,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[EditRequest], int]:
    """
    A page of requests for the staff page, plus the total count.

    Waiting requests come oldest first, so whoever has been waiting longest is
    at the top. Every other view is newest first, like the activity page.
    """
    query = db.query(EditRequest).options(
        joinedload(EditRequest.application).joinedload(LoanApplication.applicant)
    )
    if status:
        query = query.filter(EditRequest.status == EditRequestStatus(status))

    if status == EditRequestStatus.pending.value:
        order = (EditRequest.created_at.asc(), EditRequest.id.asc())
    else:
        order = (EditRequest.created_at.desc(), EditRequest.id.desc())

    total = query.count()
    items = query.order_by(*order).offset((page - 1) * limit).limit(limit).all()
    return items, total


def requests_for_application(db: Session, application_id: int, *, viewer: User) -> list[EditRequest]:
    """Every request on one application, oldest first. The owner or staff only."""
    application = _load_application(db, application_id)
    if viewer.role == UserRole.applicant and (
        application.applicant is None or application.applicant.user_id != viewer.id
    ):
        raise Forbidden("You can only view your own applications")
    return (
        db.query(EditRequest)
        .options(joinedload(EditRequest.application).joinedload(LoanApplication.applicant))
        .filter(EditRequest.application_id == application_id)
        .order_by(EditRequest.created_at.asc(), EditRequest.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# 2. Staff decide
# ---------------------------------------------------------------------------

def _decide(db: Session, request_id: int, *, approve: bool, note: str | None,
            user: User, meta: dict | None) -> EditRequest:
    request = _load_request(db, request_id)
    if request.status != EditRequestStatus.pending:
        raise RuleViolation(f"This request has already been dealt with (it is {request.status.value})")
    _refuse_if_moved_on(db, request, user=user, meta=meta)

    request.status = EditRequestStatus.approved if approve else EditRequestStatus.refused
    request.decided_by = user.email
    request.decided_at = _now()
    request.decision_note = note

    activity_service.record(
        db, action="edit_request_approved" if approve else "edit_request_refused",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="application", entity_id=request.application_id,
        details={"request_id": request.id, "fields": json.loads(request.fields), "note": note},
        **(meta or {}),
    )
    db.commit()
    logger.info("edit_request_decided", operation="decide_edit_request", request_id=request.id,
                application_id=request.application_id, approved=approve, decided_by=user.email,
                status="success")
    return _load_request(db, request.id)


def approve(db: Session, request_id: int, note: str | None, *, user: User,
            meta: dict | None = None) -> EditRequest:
    return _decide(db, request_id, approve=True, note=note, user=user, meta=meta)


def refuse(db: Session, request_id: int, note: str, *, user: User,
           meta: dict | None = None) -> EditRequest:
    return _decide(db, request_id, approve=False, note=note, user=user, meta=meta)


# ---------------------------------------------------------------------------
# 3. The customer saves the approved edit
# ---------------------------------------------------------------------------

def apply_edit(
    db: Session,
    application_id: int,
    data: ApplicationEditBody,
    *,
    user: User,
    meta: dict | None = None,
) -> LoanApplication:
    # Imported here rather than at the top: application_service imports this
    # file (for close_open_requests), so importing it back at the top would be
    # a circle. By the time this function runs, both files are fully loaded.
    from app.services.application_service import check_type_limits

    started = perf_counter()
    application = _load_application(db, application_id)
    _require_owner(application, user)

    request = _open_request(db, application.id)
    if request is None or request.status != EditRequestStatus.approved:
        raise Forbidden(
            "Editing is locked. Ask for an edit first, and wait for bank staff to approve it"
        )
    _refuse_if_moved_on(db, request, user=user, meta=meta)

    unlocked = set(json.loads(request.fields))
    sent = data.changed_fields()
    not_unlocked = sorted(set(sent) - unlocked)
    if not_unlocked:
        raise Forbidden(
            f"Only these fields were approved for change: {', '.join(sorted(unlocked))}"
        )

    # Keep only what really differs from today's values.
    changes = {name: value for name, value in sent.items() if getattr(application, name) != value}
    if not changes:
        raise RuleViolation("Nothing changed: the new values are the same as the current ones")

    # The same per-loan-type limits a brand-new application has to meet.
    new_amount = changes.get("amount_requested", application.amount_requested)
    new_tenure = changes.get("tenure_months", application.tenure_months)
    check_type_limits(application.loan_type, new_amount, new_tenure)

    before = {name: getattr(application, name) for name in changes}
    previous_eligibility = {
        "passed": application.eligibility_passed,
        "summary": application.eligibility_summary,
    }
    for name, value in changes.items():
        setattr(application, name, value)

    # Re-check eligibility against the new figures and replace the stored
    # result (settled 2026-09-22). The old one goes into the activity row
    # below, so the bank's record of what the rules said before is not lost.
    assessment = eligibility_service.assess(
        application.applicant, application.loan_type.value,
        application.amount_requested, application.tenure_months,
    )
    summary = eligibility_service.build_summary_text(
        application.applicant, application.loan_type.value,
        application.amount_requested, application.tenure_months, assessment,
    )
    application.eligibility_passed = assessment.eligible
    application.eligibility_summary = f"{summary}\n\n{RECHECK_LINE}, saved by {user.email}."
    application.eligibility_checked_at = _now()

    # One approval, one save. Editing locks again from here.
    request.status = EditRequestStatus.completed
    request.completed_at = _now()

    activity_service.record(
        db, action="application_edited",
        actor_id=user.email, actor_role=user.role.value,
        entity_type="application", entity_id=application.id,
        details={
            "request_id": request.id,
            "before": before,
            "after": changes,
            "eligibility_passed_before": previous_eligibility["passed"],
            "eligibility_passed_after": assessment.eligible,
            "previous_eligibility_summary": previous_eligibility["summary"],
        },
        **(meta or {}),
    )
    db.commit()
    logger.info("application_edited", operation="apply_edit", application_id=application.id,
                request_id=request.id, fields=sorted(changes),
                eligibility_passed=assessment.eligible,
                duration_ms=int((perf_counter() - started) * 1000), status="success")
    return application


# ---------------------------------------------------------------------------
# 4. The status moved on
# ---------------------------------------------------------------------------

def close_open_requests(db: Session, application: LoanApplication, *, user: User | None,
                        meta: dict | None = None) -> int:
    """
    Called by `application_service.update_status` after it sets the new
    status. If the application can no longer be edited, any request still
    waiting or unlocked is closed and logged. Returns how many were closed.
    Does not commit; the status change it belongs to does.
    """
    if rules.is_editable(application.status):
        return 0
    request = _open_request(db, application.id)
    if request is None:
        return 0
    _close(db, request, application, user=user, meta=meta)
    return 1
