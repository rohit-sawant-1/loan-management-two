"""
The Manager's Morning Briefing — the headline feature (D-13).

The manager opens the app and the AI has already read the whole pipeline:
what is stuck, what is risky, what needs a decision today. One short
briefing, written the way a good deputy would summarise the desk before a
morning meeting.

The discipline here is the same one Phase 5 settled on (D-19): **every
number is computed in Python, from the database, before any LLM sees
anything.** The model is handed a picture that is already correct and asked
only to put it into readable paragraphs. That means the figures on the
manager's screen cannot drift, cannot be invented, and are the same numbers
the dashboard shows. If the LLM is slow, rate-limited or unavailable, the
briefing still renders — as the facts, without the prose.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.domain import rules
from app.models.application import ApplicationStatus, LoanApplication
from app.models.document import Document
from app.models.user import User
from app.services import activity_service
from app.utils.finance import format_rupees
from app.utils.text import readable, readable_list

logger = structlog.get_logger()

# How long an application may sit in a status before it counts as "stuck".
# Deliberately short for a demo database; a real branch would tune these.
STUCK_AFTER_DAYS: dict[str, int] = {
    "submitted": 2,       # nobody has even picked it up
    "under_review": 5,    # being looked at, but not decided
    "approved": 3,        # approved but the money has not moved
}

# How many individual applications to name in the briefing. A manager can act
# on a handful; a list of forty is a spreadsheet, not a briefing.
MAX_NAMED = 5


def _age_in_days(when: datetime | None, now: datetime) -> float:
    if when is None:
        return 0.0
    # SQLite hands back naive datetimes that are actually UTC (T-39).
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (now - when).total_seconds() / 86400


def gather_facts(db: Session) -> dict:
    """
    Everything the briefing is built from, as plain numbers. No LLM involved,
    so this is exactly as trustworthy as the database itself.
    """
    now = datetime.now(timezone.utc)

    by_status_rows = (
        db.query(
            LoanApplication.status,
            func.count(LoanApplication.id),
            func.coalesce(func.sum(LoanApplication.amount_requested), 0.0),
        )
        .group_by(LoanApplication.status)
        .all()
    )
    by_status = {s: 0 for s in rules.STATUSES}
    amount_by_status = {s: 0.0 for s in rules.STATUSES}
    for status_, count, amount in by_status_rows:
        by_status[status_.value] = count
        amount_by_status[status_.value] = float(amount)

    # Everything still open, loaded once with its applicant. Only open
    # applications matter to a morning briefing — a rejected loan from March
    # is not something anyone needs to act on today.
    open_statuses = [ApplicationStatus.submitted, ApplicationStatus.under_review,
                     ApplicationStatus.approved]
    open_apps = (
        db.query(LoanApplication)
        .options(joinedload(LoanApplication.applicant))
        .filter(LoanApplication.status.in_(open_statuses))
        .all()
    )

    stuck: list[dict] = []
    failed_eligibility: list[dict] = []
    for app in open_apps:
        status = app.status.value
        # "approved" ages from when it was last touched (the approval);
        # the others age from submission.
        reference = app.updated_at if status == "approved" else app.submitted_at
        days = _age_in_days(reference, now)
        limit = STUCK_AFTER_DAYS.get(status)
        if limit is not None and days > limit:
            stuck.append({
                "id": app.id,
                "applicant_name": app.applicant.name if app.applicant else "unknown",
                "status": status,
                "days_waiting": round(days, 1),
                "amount": float(app.amount_requested),
                "loan_type": app.loan_type.value,
            })
        # Piece 19's stored assessment earns its keep here: applications the
        # bank's own rules flagged at submission and that are still open.
        if app.eligibility_passed is False:
            failed_eligibility.append({
                "id": app.id,
                "applicant_name": app.applicant.name if app.applicant else "unknown",
                "status": status,
                "amount": float(app.amount_requested),
                "loan_type": app.loan_type.value,
            })

    stuck.sort(key=lambda row: row["days_waiting"], reverse=True)
    failed_eligibility.sort(key=lambda row: row["amount"], reverse=True)

    # Applications waiting on a decision that still do not have all their
    # documents — the single most common reason a file cannot move.
    waiting_ids = [a.id for a in open_apps
                   if a.status in (ApplicationStatus.submitted, ApplicationStatus.under_review)]
    missing_docs: list[dict] = []
    if waiting_ids:
        doc_rows = (
            db.query(Document.application_id, Document.doc_type)
            .filter(Document.application_id.in_(waiting_ids))
            .all()
        )
        uploaded: dict[int, set[str]] = {}
        for application_id, doc_type in doc_rows:
            uploaded.setdefault(application_id, set()).add(
                doc_type.value if hasattr(doc_type, "value") else str(doc_type)
            )
        for app in open_apps:
            if app.id not in waiting_ids:
                continue
            missing = rules.missing_documents(app.loan_type.value, uploaded.get(app.id, set()))
            if missing:
                missing_docs.append({
                    "id": app.id,
                    "applicant_name": app.applicant.name if app.applicant else "unknown",
                    "missing": missing,
                })
    missing_docs.sort(key=lambda row: len(row["missing"]), reverse=True)

    awaiting_decision = by_status["submitted"] + by_status["under_review"]

    return {
        "generated_at": now,
        "total_open": len(open_apps),
        "by_status": by_status,
        "amount_by_status": amount_by_status,
        "awaiting_decision": awaiting_decision,
        "value_awaiting_decision": amount_by_status["submitted"] + amount_by_status["under_review"],
        "approved_not_disbursed": by_status["approved"],
        "value_approved_not_disbursed": amount_by_status["approved"],
        "stuck": stuck[:MAX_NAMED],
        "stuck_total": len(stuck),
        "failed_eligibility": failed_eligibility[:MAX_NAMED],
        "failed_eligibility_total": len(failed_eligibility),
        "missing_documents": missing_docs[:MAX_NAMED],
        "missing_documents_total": len(missing_docs),
    }


def _facts_as_text(facts: dict) -> str:
    """The facts, written out for the model to turn into prose. Numbers only, no opinions."""
    lines = [
        f"Open applications: {facts['total_open']}.",
        f"Awaiting a decision: {facts['awaiting_decision']} "
        f"worth {format_rupees(facts['value_awaiting_decision'])}.",
        f"Approved but not yet disbursed: {facts['approved_not_disbursed']} "
        f"worth {format_rupees(facts['value_approved_not_disbursed'])}.",
        f"Applications waiting longer than the branch's targets: {facts['stuck_total']}.",
    ]
    for row in facts["stuck"]:
        # `days_waiting` is rounded to one decimal for sorting, so it arrives as
        # 3.0. Left alone the model writes "3.0 days" into the manager's
        # briefing, and "1.0 days" reads worse still (T-96).
        days = round(row["days_waiting"])
        lines.append(
            f"  - Application {row['id']} ({row['applicant_name']}, "
            f"{readable(row['loan_type'])}, "
            f"{format_rupees(row['amount'])}) has been {readable(row['status'])} "
            f"for {days} day{'' if days == 1 else 's'}."
        )
    if facts["failed_eligibility_total"]:
        lines.append(f"Still open despite failing the bank's own eligibility check at "
                     f"submission: {facts['failed_eligibility_total']}.")
        for row in facts["failed_eligibility"]:
            lines.append(f"  - Application {row['id']} ({row['applicant_name']}, "
                         f"{format_rupees(row['amount'])}, now {readable(row['status'])}).")
    if facts["missing_documents_total"]:
        lines.append(f"Waiting on a decision but missing documents: {facts['missing_documents_total']}.")
        for row in facts["missing_documents"]:
            # Document types are stored as `id_proof`. The model prints what it
            # is given, so without this the manager's briefing says "is missing
            # id_proof, bank_statement".
            missing = readable_list(row["missing"])
            lines.append(f"  - Application {row['id']} ({row['applicant_name']}) "
                         f"is missing {missing}.")
    return "\n".join(lines)


def _fallback_narrative(facts: dict) -> str:
    """What the manager reads if the LLM is unavailable. Still useful, just not prose."""
    parts = [
        f"{facts['awaiting_decision']} application(s) are waiting on a decision, worth "
        f"{format_rupees(facts['value_awaiting_decision'])}."
    ]
    if facts["stuck_total"]:
        parts.append(f"{facts['stuck_total']} have been waiting longer than the branch's targets.")
    if facts["approved_not_disbursed"]:
        parts.append(f"{facts['approved_not_disbursed']} are approved but not yet disbursed, "
                     f"worth {format_rupees(facts['value_approved_not_disbursed'])}.")
    if facts["missing_documents_total"]:
        parts.append(f"{facts['missing_documents_total']} are held up by missing documents.")
    if facts["failed_eligibility_total"]:
        parts.append(f"{facts['failed_eligibility_total']} are still open despite failing "
                     f"the eligibility check at submission.")
    if len(parts) == 1:
        parts.append("Nothing is overdue and no documents are outstanding.")
    return " ".join(parts)


def _narrative(facts: dict) -> tuple[str, bool]:
    """
    Ask the LLM to write the briefing from facts that are already correct.
    Returns (text, written_by_ai). Never raises.
    """
    try:
        from llm_provider import get_llm
        from multi_agent.llm_text import text_of

        llm = get_llm(temperature=0.1)
        prompt = (
            "You are the branch manager's deputy at a bank, writing their morning "
            "briefing on the loan pipeline. Below are today's figures — every one of "
            "them is already correct.\n\n"
            f"{_facts_as_text(facts)}\n\n"
            "Write 3 short paragraphs, in plain professional English:\n"
            "1. Where the pipeline stands overall.\n"
            "2. What needs attention today, naming the specific application numbers "
            "that are worst and saying why.\n"
            "3. What you would do first, as one clear recommendation.\n\n"
            "Rules: use only the numbers given above, never invent an application, an "
            "amount or a name, and do not repeat the figures as a list — write it the "
            "way a person would say it out loud. If nothing needs attention, say so "
            "plainly rather than manufacturing a concern."
        )
        response = llm.invoke(prompt)
        text = text_of(response.content)
        if text:
            return text, True
        return _fallback_narrative(facts), False
    except Exception as exc:                                            # noqa: BLE001
        logger.warning("briefing_llm_failed", operation="briefing", error=str(exc))
        return _fallback_narrative(facts), False


def build_briefing(db: Session, *, user: User, meta: dict | None = None) -> dict:
    """The whole briefing: the narrative, plus the facts it was written from."""
    facts = gather_facts(db)
    narrative, written_by_ai = _narrative(facts)

    activity_service.record(
        db, action="briefing_viewed", actor_id=user.email, actor_role=user.role.value,
        details={"open_applications": facts["total_open"], "stuck": facts["stuck_total"],
                 "written_by_ai": written_by_ai},
        **(meta or {}),
    )
    db.commit()
    logger.info("briefing_generated", operation="briefing", user_email=user.email,
                open_applications=facts["total_open"], stuck=facts["stuck_total"],
                written_by_ai=written_by_ai)

    return {
        "generated_at": facts["generated_at"],
        "written_by_ai": written_by_ai,
        "narrative": narrative,
        "headline_numbers": {
            "open_applications": facts["total_open"],
            "awaiting_decision": facts["awaiting_decision"],
            "value_awaiting_decision": facts["value_awaiting_decision"],
            "approved_not_disbursed": facts["approved_not_disbursed"],
            "value_approved_not_disbursed": facts["value_approved_not_disbursed"],
            "waiting_too_long": facts["stuck_total"],
            "missing_documents": facts["missing_documents_total"],
            "failed_eligibility": facts["failed_eligibility_total"],
        },
        "needs_attention": facts["stuck"],
        "missing_documents": facts["missing_documents"],
        "failed_eligibility": facts["failed_eligibility"],
    }
