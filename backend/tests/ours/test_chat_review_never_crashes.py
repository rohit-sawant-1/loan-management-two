"""
The audit, phase 3: the review path must fail to a sentence, never to a banner.

Every other AI path in this product is wrapped so it cannot raise. Phase 5's
agents fall back to deterministic summaries; the briefing falls back to the
plain figures and says so on screen. The review branch in `chat.py` was the last
one that was not: it called the graph outside any `try` and then read
`state["risk_assessment"]` and its keys directly.

That only holds while the state has exactly the shape the graph produces on a
good day. An agent raising part-way through, a network failure inside LangGraph,
or a state shape nobody predicted all escape as a 500 — which reaches a person
as a red banner across the chat, mid-demo, with a page refresh as the only way
out.

Nothing here touches a real AI. Every failure is a stand-in raising on purpose.
"""

import pytest

from app.routers import chat as chat_router
from app.services import pending_actions


def _ask(client, token, message):
    return client.post("/api/v1/chat", json={"message": message},
                       headers={"Authorization": f"Bearer {token}"})


@pytest.fixture(autouse=True)
def clean_slate():
    pending_actions._pending.clear()
    chat_router._agents.clear()
    yield
    pending_actions._pending.clear()
    chat_router._agents.clear()


@pytest.fixture
def broken_review(monkeypatch):
    """Install a graph that fails in whatever way the test asks for."""

    def _install(exception):
        def fake_evaluate(application_id):
            raise exception

        monkeypatch.setattr("multi_agent.graph.evaluate_loan_application", fake_evaluate)

    return _install


@pytest.fixture
def odd_state_review(monkeypatch):
    """Install a graph that returns successfully but with an unexpected shape."""

    def _install(state):
        monkeypatch.setattr("multi_agent.graph.evaluate_loan_application",
                            lambda application_id: state)

    return _install


# ---------------------------------------------------------------------------
# The graph blowing up

@pytest.mark.parametrize("failure", [
    KeyError("risk_assessment"),
    RuntimeError("the model connection dropped half way through"),
    ValueError("something deep in LangGraph"),
    TimeoutError("the provider accepted and never answered"),
])
def test_a_crashing_review_still_answers_with_200(client, auth_token, broken_review, failure):
    broken_review(failure)
    response = _ask(client, auth_token, "assess application 7")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"], "an empty answer is as bad as a crash"
    # The customer is told the review did not happen, not given a verdict.
    assert "could not" in body["answer"].lower()


def test_the_failure_says_the_application_was_not_changed(client, auth_token, broken_review):
    """
    The first thing a loan officer wonders after an error is whether it did
    half the job. A review only reads, so the answer can say so plainly.
    """
    broken_review(RuntimeError("boom"))
    body = _ask(client, auth_token, "assess application 7").json()
    assert "unchanged" in body["answer"].lower()


def test_a_crash_is_not_reported_as_an_AI_failure(client, auth_token, broken_review):
    """
    T-93: the amber notice is about the *model* misbehaving. Saying "the AI has
    reached today's limit" about a crash in our own code would point whoever is
    watching at completely the wrong thing.
    """
    broken_review(RuntimeError("boom"))
    body = _ask(client, auth_token, "assess application 7").json()
    assert not body.get("ai_notice")


# ---------------------------------------------------------------------------
# The graph returning something unexpected

def test_a_state_missing_its_risk_figures_still_answers(client, auth_token, odd_state_review):
    """The old code read `state["risk_assessment"]` directly. This was the KeyError."""
    odd_state_review({
        "application_id": "7",
        "final_decision": "REQUEST_MORE_INFO",
        "reasoning": "More documents are needed.",
        "messages": [],
        "errors": [],
    })
    response = _ask(client, auth_token, "assess application 7")

    assert response.status_code == 200, response.text
    answer = response.json()["answer"]
    # The part it does have is still said.
    assert "REQUEST_MORE_INFO" in answer
    assert "More documents are needed." in answer


def test_a_half_filled_risk_assessment_prints_what_it_has(client, auth_token, odd_state_review):
    """
    A missing figure costs that one line, not the whole answer — and is never
    filled in with a zero. An invented number in an underwriting review is far
    worse than a short one.
    """
    odd_state_review({
        "application_id": "7",
        "risk_assessment": {"overall_risk_score": 82.0},   # no EMI, no ratio
        "compliance_check": {},
        "final_decision": "APPROVE",
        "reasoning": "",
        "messages": [],
        "errors": [],
    })
    answer = _ask(client, auth_token, "assess application 7").json()["answer"]

    assert "82/100" in answer
    assert "Estimated EMI" not in answer     # absent, not zero
    assert "0" != answer.strip()


def test_an_empty_state_does_not_invent_a_verdict(client, auth_token, odd_state_review):
    odd_state_review({})
    response = _ask(client, auth_token, "assess application 7")

    assert response.status_code == 200, response.text
    answer = response.json()["answer"]
    for invented in ("APPROVE", "REJECT"):
        assert invented not in answer, "a review that did not run must not produce a verdict"


def _manager_token(client):
    """A branch manager login. Register creates a loan officer, so the role is set directly."""
    from app.models.user import User, UserRole
    from tests.conftest import TestingSessionLocal

    client.post("/api/v1/auth/register", json={
        "name": "Review Audit Manager", "email": "review.audit@test.com",
        "password": "Test@1234",
    })
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "review.audit@test.com").first()
    user.role = UserRole.branch_manager
    db.commit()
    db.close()

    return client.post("/api/v1/auth/login", json={
        "email": "review.audit@test.com", "password": "Test@1234",
    }).json()["access_token"]


def test_the_review_is_still_recorded_when_it_fails(client, auth_token, broken_review):
    """
    A failed review is a thing that happened, and a manager auditing that
    application should be able to see somebody tried. The activity page is
    manager-only, so the check reads it as one.
    """
    broken_review(RuntimeError("boom"))
    _ask(client, auth_token, "assess application 7")

    rows = client.get("/api/v1/activity?action=chat_review",
                      headers={"Authorization": f"Bearer {_manager_token(client)}"})
    assert rows.status_code == 200, rows.text
    assert rows.json()["total_count"] >= 1
