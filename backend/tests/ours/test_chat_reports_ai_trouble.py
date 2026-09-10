"""
When the AI misbehaves, the chat says which way it misbehaved (Piece 23, D-20).

Two things are being protected here.

The first is that a person gets told something specific. "The online AI has
reached today's limit, so a local model answered" tells them why the next answer
is shorter; a bare "something went wrong" leaves them thinking the product is
broken.

The second matters more and is easy to lose in a refactor: **a failing AI must
never turn into a 500.** Before this, if the agent failed and the manual chain
failed too, the exception escaped and the customer got a blank error page. The
chat is one screen in a working app — everything else still functions, and it
should say so.

Every failure here is faked, so this file costs no quota and needs no network.
"""

import pytest

import llm_provider
from app.routers import chat as chat_router


def _ask(client, token, message="Anything at all"):
    return client.post("/api/v1/chat", json={"message": message},
                       headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def broken_agent(monkeypatch):
    """The agent always fails. What it raises is chosen per test."""
    def _break_with(exc):
        def fake_run_agent(question, executor=None):
            raise exc

        import agent.agent as agent_module
        monkeypatch.setattr(agent_module, "run_agent", fake_run_agent)
        monkeypatch.setattr(chat_router, "get_agent", lambda: None)

    return _break_with


@pytest.fixture
def working_manual(monkeypatch):
    """The Phase 2 manual chain still answers, as it would on a spent quota."""
    monkeypatch.setattr(chat_router, "_answer_with_rag",
                        lambda q: ("The manual says six documents.", []))


@pytest.fixture
def broken_manual(monkeypatch):
    """The manual chain fails too — both brains down."""
    def fails(question):
        raise RuntimeError("Connection refused to http://localhost:11434")

    monkeypatch.setattr(chat_router, "_answer_with_rag", fails)


def test_a_normal_answer_says_nothing_at_all(client, auth_token, monkeypatch):
    """
    The quiet case, and the one that must stay quiet. A notice on every healthy
    answer would train people to ignore it, and then it is worthless on the day
    it matters.
    """
    def fine(question, executor=None):
        return {"output": "All good.", "intermediate_steps": []}

    import agent.agent as agent_module
    monkeypatch.setattr(agent_module, "run_agent", fine)
    monkeypatch.setattr(chat_router, "get_agent", lambda: None)
    monkeypatch.setattr(chat_router, "_policy_sources", lambda calls: [])

    body = _ask(client, auth_token).json()
    assert body["ai_status"] == "ai_ok"
    assert body["ai_notice"] == ""


def test_a_spent_quota_is_named_as_a_spent_quota(client, auth_token,
                                                  broken_agent, working_manual):
    """The demo case: Gemini's daily cap runs out and something else answers."""
    broken_agent(RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))

    body = _ask(client, auth_token).json()
    assert body["ai_status"] == llm_provider.AI_QUOTA_EXHAUSTED
    assert "limit" in body["ai_notice"].lower()
    # The question was still answered. That is the point of the fallback.
    assert body["answer"] == "The manual says six documents."


def test_a_bad_key_is_not_reported_as_a_spent_quota(client, auth_token,
                                                     broken_agent, working_manual):
    """
    These need different actions from us — one waits until tomorrow, the other
    is a typo to fix now — so they must not share a message.
    """
    broken_agent(RuntimeError("400 API key not valid. Please pass a valid API key."))

    body = _ask(client, auth_token).json()
    assert body["ai_status"] == llm_provider.AI_KEY_INVALID


def test_everything_down_still_answers_200_and_explains(client, auth_token,
                                                         broken_agent, broken_manual):
    """
    The one that stops a demo dying. Both brains fail; the person still gets a
    real reply that says what is wrong, not a 500.
    """
    broken_agent(RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))

    response = _ask(client, auth_token)
    assert response.status_code == 200

    body = response.json()
    assert body["mode"] == "unavailable"
    assert body["ai_status"] == llm_provider.AI_LOCAL_NOT_RUNNING
    assert body["answer"]           # there is something to read
    assert "local model is not running" in body["answer"].lower()


def test_the_same_sentence_is_never_shown_twice(client, auth_token,
                                                 broken_agent, broken_manual):
    """
    When every brain is down the answer *is* the explanation, so repeating it
    in the notice above would read as a glitch rather than as care.
    """
    broken_agent(RuntimeError("429 RESOURCE_EXHAUSTED"))

    body = _ask(client, auth_token).json()
    assert body["ai_notice"] == ""
    assert body["answer"]


def test_an_empty_question_is_not_treated_as_a_failure(client, auth_token):
    """Nothing was asked, so nothing went wrong — the notice stays quiet."""
    body = _ask(client, auth_token, "   ").json()
    assert body["mode"] == "empty"
    assert body["ai_status"] == "ai_ok"
    assert body["ai_notice"] == ""


def test_the_code_is_written_to_the_activity_log(client, auth_token,
                                                  broken_agent, working_manual):
    """
    Worth recording: a run of these in the log is how we find out a key died
    quietly yesterday, rather than hearing it from whoever was demoing.

    Read straight from the table rather than through `/activity`, which is
    manager-only — borrowing a manager's token here would be testing the log's
    permissions rather than what the chat wrote into it.
    """
    import json

    from app.models.activity_log import ActivityLog
    from tests.conftest import TestingSessionLocal

    broken_agent(RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))
    _ask(client, auth_token)

    session = TestingSessionLocal()
    try:
        row = (session.query(ActivityLog)
               .filter(ActivityLog.action == "chat_message")
               .order_by(ActivityLog.id.desc())
               .first())
        details = json.loads(row.details) if row else None
    finally:
        session.close()

    assert row is not None
    assert details["ai_status"] == llm_provider.AI_QUOTA_EXHAUSTED
