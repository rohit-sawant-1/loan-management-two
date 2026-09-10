"""
Phase 4's record-changing tools in the chat: staff only, and never without a yes.

The security tests come first here, because they are the ones whose failure
matters. A customer must not be able to change a record by asking nicely, and
nothing at all may change on a single message — the person has to see what is
about to happen and agree to it.

Nothing here calls a real AI. The agent is replaced by a stand-in that calls
whichever tool the test wants, which is the same thing a real model would do
after reasoning, minus the quota.
"""

import pytest

from agent import agent as agent_module
from agent.write_tools import WRITE_TOOLS
from app.routers import chat as chat_router
from app.services import pending_actions


def _ask(client, token, message):
    return client.post("/api/v1/chat", json={"message": message},
                       headers={"Authorization": f"Bearer {token}"})


@pytest.fixture(autouse=True)
def clean_slate():
    """No pending action leaks between tests."""
    pending_actions._pending.clear()
    chat_router._agents.clear()
    yield
    pending_actions._pending.clear()
    chat_router._agents.clear()


@pytest.fixture
def customer_token(client):
    client.post("/api/v1/auth/register-applicant", json={
        "name": "Write Customer", "email": "writecustomer@test.com",
        "password": "Test@1234", "phone": "9876500022",
        "annual_income": 500000.0, "employment_status": "salaried",
    })
    return client.post("/api/v1/auth/login", json={
        "email": "writecustomer@test.com", "password": "Test@1234",
    }).json()["access_token"]


@pytest.fixture
def agent_calls(monkeypatch):
    """
    Replace the agent with one that calls a tool we choose, by name.

    This is what a real model does once it has decided — it invokes the tool.
    Skipping the deciding part is the whole saving.
    """
    def _use(tool_name, **tool_args):
        def fake_run_agent(question, executor=None):
            tool = next(t for t in WRITE_TOOLS if t.name == tool_name)
            observation = tool.invoke(tool_args)
            return {"output": observation, "intermediate_steps": []}

        monkeypatch.setattr(agent_module, "run_agent", fake_run_agent)
        monkeypatch.setattr(chat_router, "get_agent", lambda role=None: None)
        monkeypatch.setattr(chat_router, "_policy_sources", lambda calls: [])

    return _use


# ---------------------------------------------------------------------------
# Who is allowed to have these tools at all
# ---------------------------------------------------------------------------

def test_a_customer_has_no_write_tools_whatsoever():
    """
    The one that matters most. Not "the API would refuse it" — the tool is not
    in the list, so the agent has no way to even propose the change.
    """
    names = [t.name for t in agent_module.tools_for("applicant")]

    assert "update_application_status" not in names
    assert "submit_loan_application" not in names
    assert "upload_document_metadata" not in names


def test_staff_get_the_write_tools():
    for role in ("loan_officer", "branch_manager"):
        names = [t.name for t in agent_module.tools_for(role)]
        assert "update_application_status" in names, role


def test_an_officer_and_a_manager_get_the_same_tools():
    """
    Disbursement is the only difference between them, and the API already
    enforces it. A second copy of that rule here is a second thing to keep in
    step, and copies of permission rules drift.
    """
    officer = [t.name for t in agent_module.tools_for("loan_officer")]
    manager = [t.name for t in agent_module.tools_for("branch_manager")]
    assert officer == manager


def test_no_role_means_the_read_only_agent():
    """The trainer's Phase 3 tests call build_agent() with no arguments."""
    names = [t.name for t in agent_module.tools_for(None)]
    assert "update_application_status" not in names
    assert "get_application_details" in names


# ---------------------------------------------------------------------------
# Nothing changes without a yes
# ---------------------------------------------------------------------------

def test_a_change_is_proposed_not_performed(client, auth_token, agent_calls):
    """The first message must never write. It describes and waits."""
    agent_calls("update_application_status", application_id="1",
                new_status="approved", remarks="looks fine")

    body = _ask(client, auth_token, "approve application 1, looks fine").json()

    assert body["mode"] == "agent"
    # It is being held, not done.
    assert pending_actions.peek("officer@test.com") is not None


def test_the_proposal_names_the_actual_change(client, auth_token, agent_calls):
    """
    A vague "shall I proceed?" is worthless — catching a wrong application
    number is the entire reason this step exists.
    """
    agent_calls("update_application_status", application_id="7",
                new_status="rejected", remarks="income too low")
    _ask(client, auth_token, "reject application 7, income too low")

    held = pending_actions.peek("officer@test.com")
    assert "7" in held["description"]
    assert "rejected" in held["description"]
    assert "income too low" in held["description"]


def test_yes_performs_the_recorded_call_not_a_fresh_guess(client, auth_token,
                                                           agent_calls, monkeypatch):
    """
    The important one. On "yes" the model is never consulted again — the exact
    arguments recorded at proposal time are what run, so a model that
    misremembers a digit cannot disburse the wrong loan.
    """
    agent_calls("update_application_status", application_id="3",
                new_status="approved", remarks="all documents verified")
    _ask(client, auth_token, "approve application 3")

    ran = {}

    def fake_update(**kwargs):
        ran.update(kwargs)
        return {"id": 3, "status": "approved"}

    from mcp_server import mcp_app
    monkeypatch.setattr(mcp_app, "update_application_status", fake_update)

    body = _ask(client, auth_token, "yes").json()

    assert body["mode"] == "action"
    assert ran == {"application_id": 3, "new_status": "approved",
                   "remarks": "all documents verified"}
    # Used up: a second yes must not repeat it.
    assert pending_actions.peek("officer@test.com") is None


def test_saying_no_changes_nothing(client, auth_token, agent_calls):
    agent_calls("update_application_status", application_id="2",
                new_status="rejected", remarks="not eligible")
    _ask(client, auth_token, "reject application 2, not eligible")

    body = _ask(client, auth_token, "no").json()

    assert "cancelled" in body["answer"].lower()
    assert pending_actions.peek("officer@test.com") is None


def test_a_new_instruction_drops_the_old_proposal(client, auth_token, agent_calls):
    """
    Otherwise a stray "yes" minutes later lands on something the person has
    long since moved on from — exactly the accident this guards against.
    """
    agent_calls("update_application_status", application_id="4",
                new_status="rejected", remarks="first thought")
    _ask(client, auth_token, "reject application 4")

    # They change their mind and ask something else entirely.
    def fake_run_agent(question, executor=None):
        return {"output": "Application 9 is under review.", "intermediate_steps": []}

    import agent.agent as am
    original = am.run_agent
    am.run_agent = fake_run_agent
    try:
        _ask(client, auth_token, "actually, what is the status of application 9?")
    finally:
        am.run_agent = original

    assert pending_actions.peek("officer@test.com") is None


def test_an_expired_proposal_cannot_be_confirmed(client, auth_token, agent_calls,
                                                  monkeypatch):
    """An abandoned confirmation must not be completable an hour later."""
    agent_calls("update_application_status", application_id="5",
                new_status="disbursed", remarks="ready to pay out")
    _ask(client, auth_token, "disburse application 5")

    # Wind the clock past the expiry.
    held = pending_actions._pending["officer@test.com"]
    held["created_at"] -= pending_actions.EXPIRY_SECONDS + 1

    assert pending_actions.peek("officer@test.com") is None


def test_a_refusal_from_the_api_is_read_back_plainly(client, auth_token,
                                                      agent_calls, monkeypatch):
    """
    An officer confirming a disbursement gets the API's own 403. The chat is a
    different door to the same building, not a wider one.
    """
    agent_calls("update_application_status", application_id="6",
                new_status="disbursed", remarks="pay it out")
    _ask(client, auth_token, "disburse application 6")

    from mcp_server import mcp_app
    monkeypatch.setattr(mcp_app, "update_application_status",
                        lambda **kw: {"error": "api_error",
                                      "detail": "Only a branch manager can disburse a loan"})

    body = _ask(client, auth_token, "yes").json()

    assert "branch manager" in body["answer"].lower()
    assert body["mode"] == "action"


# ---------------------------------------------------------------------------
# The tools' own checking, before anything is proposed
# ---------------------------------------------------------------------------

def test_a_status_that_does_not_exist_is_refused_before_proposing():
    with pending_actions.owned_by("someone@test.com"):
        result = WRITE_TOOLS[0].invoke({
            "application_id": "1", "new_status": "banana", "remarks": "why not",
        })

    assert "not a status" in result
    assert pending_actions.peek("someone@test.com") is None


def test_a_status_change_without_a_reason_is_refused():
    """Remarks go into the audit trail, so a blank one is not acceptable."""
    with pending_actions.owned_by("someone@test.com"):
        result = WRITE_TOOLS[0].invoke({
            "application_id": "1", "new_status": "approved", "remarks": "   ",
        })

    assert "reason is required" in result.lower()
    assert pending_actions.peek("someone@test.com") is None


def test_a_word_where_a_number_belongs_is_refused():
    with pending_actions.owned_by("someone@test.com"):
        result = WRITE_TOOLS[0].invoke({
            "application_id": "the first one", "new_status": "approved",
            "remarks": "fine",
        })

    assert "not a valid application number" in result


@pytest.mark.parametrize("said, expected", [
    ("yes", True), ("YES", True), ("Yes please", True), ("go ahead", True),
    ("confirm", True), ("do it.", True),
    ("no", False), ("cancel", False), ("not that one", False),
    ("yes but change the reason", False), ("why?", False), ("", False),
])
def test_only_a_plain_yes_counts_as_agreement(said, expected):
    """
    Reading "no, not that one" as agreement would wrongly reject a loan, so
    anything not plainly affirmative is treated as a new instruction instead.
    """
    assert pending_actions.looks_like_yes(said) is expected
