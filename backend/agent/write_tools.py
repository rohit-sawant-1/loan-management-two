"""
The tools that change a record — and the reason they do not change it yet.

Phase 4 gave the assistant six operations, and three of them write:
submitting an application, moving its status, and recording a document. One of
those can reject or disburse a loan, and neither of those can be undone.

**So these tools do not perform the change. They propose it.**

Each one records what it is about to do as plain data — the tool's name and its
arguments — and returns a sentence for the agent to read back to the person.
Nothing reaches the database until that person replies yes, at which point
`app/services/pending_actions.py` runs the recorded call directly.

Why it is built this way rather than asking the model to remember
----------------------------------------------------------------

The obvious shortcut is to let the agent hold the pending change in the
conversation and re-issue it when the person says yes. That would be a mistake.
A model that misremembers one digit disburses the wrong loan, and it would do it
confidently. Recording the arguments as data means **the model decides what to
propose, and Python decides what runs** — the model never gets a second chance
to change its mind about which application it was.

These are deliberately given only to staff. See `agent/agent.py`, which picks
the toolset from the caller's role.
"""

from __future__ import annotations

import structlog
from langchain_core.tools import tool

from app.services import pending_actions
from app.domain import rules

logger = structlog.get_logger()


def _propose(tool_name: str, arguments: dict, description: str) -> str:
    """
    Hold an action back and ask for confirmation.

    The returned sentence is what the agent reads back to the person, so it
    names the change in full. A vague "shall I proceed?" is worthless — the
    whole point is that they can catch a wrong application number here.
    """
    pending_actions.remember(tool_name, arguments, description)
    logger.info("write_proposed", operation="write_proposed",
                tool=tool_name, description=description)
    return (f"CONFIRMATION NEEDED. {description} "
            f"Tell the user exactly this and ask them to reply YES to go ahead. "
            f"Do not call any other tool.")


@tool
def update_application_status(application_id: str, new_status: str, remarks: str) -> str:
    """Use this to move a loan application to a new status: under_review, approved,
    rejected, or disbursed. Give the application number, the new status, and the
    reason the person gave you as remarks. This does NOT take effect immediately —
    it asks the person to confirm first, which is intended. Do not use this to
    create a new application."""
    try:
        app_id = int(str(application_id).strip())
    except ValueError:
        return f"'{application_id}' is not a valid application number."

    status = str(new_status).strip().lower()
    if status not in rules.STATUSES:
        allowed = ", ".join(sorted(rules.STATUSES))
        return f"'{new_status}' is not a status. It must be one of: {allowed}."

    if not str(remarks).strip():
        return "A reason is required before a status can change. Ask the user why."

    return _propose(
        "update_application_status",
        {"application_id": app_id, "new_status": status, "remarks": remarks.strip()},
        f"About to move application {app_id} to '{status}', "
        f"with the reason: {remarks.strip()}.",
    )


@tool
def submit_loan_application(applicant_id: str, loan_type: str, amount_requested: str,
                            tenure_months: str, purpose: str) -> str:
    """Use this to submit a brand new loan application for an existing applicant.
    loan_type must be personal, home, or auto. amount_requested is in rupees and
    tenure_months is the loan term. This asks the person to confirm before it
    takes effect. Do not use this to change an application that already exists."""
    try:
        parsed = {
            "applicant_id": int(str(applicant_id).strip()),
            "amount_requested": float(str(amount_requested).strip()),
            "tenure_months": int(str(tenure_months).strip()),
        }
    except ValueError:
        return ("The applicant number, amount and tenure must all be numbers. "
                "Ask the user for whichever one is missing.")

    kind = str(loan_type).strip().lower()
    if kind not in rules.LOAN_TYPES:
        allowed = ", ".join(sorted(rules.LOAN_TYPES))
        return f"'{loan_type}' is not a loan type. It must be one of: {allowed}."

    arguments = {**parsed, "loan_type": kind, "purpose": str(purpose).strip()}
    return _propose(
        "submit_loan_application",
        arguments,
        f"About to create a new {kind} loan application for applicant "
        f"{arguments['applicant_id']}: Rs {arguments['amount_requested']:,.0f} "
        f"over {arguments['tenure_months']} months.",
    )


@tool
def upload_document_metadata(application_id: str, doc_type: str, file_name: str) -> str:
    """Use this to record that a document has been received for a loan application.
    doc_type must be one of: id_proof, income_proof, bank_statement, property_docs,
    employment_letter. This asks the person to confirm before it takes effect."""
    try:
        app_id = int(str(application_id).strip())
    except ValueError:
        return f"'{application_id}' is not a valid application number."

    kind = str(doc_type).strip().lower()
    if kind not in rules.DOCUMENT_TYPES:
        allowed = ", ".join(sorted(rules.DOCUMENT_TYPES))
        return f"'{doc_type}' is not a document type. It must be one of: {allowed}."

    return _propose(
        "upload_document_metadata",
        {"application_id": app_id, "doc_type": kind, "file_name": str(file_name).strip()},
        f"About to record a {kind} document named '{file_name}' "
        f"against application {app_id}.",
    )


WRITE_TOOLS = [
    update_application_status,
    submit_loan_application,
    upload_document_metadata,
]
