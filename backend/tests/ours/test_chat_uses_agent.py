"""
The chat endpoint routes to the Phase 3 agent, and does it as the person
asking (Piece 22, step 2).

No real AI call happens here. `run_agent` is replaced with a stand-in that
records who it was told it is, which is the thing worth proving: the answer
text is Phase 3's job and is already tested there, but *whose identity the
tools run under* is what stops one customer seeing another's loan.
"""

import pytest

from jose import jwt          # the same library the app itself signs with (T-88)

from app.config import settings
from app.routers import chat as chat_router
from app.services.loan_api_client import service_token


class _FakeAction:
    """Stands in for LangChain's AgentAction — the tool name and its input."""
    def __init__(self, tool, tool_input):
        self.tool = tool
        self.tool_input = tool_input


@pytest.fixture
def fake_agent(monkeypatch):
    """
    Replace the agent with a stand-in that reports the identity it ran under.

    `seen` collects the JWT claims that `service_token()` produced during the
    call, which is exactly what the real tools would have sent to the API.
    """
    seen = {}

    def fake_run_agent(question, executor=None):
        token = service_token()
        seen["claims"] = jwt.decode(token, settings.secret_key,
                                    algorithms=[settings.jwt_algorithm])
        seen["question"] = question
        return {
            "output": "Home loans need six documents.",
            "intermediate_steps": [
                (_FakeAction("search_loan_policy", "home loan documents"),
                 "the observation"),
            ],
        }

    import agent.agent as agent_module
    monkeypatch.setattr(agent_module, "run_agent", fake_run_agent)
    # The endpoint builds the agent on first use; a stand-in needs no building.
    monkeypatch.setattr(chat_router, "get_agent", lambda role=None: None)
    # Sources come from the vector store, which we are not exercising here.
    monkeypatch.setattr(chat_router, "_policy_sources", lambda calls: [])
    return seen


def _ask(client, token, message):
    return client.post("/api/v1/chat", json={"message": message},
                       headers={"Authorization": f"Bearer {token}"})


def test_chat_now_answers_as_the_agent(client, auth_token, fake_agent):
    """The brain behind the chat door is the agent, not the bare RAG chain."""
    response = _ask(client, auth_token, "What documents does a home loan need?")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "agent"
    assert body["answer"] == "Home loans need six documents."


def test_the_reply_says_which_tools_ran(client, auth_token, fake_agent):
    """The screen needs this to show how the answer was worked out."""
    body = _ask(client, auth_token, "What documents does a home loan need?").json()

    assert [t["tool"] for t in body["tools_used"]] == ["search_loan_policy"]
    assert body["tools_used"][0]["tool_input"] == "home loan documents"


def test_the_agent_runs_as_the_person_who_asked(client, auth_token, fake_agent):
    """
    The whole point of step 1, now proved through the endpoint: the officer
    who typed the question is who the tools call the API as.
    """
    _ask(client, auth_token, "List submitted applications")

    assert fake_agent["claims"]["sub"] == "officer@test.com"
    assert fake_agent["claims"]["role"] == "loan_officer"


def test_a_customer_is_not_promoted_by_asking(client, fake_agent):
    """A customer's chat must never run with a staff identity."""
    client.post("/api/v1/auth/register-applicant", json={
        "name": "Chat Customer", "email": "chatcustomer@test.com",
        "password": "Test@1234", "phone": "9876500011",
        "annual_income": 500000.0, "employment_status": "salaried",
    })
    token = client.post("/api/v1/auth/login", json={
        "email": "chatcustomer@test.com", "password": "Test@1234"
    }).json()["access_token"]

    _ask(client, token, "Show me application 5")

    assert fake_agent["claims"]["sub"] == "chatcustomer@test.com"
    assert fake_agent["claims"]["role"] == "applicant"


def test_an_empty_message_never_reaches_the_agent(client, auth_token, fake_agent):
    """Blank input is answered on the spot, without spending an AI call."""
    body = _ask(client, auth_token, "   ").json()

    assert body["mode"] == "empty"
    assert "claims" not in fake_agent


def test_a_broken_agent_falls_back_to_the_manual(client, auth_token, monkeypatch):
    """
    If the agent cannot run — rate-limited, or its loop gives up — the person
    still gets an answer from the manual, and `mode` says so honestly.
    """
    import agent.agent as agent_module

    def boom(question, executor=None):
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr(agent_module, "run_agent", boom)
    monkeypatch.setattr(chat_router, "get_agent", lambda role=None: None)
    monkeypatch.setattr(chat_router, "_answer_with_rag",
                        lambda q: ("From the manual.", []))

    body = _ask(client, auth_token, "What is the interest rate?").json()

    assert body["mode"] == "rag"
    assert body["answer"] == "From the manual."
    assert body["tools_used"] == []


def test_langchains_retry_marker_is_not_shown_as_a_tool(client, auth_token, monkeypatch):
    """
    When the model writes a malformed step, LangChain records a step called
    `_Exception` and asks it to try again. That is a real thing that happened,
    but it is not something the assistant *did* — showing it in a customer's
    "how this was worked out" list reads as a crash. Seen live on a customer's
    refused request, so it is not hypothetical (T-77).
    """
    import agent.agent as agent_module

    def run(question, executor=None):
        return {
            "output": "You can only view your own applications.",
            "intermediate_steps": [
                (_FakeAction("get_application_details", "3"), "403"),
                (_FakeAction("_Exception", "Invalid Format"), "retry"),
            ],
        }

    monkeypatch.setattr(agent_module, "run_agent", run)
    monkeypatch.setattr(chat_router, "get_agent", lambda role=None: None)
    monkeypatch.setattr(chat_router, "_policy_sources", lambda calls: [])

    body = _ask(client, auth_token, "Show me application 3").json()

    assert [t["tool"] for t in body["tools_used"]] == ["get_application_details"]

