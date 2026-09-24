"""
Piece 36: saved chat sessions.

Two core tests (trimmed-testing rule). The answer itself is stubbed, so
nothing here calls Gemini: `_answer` is replaced with a fixed reply, which is
all these tests need, since they're about saving and privacy, not answering.
"""

from app.models.user import UserRole
from app.routers import chat as chat_router
from app.schemas.chat import ChatResponse
from tests.ours.test_uploads import _customer, _headers, _staff_with_role


def _stub_answers(monkeypatch):
    def fake(body, request, db, user):
        return ChatResponse(answer=f"Answer to: {body.message.strip()}", mode="rag", duration_ms=1.0)
    monkeypatch.setattr(chat_router, "_answer", fake)


def _ask(client, token, message, session_id=None):
    return client.post("/api/v1/chat", json={"message": message, "session_id": session_id},
                       headers=_headers(token))


def test_a_conversation_is_saved_in_order_and_reopens(client, monkeypatch):
    _stub_answers(monkeypatch)
    priya = _customer(client, "priya.chat@test.com", "9876500081")

    first = _ask(client, priya, "What documents do I need?")
    assert first.status_code == 200, first.text
    session_id = first.json()["session_id"]
    second = _ask(client, priya, "And for a home loan?", str(session_id))
    assert second.json()["session_id"] == session_id          # carried on in the same chat

    sessions = client.get("/api/v1/chat/sessions", headers=_headers(priya)).json()
    assert [s["id"] for s in sessions] == [session_id]
    assert sessions[0]["title"] == "What documents do I need?"

    page = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=_headers(priya)).json()
    assert [(m["role"], m["content"]) for m in page["items"]] == [
        ("user", "What documents do I need?"),
        ("assistant", "Answer to: What documents do I need?"),
        ("user", "And for a home loan?"),
        ("assistant", "Answer to: And for a home loan?"),
    ]
    assert page["has_more"] is False


def test_nobody_else_can_open_or_add_to_a_chat(client, monkeypatch):
    _stub_answers(monkeypatch)
    priya = _customer(client, "priya.chat2@test.com", "9876500082")
    rahul = _customer(client, "rahul.chat2@test.com", "9876500083")
    admin = _staff_with_role(client, "admin.chat2@test.com", UserRole.admin)

    session_id = _ask(client, priya, "Is my loan approved?").json()["session_id"]

    for other in (rahul, admin):
        assert client.get(f"/api/v1/chat/sessions/{session_id}/messages",
                          headers=_headers(other)).status_code == 404
        assert client.patch(f"/api/v1/chat/sessions/{session_id}", json={"archived": True},
                            headers=_headers(other)).status_code == 404
        assert _ask(client, other, "Let me in", str(session_id)).status_code == 404
        assert client.get("/api/v1/chat/sessions", headers=_headers(other)).json() == []


def test_the_audit_row_keeps_bounded_excerpts_of_question_and_answer(client, auth_token, monkeypatch):
    """
    Rohit, 2026-09-24: a complete audit trail of the chatbot, kept as bounded
    excerpts (the first 200 characters of the question and the first 500 of the
    answer), while the full conversation stays in the owner's saved chat.
    The real answering code runs here; only the agent itself is faked.
    """
    import json

    import agent.agent as agent_module
    from app.models.activity_log import ActivityLog
    from tests.conftest import TestingSessionLocal

    long_answer = "The manual says: " + "x" * 800
    monkeypatch.setattr(agent_module, "run_agent",
                        lambda question, executor=None: {"output": long_answer, "intermediate_steps": []})
    monkeypatch.setattr(chat_router, "get_agent", lambda role=None: None)
    monkeypatch.setattr(chat_router, "_policy_sources", lambda calls: [])

    question = "What documents do I need? " + "y" * 300
    assert _ask(client, auth_token, question).status_code == 200

    db = TestingSessionLocal()
    row = db.query(ActivityLog).filter(ActivityLog.action == "chat_message").order_by(ActivityLog.id.desc()).first()
    db.close()
    details = json.loads(row.details)
    assert details["question"] == question[:200]           # an excerpt, not the whole question
    assert details["answer"] == long_answer[:500]           # an excerpt, not the whole answer
    assert details["mode"] == "agent" and details["ai_status"] == "ai_ok"
