"""
Phase 5's four-agent review, reachable from the chat box.

"Assess application 7" runs the whole underwriting pipeline and shows the
verdict. Before this, the only way to run one was a terminal prompt, so the
smartest part of the product was invisible inside the product.

Nothing here calls a real AI or the real graph — `evaluate_loan_application` is
replaced by a stand-in returning a state of the shape the real one produces. A
genuine review is two AI calls and ten seconds, and these tests run hundreds of
times while building.
"""

import json

import pytest
from jose import jwt

from app.config import settings
from app.routers import chat as chat_router
from app.services import pending_actions
from app.services.loan_api_client import service_token


def _ask(client, token, message):
    # Piece 36: carry on in the person's latest chat, as the Assistant page
    # does. A "reply YES" only works in the chat the change was proposed in.
    latest = client.get("/api/v1/chat/sessions", headers={"Authorization": f"Bearer {token}"}).json()
    session_id = str(latest[0]["id"]) if latest else None
    return client.post("/api/v1/chat", json={"message": message, "session_id": session_id},
                       headers={"Authorization": f"Bearer {token}"})


def _good_state(application_id="7", decision="APPROVE"):
    """A finished review, shaped exactly as the real graph returns one."""
    return {
        "application_id": application_id,
        "applicant_data": {"id": 1, "name": "Priya Sharma"},
        "application_data": {"id": int(application_id), "loan_type": "home"},
        "documents": [],
        "risk_assessment": {
            "debt_to_income_ratio": 0.29,
            "emi_amount": 9415.0,
            "emi_affordability": "yes",
            "credit_risk_level": "low",
            "employment_risk": "low",
            "overall_risk_score": 90.0,
            "risk_summary": "A strong application.",
        },
        "compliance_check": {
            "documents_complete": True,
            "missing_documents": [],
            "kyc_verified": True,
            "amount_within_limit": True,
            "age_eligible": True,
            "compliance_passed": True,
            "compliance_notes": "All compliance checks passed",
        },
        "final_decision": decision,
        "reasoning": "The applicant comfortably affords the requested EMI.",
        "messages": [
            {"agent": "data_collector", "message": "Collected data for application 7"},
            {"agent": "risk_assessor", "message": "Risk score: 90/100"},
            {"agent": "compliance_checker", "message": "Compliance: PASSED"},
            {"agent": "decision_maker", "message": f"Final Decision: {decision}"},
        ],
        "current_agent": "decision_maker",
        "errors": [],
    }


def _failed_state(problem="Application 99 not found"):
    """
    What comes back when data collection fails: the graph short-circuits, so
    the risk and compliance dicts are still empty and no agent reported in.
    """
    return {
        "application_id": "99",
        "applicant_data": {}, "application_data": {}, "documents": [],
        "risk_assessment": {}, "compliance_check": {},
        "final_decision": "", "reasoning": "",
        "messages": [], "current_agent": "data_collector",
        "errors": [problem],
    }


@pytest.fixture(autouse=True)
def clean_slate():
    pending_actions._pending.clear()
    chat_router._agents.clear()
    yield
    pending_actions._pending.clear()
    chat_router._agents.clear()


@pytest.fixture
def fake_review(monkeypatch):
    """
    Stand in for the real graph. Records that it ran, and under whose identity —
    the second of those is the security-critical part.
    """
    seen = {"calls": 0, "application_id": None, "claims": None}

    def _install(state=None):
        result = state if state is not None else _good_state()

        def fake_evaluate(application_id):
            seen["calls"] += 1
            seen["application_id"] = application_id
            # Whatever token the real agents would have sent to the API.
            seen["claims"] = jwt.decode(service_token(), settings.secret_key,
                                        algorithms=[settings.jwt_algorithm])
            return result

        monkeypatch.setattr("multi_agent.graph.evaluate_loan_application", fake_evaluate)
        return seen

    return _install


@pytest.fixture
def customer_token(client):
    client.post("/api/v1/auth/register-applicant", json={
        "name": "Review Customer", "email": "reviewcustomer@test.com",
        "password": "Test@1234", "phone": "9876500033",
        "annual_income": 600000.0, "employment_status": "salaried",
    })
    return client.post("/api/v1/auth/login", json={
        "email": "reviewcustomer@test.com", "password": "Test@1234",
    }).json()["access_token"]


# ---------------------------------------------------------------------------
# It runs, and it runs as the right person
# ---------------------------------------------------------------------------

def test_an_officer_can_run_a_review(client, auth_token, fake_review):
    seen = fake_review()
    body = _ask(client, auth_token, "assess application 7").json()

    assert body["mode"] == "review"
    assert seen["calls"] == 1
    assert seen["application_id"] == "7"
    assert "APPROVE" in body["answer"]


def test_the_review_runs_as_the_person_who_asked(client, auth_token, fake_review):
    """
    The security-critical one. Outside `acting_as()` the API client falls back
    to a branch-manager service identity, which would hand whoever asked a
    manager's view of the bank (T-75).
    """
    seen = fake_review()
    _ask(client, auth_token, "assess application 7")

    assert seen["claims"]["sub"] == "officer@test.com"
    assert seen["claims"]["role"] == "loan_officer"


def test_a_customer_is_refused_and_the_review_never_runs(client, customer_token,
                                                          fake_review):
    """
    Refused before the graph starts, so it costs no AI call and no ten-second
    wait — and no customer is shown an AI's "REJECT" for an application a human
    has not rejected.
    """
    seen = fake_review()
    body = _ask(client, customer_token, "assess application 2").json()

    assert seen["calls"] == 0
    assert body["mode"] == "review"
    assert "staff" in body["answer"].lower()


def test_the_answer_carries_the_verdict_and_the_figures(client, auth_token, fake_review):
    fake_review()
    answer = _ask(client, auth_token, "assess application 7").json()["answer"]

    assert "Application 7" in answer
    assert "APPROVE" in answer
    assert "90/100" in answer                  # the risk score, no decimal tail
    assert "29%" in answer                     # debt-to-income, as a percentage
    assert "9,415" in answer                   # EMI, grouped the Indian way
    assert "comfortably affords" in answer     # the reasoning paragraph


def test_all_four_agents_show_up_as_steps_in_order(client, auth_token, fake_review):
    """
    The demo moment: the "how this was worked out" panel becomes the pipeline,
    which is why no new response field was needed for any of this.
    """
    fake_review()
    body = _ask(client, auth_token, "assess application 7").json()

    assert [t["tool"] for t in body["tools_used"]] == [
        "data_collector", "risk_assessor", "compliance_checker", "decision_maker",
    ]
    assert "90/100" in body["tools_used"][1]["tool_input"]


def test_missing_documents_are_named(client, auth_token, fake_review):
    state = _good_state(decision="REQUEST_MORE_INFO")
    state["compliance_check"]["compliance_passed"] = False
    state["compliance_check"]["missing_documents"] = ["income_proof", "bank_statement"]
    fake_review(state)

    answer = _ask(client, auth_token, "assess application 7").json()["answer"]
    assert "income proof" in answer
    assert "bank statement" in answer


# ---------------------------------------------------------------------------
# When it cannot run
# ---------------------------------------------------------------------------

def test_a_missing_application_is_explained_not_crashed(client, auth_token, fake_review):
    fake_review(_failed_state())
    response = _ask(client, auth_token, "assess application 99")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "review"
    assert "not found" in body["answer"]
    assert body["tools_used"] == []            # no agent got as far as reporting


def test_a_failed_review_is_not_reported_as_an_ai_failure(client, auth_token, fake_review):
    """
    A typo'd application number has nothing to do with the model. Setting the AI
    codes here would make the amber notice claim a quota problem about it.
    """
    fake_review(_failed_state())
    body = _ask(client, auth_token, "assess application 99").json()

    assert body["ai_status"] == "ai_ok"
    assert body["ai_notice"] == ""


# ---------------------------------------------------------------------------
# It does not swallow anything else
# ---------------------------------------------------------------------------

def test_a_question_about_an_application_is_not_a_review(client, auth_token,
                                                          fake_review, monkeypatch):
    """
    The case the whole trigger design exists for. This sentence contains
    "application 7" and must still be answered in a second by the ordinary
    agent, not in ten by four of them.
    """
    seen = fake_review()

    def fake_run_agent(question, executor=None):
        return {"output": "It is under review.", "intermediate_steps": []}

    import agent.agent as agent_module
    monkeypatch.setattr(agent_module, "run_agent", fake_run_agent)
    monkeypatch.setattr(chat_router, "get_agent", lambda role=None: None)
    monkeypatch.setattr(chat_router, "_policy_sources", lambda calls: [])

    body = _ask(client, auth_token, "what happened to application 7").json()

    assert seen["calls"] == 0
    assert body["mode"] == "agent"


def test_a_pending_confirmation_still_works(client, auth_token, fake_review, monkeypatch):
    """
    "yes" must keep reaching the pending-action check rather than being read as
    anything to do with a review.
    """
    fake_review()
    pending_actions._pending["officer@test.com"] = {
        "tool": "update_application_status",
        "arguments": {"application_id": 1, "new_status": "approved", "remarks": "fine"},
        "description": "About to move application 1 to 'approved'.",
        "created_at": __import__("time").monotonic(),
    }

    from mcp_server import mcp_app
    monkeypatch.setattr(mcp_app, "update_application_status",
                        lambda **kw: {"id": 1, "status": "approved"})

    body = _ask(client, auth_token, "yes").json()
    assert body["mode"] == "action"


def test_a_review_drops_a_pending_change_first(client, auth_token, fake_review):
    """
    Someone who proposes a rejection and then asks for a review has moved on.
    The old proposal must not survive to be confirmed by a later stray "yes".
    """
    fake_review()
    pending_actions._pending["officer@test.com"] = {
        "tool": "update_application_status",
        "arguments": {"application_id": 1, "new_status": "rejected", "remarks": "no"},
        "description": "About to move application 1 to 'rejected'.",
        "created_at": __import__("time").monotonic(),
    }

    _ask(client, auth_token, "assess application 7")
    assert pending_actions.peek("officer@test.com") is None


# ---------------------------------------------------------------------------
# The audit trail
# ---------------------------------------------------------------------------

def test_the_review_is_recorded_against_the_application(client, auth_token, fake_review):
    """
    Filed under the application, not under "chat", so it appears on that
    application's own timeline where an auditor would look for it (T-91).
    """
    from app.models.activity_log import ActivityLog
    from tests.conftest import TestingSessionLocal

    fake_review()
    _ask(client, auth_token, "assess application 7")

    session = TestingSessionLocal()
    try:
        row = (session.query(ActivityLog)
               .filter(ActivityLog.action == "chat_review")
               .order_by(ActivityLog.id.desc())
               .first())
        details = json.loads(row.details) if row else None
    finally:
        session.close()

    assert row is not None
    assert row.entity_type == "application"
    assert row.entity_id == 7
    assert details["decision"] == "APPROVE"
    assert details["risk_score"] == 90.0
    assert details["agents_run"] == [
        "data_collector", "risk_assessor", "compliance_checker", "decision_maker",
    ]
