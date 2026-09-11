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
from app.utils.finance import format_rupees

logger = structlog.get_logger()


def _unpack(first_value, expected: tuple[str, ...]) -> dict | None:
    """
    Rescue the arguments when ReAct hands them over as one blob.

    The ReAct format has no structure for a tool that takes several arguments —
    the model writes one "Action Input:" line, and LangChain passes whatever is
    on it. For a single-argument tool that is fine. For these, the entire
    dictionary regularly lands in the *first* parameter as a string, leaving
    the rest empty, and the call dies in validation before the tool body ever
    runs. `agent/tools.py` documents the single-argument half of this problem;
    this is the multi-argument half.

    So when the first parameter arrives looking like a whole dict, it is parsed
    and used. `ast.literal_eval` handles the single quotes a model usually
    writes; `json.loads` handles proper JSON. Neither can execute anything —
    they only read data — which is why they are used rather than `eval`.

    Two shapes are seen in practice and both are handled:

        {'application_id': 1, 'new_status': 'approved', 'remarks': 'ok'}
        application_id: 1, new_status: approved, remarks: ok

    Returns the unpacked arguments, or None if this was a normal call.
    """
    import ast
    import json
    import re

    text = str(first_value).strip()

    # Shape one: a real dict, quoted however the model felt like quoting it.
    if text.startswith("{") and text.endswith("}"):
        for parse in (ast.literal_eval, json.loads):
            try:
                parsed = parse(text)
            except (ValueError, SyntaxError):
                continue
            if isinstance(parsed, dict) and any(k in parsed for k in expected):
                return {k: parsed.get(k, "") for k in expected}

    # Shape two: named pairs, written with either a colon or an equals sign.
    # Split on the commas that come immediately before another known field
    # name, so a comma inside a reason ("income too low, and no collateral")
    # does not tear the value in half.
    if any(re.search(rf"\b{name}\s*[:=]", text) for name in expected):
        boundary = re.compile(rf",\s*(?=(?:{'|'.join(expected)})\s*[:=])")
        found: dict[str, str] = {}
        for piece in boundary.split(text):
            match = re.match(rf"\s*[\"']?({'|'.join(expected)})[\"']?\s*[:=]\s*(.*)",
                             piece, re.DOTALL)
            if match:
                found[match.group(1)] = match.group(2).strip().strip("\"',")
        if found:
            return {k: found.get(k, "") for k in expected}

    # Shape three: bare values in the order the tool declares them, which is
    # what a model falls back to when it stops writing names at all. Only
    # trusted when the count matches exactly — anything else is guesswork, and
    # guessing which value is the application number is how the wrong loan gets
    # approved.
    pieces = [p.strip().strip("\"'") for p in text.split(",")]
    if len(pieces) == len(expected) and all(pieces):
        return dict(zip(expected, pieces))

    return None


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


# Every parameter below the first has a default, and that is load-bearing
# rather than sloppy. ReAct writes one "Action Input:" line, so LangChain
# regularly delivers all of a multi-argument call inside the first parameter.
# With required parameters, pydantic rejects that before the function body runs
# and `_unpack` never gets a chance — the call dies with a validation error the
# person sees as "no AI available". Defaults let the call land, and `_unpack`
# sorts out what the model actually meant.
@tool
def update_application_status(application_id: str, new_status: str = "",
                              remarks: str = "") -> str:
    """Use this to move a loan application to a new status: under_review, approved,
    rejected, or disbursed. Give the application number, the new status, and the
    reason the person gave you as remarks. This does NOT take effect immediately —
    it asks the person to confirm first, which is intended. Do not use this to
    create a new application."""
    blob = _unpack(application_id, ("application_id", "new_status", "remarks"))
    if blob:
        application_id, new_status, remarks = (
            blob["application_id"], blob["new_status"], blob["remarks"])

    try:
        app_id = int(str(application_id).strip())
    except ValueError:
        return f"'{application_id}' is not a valid application number."

    status = str(new_status).strip().lower()
    if not status:
        return ("Which status should it move to? One of: "
                + ", ".join(sorted(rules.STATUSES)) + ".")
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
def submit_loan_application(applicant_id: str, loan_type: str = "",
                            amount_requested: str = "", tenure_months: str = "",
                            purpose: str = "") -> str:
    """Use this to submit a brand new loan application for an existing applicant.
    loan_type must be personal, home, or auto. amount_requested is in rupees and
    tenure_months is the loan term. This asks the person to confirm before it
    takes effect. Do not use this to change an application that already exists."""
    blob = _unpack(applicant_id, ("applicant_id", "loan_type", "amount_requested",
                                  "tenure_months", "purpose"))
    if blob:
        applicant_id, loan_type = blob["applicant_id"], blob["loan_type"]
        amount_requested, tenure_months = blob["amount_requested"], blob["tenure_months"]
        purpose = blob["purpose"]

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
        # The amount is formatted the way the rest of the app formats money.
        # This sentence is the last thing a person reads before agreeing to
        # create a real record, so it must not be the one place in the product
        # that writes rupees differently (T-96).
        f"About to create a new {kind} loan application for applicant "
        f"{arguments['applicant_id']}: {format_rupees(arguments['amount_requested'])} "
        f"over {arguments['tenure_months']} months.",
    )


@tool
def upload_document_metadata(application_id: str, doc_type: str = "",
                             file_name: str = "") -> str:
    """Use this to record that a document has been received for a loan application.
    doc_type must be one of: id_proof, income_proof, bank_statement, property_docs,
    employment_letter. This asks the person to confirm before it takes effect."""
    blob = _unpack(application_id, ("application_id", "doc_type", "file_name"))
    if blob:
        application_id, doc_type, file_name = (
            blob["application_id"], blob["doc_type"], blob["file_name"])

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
