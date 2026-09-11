"""
The five tools the agent can call.

Four read live data from the Phase 1 API over plain HTTP, exactly the way a
browser would; the fifth calls Phase 2's RAG chain directly, in the same
process. **Every description below is written like an instruction, not
documentation** — "use this when… do not use this for…" — because that text is
the only thing the model reads when deciding which tool fits a question
(blueprint Part 8's warning). A vague description means a wrong tool gets
called and the agent looks stupid even though its code was perfectly capable.

Three failure paths are deliberately handled as **text, not exceptions**,
because the trainer's `TC-01-P3-EXEC-05/06` and the error-handling section of
the blueprint both require it:

  * a bad application ID       -> the sentence "Application not found."
  * the Phase 1 API is down    -> a plain sentence saying so
  * a filter matches nothing   -> "No applications found matching the criteria."

An agent that raises an exception on any of these stops the whole
conversation. One that returns a sentence lets the agent keep reasoning and
tell the person what happened.

`API_BASE_URL` is read from `os.environ` directly, not through the pydantic
settings object, because `TC-01-P3-EXEC-06` patches the environment variable
and reloads this module to prove the tools notice a different address:

    monkeypatch.setenv("API_BASE_URL", "http://localhost:9999/api/v1")
    importlib.reload(tools)
"""

from __future__ import annotations

import time
from datetime import datetime

import structlog
from langchain_core.tools import tool

from app.services.loan_api_client import API_BASE_URL, api_get  # noqa: F401
from app.utils.finance import format_rupees
from app.utils.otel_config import get_tracer

logger = structlog.get_logger()

# `API_BASE_URL` is re-exported above so that the trainer's TC-01-P3-EXEC-06 —
# which patches the environment variable and reloads this module — still sees
# the value it expects on this module. The HTTP work itself lives in
# app/services/loan_api_client.py, shared with Phase 4's MCP tools and Phase 5's
# data collector, so there is one definition of "call the loan API" rather than
# three that drift apart.


def _call_tool_span(tool_name: str, input_repr: str, fn):
    """Wraps a tool body in the `agent.tool_call` span the observability guide asks for."""
    tracer = get_tracer()
    started = time.perf_counter()
    with tracer.start_as_current_span("agent.tool_call") as span:
        span.set_attribute("agent.tool_name", tool_name)
        span.set_attribute("agent.tool_input", input_repr[:200])
        result = fn()
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        span.set_attribute("agent.output_length", len(result))
        span.set_attribute("agent.duration_ms", duration_ms)
        logger.info("agent_tool_called", operation="tool_call", tool=tool_name,
                    input=input_repr[:200], output_length=len(result),
                    duration_ms=duration_ms)
        return result


def _readable(value) -> str:
    """
    A stored enum as a person would say it: `under_review` -> "under review".

    Everything these tools return is read twice — once by the model, which
    reasons over it, and then by whoever is reading the chat, because the model
    echoes what it was given. Handing it `id_proof` is how "id_proof" ends up in
    a sentence addressed to a loan officer (T-96).
    """
    return str(value).replace("_", " ") if value is not None else "not recorded"


def _readable_time(value) -> str:
    """
    A stored timestamp as a date a person can read.

    The API sends UTC with a `Z`, which is right for a browser that converts it
    but wrong for a model: handed `2026-09-05T20:13:55Z` it will read the UTC
    wall clock aloud as though it were local, which is the 5.5-hour bug
    returning through a door `UtcDateTime` cannot guard (T-97).

    The date is what anyone actually asks about here — "when was it submitted" —
    so the time of day is dropped rather than converted, which would need a
    timezone this layer has no business deciding.
    """
    if not value:
        return "not recorded"
    try:
        cleaned = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return str(value)


def _summarize_if_long(text: str) -> str:
    """
    Condense a tool's own output before it goes back to the agent, if it is
    long enough to matter. Kept as its own function — not inlined into every
    tool — because `TC-01-P3-CTX-03` imports it directly to prove a short
    string comes back completely unchanged.
    """
    from agent.summarizer import SUMMARIZE_ABOVE_CHARS, summarize_text

    if len(text) <= SUMMARIZE_ABOVE_CHARS:
        return text
    return summarize_text(text)


# ---------------------------------------------------------------------------
# The five tools
# ---------------------------------------------------------------------------

@tool
def get_application_details(application_id: str) -> str:
    """Use this when the user asks about ONE specific loan application by its
    number, for example "what is the status of application 5?" or "tell me
    about application 12". Do not use this for questions about several
    applications, or about a person rather than a loan. Give it just the
    number, as a string, such as "5"."""
    def run():
        ok, data = api_get(f"/applications/{application_id}")
        if not ok:
            if data == "not found":
                return "Application not found."
            return data
        lines = [
            f"Application ID: {data['id']}",
            f"Loan Type: {_readable(data['loan_type'])}",
            f"Status: {_readable(data['status'])}",
            f"Amount Requested: {format_rupees(data['amount_requested'])}",
            f"Tenure: {data['tenure_months']} months",
            f"Purpose: {data.get('purpose', 'not given')}",
            f"Submitted: {_readable_time(data.get('submitted_at'))}",
        ]
        if data.get("applicant"):
            lines.append(f"Applicant: {data['applicant'].get('name', 'unknown')}")
        return _summarize_if_long("\n".join(lines))

    return _call_tool_span("get_application_details", application_id, run)


@tool
def list_applications(status: str = "", loan_type: str = "") -> str:
    """Use this when the user asks about SEVERAL applications at once, or
    about the pipeline in general — "how many are pending review?", "show me
    rejected home loans", "list all under review". Both arguments are
    optional; leave one blank to not filter by it. Do not use this for a
    single application by number, use get_application_details for that."""
    def run():
        params = {}
        if status:
            params["status"] = status
        if loan_type:
            params["loan_type"] = loan_type
        ok, data = api_get("/applications", params=params)
        if not ok:
            return data
        items = data.get("items", [])
        if not items:
            return "No applications found matching the criteria."
        lines = [f"Found {data.get('total_count', len(items))} application(s):"]
        for item in items[:20]:
            lines.append(
                f"- Application {item['id']}: {_readable(item['loan_type'])}, "
                f"{format_rupees(item['amount_requested'])}, "
                f"status {_readable(item['status'])}"
            )
        return _summarize_if_long("\n".join(lines))

    return _call_tool_span("list_applications", f"status={status},loan_type={loan_type}", run)


@tool
def get_dashboard_summary() -> str:
    """Use this when the user asks a general "how many / what's the overall
    picture" question about the whole branch — totals, counts by status, or
    the total amount requested. Do not use this for a question about one
    specific application or applicant."""
    def run():
        ok, data = api_get("/dashboard/summary")
        if not ok:
            return data
        lines = [
            "Dashboard Summary:",
            f"Total Applications: {data.get('total_applications', 0)}",
            f"Pending Review: {data.get('pending_review', 0)}",
            f"Total Amount Requested: {format_rupees(data.get('total_amount_requested', 0))}",
            f"Approved Amount (not yet disbursed): {format_rupees(data.get('approved_amount', 0))}",
        ]
        by_status = data.get("by_status") or {}
        if by_status:
            lines.append("By status: " + ", ".join(
                f"{_readable(k)}: {v}" for k, v in by_status.items()))
        by_type = data.get("by_loan_type") or {}
        if by_type:
            lines.append("By loan type: " + ", ".join(
                f"{_readable(k)}: {v}" for k, v in by_type.items()))
        return _summarize_if_long("\n".join(lines))

    return _call_tool_span("get_dashboard_summary", "{}", run)


@tool
def search_loan_policy(query: str) -> str:
    """Use this for any question about the BANK'S POLICY rather than a
    specific application: eligibility rules, required documents, interest
    rates, fees, processing times, or how the loan process works. This is
    the only tool that knows the content of the bank's user manual. Do not
    use this for questions about a specific application's status."""
    def run():
        from rag.rag_chain import answer_policy_question

        return _summarize_if_long(answer_policy_question(query))

    return _call_tool_span("search_loan_policy", query, run)


@tool
def get_applicant_details(applicant_id: str) -> str:
    """Use this when the user asks about a PERSON — their income, employment
    status, or credit score — rather than about a specific loan application.
    Give it the applicant's number, as a string. Do not use this for
    questions about an application's status, use get_application_details for
    that."""
    def run():
        ok, data = api_get(f"/applicants/{applicant_id}")
        if not ok:
            if data == "not found":
                return "Applicant not found."
            return data
        lines = [
            f"Applicant ID: {data['id']}",
            f"Name: {data['name']}",
            f"Employment: {_readable(data.get('employment_status'))}",
            f"Annual Income: {format_rupees(data.get('annual_income', 0))}",
        ]
        credit = data.get("credit_score")
        # The scale is stated because CIBIL runs 300-900, and a model given a
        # bare "750" may read it against a 0-100 or an American scale and call
        # a good score mediocre (T-96).
        lines.append(f"CIBIL Score: {credit} out of 900" if credit is not None
                     else "CIBIL Score: not provided")
        return _summarize_if_long("\n".join(lines))

    return _call_tool_span("get_applicant_details", applicant_id, run)


ALL_TOOLS = [
    get_application_details,
    list_applications,
    get_dashboard_summary,
    search_loan_policy,
    get_applicant_details,
]
