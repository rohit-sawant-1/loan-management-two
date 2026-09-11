"""
The staff chat interface: a Streamlit screen where a loan officer or manager
manages applications by typing sentences instead of filling in forms.

Two halves live in this one file, on purpose:

  1. The logic — `build_executor()`, `process_message()`, and `MCP_TOOLS` —
     is what `tests/phase4/` imports directly, the same way Phase 3's tests
     import `agent.agent`. It has no Streamlit calls in it, so importing this
     module for a test never touches the UI.
  2. The Streamlit screen itself is built inside `main()`, called only when
     this file is run as a script (`streamlit run mcp_server/chat_interface.py`).
     `streamlit run` executes a script as `__main__`, the same as any other
     Python entry point, so the `if __name__ == "__main__":` guard below
     works for both cases: a real `streamlit run` still calls `main()`, and a
     plain `import mcp_server.chat_interface` from a test never does.

The six tools the agent can call are the same six MCP tools in `mcp_app.py`,
wrapped as LangChain tools here so a ReAct agent — the same shape Phase 3
uses — can reason about which one to call. `mcp.tool()` in fastmcp leaves the
underlying function directly callable (that is what lets `mcp_app.py`'s own
tests call `get_application_details(application_id=1)` as a plain function),
so wrapping them again here with LangChain's `@tool` costs nothing extra.
"""

from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# `streamlit run mcp_server/chat_interface.py` puts THIS file's folder
# (backend/mcp_server) first on Python's import path — not backend/. So
# `import app` looks inside mcp_server/, finds no `app` package there, and
# the page dies with "ModuleNotFoundError: No module named 'app'" the moment
# a browser connects. The server still starts and still answers 200, because
# that 200 is only the empty page shell; the script itself is not run until
# someone opens it. That is why every check that imported this module from a
# process already started in backend/ — pytest, Streamlit's AppTest — passed
# while the actual command a person types failed (T-74).
#
# Adding backend/ to the path here fixes it wherever the file is launched
# from, rather than relying on the person being in the right folder.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import structlog                                                      # noqa: E402
from langchain_classic.agents import AgentExecutor, create_react_agent  # noqa: E402
from langchain_core.prompts import PromptTemplate                     # noqa: E402
from langchain_core.tools import tool                                 # noqa: E402

from app.utils.finance import format_rupees                          # noqa: E402
from app.utils.logging_config import configure_logging               # noqa: E402
from app.utils.otel_config import get_tracer, setup_telemetry        # noqa: E402
from llm_provider import enable_langsmith, get_llm                   # noqa: E402
from mcp_server import mcp_app                                       # noqa: E402

logger = structlog.get_logger()

LANGSMITH_PROJECT = "AI-Readiness-POC-01-P4"
MAX_ITERATIONS = 8

CHAT_SYSTEM_PROMPT = """You are a professional Loan Management Assistant for a bank's staff \
(loan officers and branch managers). Help them manage loan applications through natural \
language instead of forms.

You have six tools. Choose carefully between them:

- Use submit_loan_application to create a brand new application for an existing applicant.
- Use get_application_details when the question names ONE specific application by number.
- Use update_application_status to move an application to a new status (under_review, \
approved, rejected, or disbursed) — always pass the reason given as remarks.
- Use list_applications_by_filter for questions about several applications at once, or the \
pipeline in general — "show me pending applications", "list rejected home loans".
- Use get_dashboard_summary for the overall picture — totals, counts by status, the branch \
as a whole.
- Use upload_document_metadata to record that a document has been uploaded for an application.

Rules you must follow, without exception:
- update_application_status changes a real record and some moves (rejected, disbursed) can \
never be undone. If the person's instruction already names the application, the new status \
and a reason, act on it directly — that is what they asked for. If it is vague or you are \
not sure what they mean, ask a clarifying question instead of guessing and calling the tool.
- Never invent an application ID, an amount, a status, or a number a tool did not give you. \
If a tool returns an error, say so plainly rather than making something up.
- Use tools to perform actual operations — never simulate or make up what a tool would return.
- Be professional and concise. Show the real data a tool returned, not a paraphrase of what \
you assume it contains.

You reason step by step, using the tools available to you, before giving your final answer."""

REACT_TEMPLATE = CHAT_SYSTEM_PROMPT + """

You have access to the following tools:

{tools}

Use the following format exactly:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


# Keys whose values are money. Named explicitly rather than guessed from the
# name, so a new field is formatted deliberately or not at all.
_MONEY_KEYS = {"amount_requested", "amount", "annual_income", "monthly_income",
               "total_amount_requested", "approved_amount", "emi_amount"}

_DATE_KEYS = {"submitted_at", "created_at", "updated_at", "decided_at",
              "uploaded_at", "verified_at", "disbursed_at"}


def _format_value(key: str, value) -> str:
    """
    One field of a tool's answer, in a shape both the model and a person can
    read.

    This function is where two of this project's real bugs met. Before it, every
    field went to the model as `key: repr(value)` — so an amount arrived as a
    bare `4000000.0` (which is how the AI came to write dollars, T-94), a
    timestamp as a raw UTC string, an enum as `under_review`, and a nested dict
    as Python's `{'name': 'Priya'}`. The model repeats what it is given, so all
    of that reached whoever was reading the chat.
    """
    if value is None or value == "":
        return "not recorded"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if key in _MONEY_KEYS:
        try:
            return format_rupees(float(value))
        except (TypeError, ValueError):
            return str(value)
    if key in _DATE_KEYS:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d %b %Y")
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, list):
        if not value:
            return "none"
        # A list of records — documents, history entries — is summarised rather
        # than dumped, because `repr` of a dict is not something to show anyone.
        if isinstance(value[0], dict):
            return f"{len(value)} item(s)"
        return ", ".join(str(v).replace("_", " ") for v in value)
    if isinstance(value, dict):
        name = value.get("name") or value.get("id")
        return str(name) if name is not None else f"{len(value)} field(s)"
    if isinstance(value, str):
        return value.replace("_", " ")
    return str(value)


def _format_dict(data: dict) -> str:
    """A tool's raw dict, as a short readable observation for the agent to reason over."""
    if "error" in data:
        return f"Error: {data.get('detail', data['error'])}"
    return "\n".join(f"{key.replace('_', ' ')}: {_format_value(key, value)}"
                     for key, value in data.items())


# ---------------------------------------------------------------------------
# The six tools, as LangChain tools wrapping the six MCP tools above.
# ---------------------------------------------------------------------------

@tool
def submit_loan_application(applicant_id: int, loan_type: str, amount_requested: float,
                             tenure_months: int, purpose: str) -> str:
    """Use this to submit a brand new loan application for an existing applicant.
    loan_type must be one of: personal, home, auto. amount_requested is in rupees.
    tenure_months is the loan term in months. Do not use this to change an
    existing application - use update_application_status for that."""
    return _format_dict(mcp_app.submit_loan_application(
        applicant_id=applicant_id, loan_type=loan_type,
        amount_requested=amount_requested, tenure_months=tenure_months, purpose=purpose,
    ))


@tool
def get_application_details(application_id: str) -> str:
    """Use this when the user asks about ONE specific loan application by its number,
    such as "show me application 5" or "what is the status of application 12". Give it
    just the number, as a string, such as "5". Do not use this for a list of several
    applications, use list_applications_by_filter for that.

    A single-argument tool like this one is a known rough edge in the ReAct format
    this agent uses: when a tool takes exactly one field, LangChain sometimes hands
    the whole "Action Input" line through as a raw string rather than parsing it as
    JSON, which breaks instantly against an `int` parameter. Taking a string and
    converting it here is the same fix Phase 3's tools.py uses for exactly this
    tool, for exactly this reason."""
    try:
        app_id = int(str(application_id).strip())
    except ValueError:
        return f"Error: '{application_id}' is not a valid application number."
    return _format_dict(mcp_app.get_application_details(application_id=app_id))


@tool
def update_application_status(application_id: int, new_status: str, remarks: str) -> str:
    """Use this to move a loan application to a new status: under_review, approved,
    rejected, or disbursed. remarks is required and is recorded in the audit trail -
    always include the reason the user gave you. Do not use this to create a new
    application, use submit_loan_application for that."""
    return _format_dict(mcp_app.update_application_status(
        application_id=application_id, new_status=new_status, remarks=remarks,
    ))


@tool
def list_applications_by_filter(status: str = "", loan_type: str = "",
                                 page: int = 1, limit: int = 10) -> str:
    """Use this when the user asks about SEVERAL applications at once, or the pipeline
    in general - "show all pending applications", "list rejected home loans". Both
    status and loan_type are optional; leave either blank to not filter by it. Do not
    use this for one specific application by number, use get_application_details for that."""
    return _format_dict(mcp_app.list_applications_by_filter(
        status=status, loan_type=loan_type, page=page, limit=limit,
    ))


@tool
def get_dashboard_summary() -> str:
    """Use this when the user asks a general "how many / what's the overall picture"
    question about the whole branch - totals, counts by status, or the total amount
    requested. Do not use this for a question about one specific application."""
    return _format_dict(mcp_app.get_dashboard_summary())


@tool
def upload_document_metadata(application_id: int, doc_type: str, file_name: str) -> str:
    """Use this to record that a document has been uploaded for a loan application.
    doc_type must be one of: id_proof, income_proof, bank_statement, property_docs,
    employment_letter. Do not use this for any other kind of update to an application."""
    return _format_dict(mcp_app.upload_document_metadata(
        application_id=application_id, doc_type=doc_type, file_name=file_name,
    ))


MCP_TOOLS = [
    submit_loan_application, get_application_details, update_application_status,
    list_applications_by_filter, get_dashboard_summary, upload_document_metadata,
]


# ---------------------------------------------------------------------------
# The logic tests/phase4 imports directly
# ---------------------------------------------------------------------------

def build_executor() -> AgentExecutor:
    """Build the chat agent. Same ReAct shape as Phase 3's agent, six tools instead of five."""
    configure_logging()
    setup_telemetry()
    enable_langsmith(LANGSMITH_PROJECT)

    llm = get_llm(temperature=0)
    prompt = PromptTemplate.from_template(REACT_TEMPLATE)
    agent = create_react_agent(llm, MCP_TOOLS, prompt)

    return AgentExecutor(
        agent=agent,
        tools=MCP_TOOLS,
        max_iterations=MAX_ITERATIONS,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


def process_message(message: str, session_id: str, executor: AgentExecutor) -> dict:
    """
    Ask the agent one message, tagged with the session so LangSmith can group
    every trace from one conversation together (US-01-P4-05).

    An empty message is handled here rather than sent to the model: there is
    nothing to reason about, and Phase 2 already found that asking an LLM
    about an empty string can fail outright (T-56) rather than answer
    sensibly. `TC-01-P4-CHAT-06` sends exactly this case and expects a normal
    result, not a crash.
    """
    log = logger.bind(poc_id="POC-01", phase=4, session_id=session_id)
    log.info("chat_message_received", operation="chat_message", message_length=len(message))
    started = time.perf_counter()

    if not message.strip():
        result = {"output": "I didn't receive a question — please type what you'd like help with.",
                  "intermediate_steps": []}
    else:
        tracer = get_tracer()
        with tracer.start_as_current_span("mcp.response") as span:
            span.set_attribute("session_id", session_id)
            result = executor.invoke(
                {"input": message},
                config={
                    "metadata": {"poc_id": "POC-01", "phase": 4, "session_id": session_id},
                    "tags": [f"session:{session_id}"],
                },
            )
            span.set_attribute("mcp.tool_calls_count", len(result.get("intermediate_steps", [])))

    duration_ms = int((time.perf_counter() - started) * 1000)
    log.info("chat_message_processed", operation="chat_message",
              response_length=len(result.get("output", "")),
              tool_calls_count=len(result.get("intermediate_steps", [])),
              duration_ms=duration_ms)
    return result


# ---------------------------------------------------------------------------
# The Streamlit screen. Only runs under `streamlit run`, never on import.
# ---------------------------------------------------------------------------

def _render_tool_calls(st, tool_calls: list) -> None:
    with st.expander(f"🔧 Tools used ({len(tool_calls)})"):
        for tool_name, tool_input in tool_calls:
            st.write(f"**{tool_name}**")
            st.json(tool_input if isinstance(tool_input, dict) else {"input": str(tool_input)})


def _handle_user_message(st, prompt: str) -> None:
    """
    Append the user's message, run it through the agent, and append the
    reply — the one path both the chat box and the sidebar's quick-action
    buttons go through.

    Earlier this only existed inline under `st.chat_input`, so a quick-action
    button appended a user bubble and reran the page without ever calling
    `process_message` — it looked like asking a question, but nothing
    answered. Found by actually driving the app end to end with Streamlit's
    own `AppTest`, not by reading the code, which is exactly the kind of gap
    a passing test suite does not catch on its own.
    """
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Working on it…"):
            result = process_message(prompt, st.session_state.session_id, st.session_state.executor)

        response_text = result.get("output") or "I couldn't process that request."
        st.markdown(response_text)

        tool_calls = [(action.tool, action.tool_input)
                      for action, _ in result.get("intermediate_steps", [])]
        if tool_calls:
            _render_tool_calls(st, tool_calls)

        st.session_state.messages.append({
            "role": "assistant", "content": response_text, "tool_calls": tool_calls,
        })


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Loan Management Chat", page_icon="🏦", layout="wide")
    st.title("🏦 Loan Management Assistant")
    st.caption("For bank staff — manage loan applications through natural language, "
               "the same six operations as the API, over MCP.")

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.session_state.executor = build_executor()

    with st.sidebar:
        st.header("Session")
        st.code(f"Session: {st.session_state.session_id}")
        st.caption("A new session starts on every page refresh, by design (US-01-P4-04).")
        st.divider()
        st.header("Quick actions")
        clicked_action = None
        for action in [
            "Show all pending applications",
            "Give me the dashboard summary",
            "List all home loan applications",
            "Show details of application 1",
        ]:
            if st.button(action, use_container_width=True):
                clicked_action = action

    # Replay the conversation so far before handling anything new this run.
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                _render_tool_calls(st, msg["tool_calls"])

    typed_prompt = st.chat_input("Type your request…")

    # A quick-action click and the chat box both end up here; the chat box
    # is checked second so a click is never silently overwritten by a stale
    # widget value from the same rerun.
    prompt = clicked_action or typed_prompt
    if prompt:
        _handle_user_message(st, prompt)


if __name__ == "__main__":
    main()
