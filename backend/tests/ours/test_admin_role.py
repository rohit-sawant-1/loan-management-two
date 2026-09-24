"""
Piece 27: the System Administrator sees everything and changes nothing.

Every address was sorted into VIEW or ACT. These tests walk both lists as the
admin, through the real addresses, the way a browser would. The ACT list comes
with a second check that nothing actually changed, because a 403 that still
wrote something would be worse than no guard at all.

Nothing here calls a real AI, so it spends no Gemini quota.
"""

import pytest
from langchain_core.prompts import PromptTemplate

from agent.agent import (
    ADMIN_REACT_TEMPLATE, REACT_TEMPLATE, STAFF_REACT_TEMPLATE, template_for, tools_for,
)
from agent.write_tools import WRITE_TOOLS
from app.domain import rules
from app.models.user import User, UserRole
from app.routers import chat as chat_router
from app.services import pending_actions
from tests.conftest import TestingSessionLocal

PASSWORD = "Test@1234"
GOOD_REASON = "I typed the wrong amount by mistake"
ADMIN_REFUSAL = "The system administrator can view records but cannot create or change them."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _staff_with_role(client, email, role):
    """Register makes a loan officer, so the role is changed directly (as in test_edit_requests)."""
    response = client.post("/api/v1/auth/register", json={
        "name": "Role Test", "email": email, "password": PASSWORD,
    })
    assert response.status_code == 201, response.text
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    user.role = role
    db.commit()
    db.close()
    return _login(client, email)


def _admin_token(client):
    return _staff_with_role(client, "admin.test@test.com", UserRole.admin)


@pytest.fixture
def world(client, auth_token):
    """
    One of everything the admin might look at or try to change: a customer
    with an application, a document on it, and an edit request waiting. Plus
    the trainer's officer (auth_token), a manager, and the admin.
    """
    client.post("/api/v1/auth/register-applicant", json={
        "name": "Priya Admin", "email": "priya.admin@test.com", "password": PASSWORD,
        "phone": "9876500041", "annual_income": 600000.0, "employment_status": "salaried",
        "credit_score": 760, "date_of_birth": "1994-03-15", "years_with_employer": 3.0,
    })
    customer = _login(client, "priya.admin@test.com")
    applicant_id = client.get("/api/v1/applicants/me", headers=_headers(customer)).json()["id"]

    application = client.post("/api/v1/applications", json={
        "applicant_id": applicant_id, "loan_type": "personal",
        "amount_requested": 200000.0, "tenure_months": 24, "purpose": "Home renovation",
    }, headers=_headers(customer))
    assert application.status_code == 201, application.text
    app_id = application.json()["id"]

    document = client.post(f"/api/v1/applications/{app_id}/documents",
                           json={"doc_type": "id_proof", "file_name": "aadhaar.pdf"},
                           headers=_headers(customer))
    assert document.status_code == 201, document.text

    edit_request = client.post(f"/api/v1/applications/{app_id}/edit-requests",
                               json={"fields": ["amount_requested"], "reason": GOOD_REASON},
                               headers=_headers(customer))
    assert edit_request.status_code == 201, edit_request.text

    return {
        "customer": customer,
        "officer": auth_token,
        "manager": _staff_with_role(client, "manager.test@test.com", UserRole.branch_manager),
        "admin": _admin_token(client),
        "applicant_id": applicant_id,
        "app_id": app_id,
        "doc_id": document.json()["id"],
        "request_id": edit_request.json()["id"],
    }


# ---------------------------------------------------------------------------
# Nobody can make themselves an admin
# ---------------------------------------------------------------------------

def test_nobody_can_register_as_an_admin(client):
    """T-115. The register address takes a role, so it has to refuse this one."""
    response = client.post("/api/v1/auth/register", json={
        "name": "Sneaky", "email": "sneaky@test.com", "password": PASSWORD, "role": "admin",
    })
    assert response.status_code == 422
    assert "Administrator accounts are created by the bank" in response.json()["detail"]


def test_register_without_a_role_still_makes_a_loan_officer(client):
    """The trainer's default (D-07) is untouched by the new role."""
    response = client.post("/api/v1/auth/register", json={
        "name": "Plain Officer", "email": "plain@test.com", "password": PASSWORD,
    })
    assert response.status_code == 201
    assert response.json()["role"] == "loan_officer"


def test_the_admin_knows_who_it_is(client):
    me = client.get("/api/v1/auth/me", headers=_headers(_admin_token(client)))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


# ---------------------------------------------------------------------------
# VIEW: the admin can look at everything
# ---------------------------------------------------------------------------

VIEW_ADDRESSES = [
    "/api/v1/applications",
    "/api/v1/applications/{app_id}",
    "/api/v1/applicants",
    "/api/v1/applicants/{applicant_id}",
    "/api/v1/applications/{app_id}/documents",
    "/api/v1/applications/{app_id}/edit-requests",
    "/api/v1/edit-requests",
    "/api/v1/dashboard/summary",
    "/api/v1/activity",
    "/api/v1/activity/entity/application/{app_id}",
    "/api/v1/admin/users",
]


@pytest.mark.parametrize("address", VIEW_ADDRESSES)
def test_the_admin_can_view(client, world, address):
    response = client.get(address.format(**world), headers=_headers(world["admin"]))
    assert response.status_code == 200, response.text


def test_the_admin_sees_every_application_not_just_its_own(client, world):
    """The admin has no applications of its own, so an empty list would mean it was scoped like a customer."""
    body = client.get("/api/v1/applications", headers=_headers(world["admin"])).json()
    assert body["total_count"] == 1
    assert body["items"][0]["id"] == world["app_id"]


def test_the_account_list_counts_every_role(client, world):
    body = client.get("/api/v1/admin/users", headers=_headers(world["admin"])).json()

    # Every role is a key, even the ones with nobody in them.
    assert set(body["counts_by_role"]) == set(rules.ROLES)
    assert body["counts_by_role"] == {
        "applicant": 1, "loan_officer": 1, "branch_manager": 1, "admin": 1,
    }
    assert body["total_count"] == 4
    assert len(body["items"]) == 4
    # The same shape as /auth/me, and never the password hash.
    first = body["items"][0]
    assert set(first) == {"id", "name", "email", "role", "is_active", "created_at"}


# ---------------------------------------------------------------------------
# ACT: the admin can change nothing
# ---------------------------------------------------------------------------

def _act_addresses(world):
    """(method, address, body) for every action. Bodies are valid, so a 403 is the guard, not bad input."""
    return [
        ("post", "/api/v1/applications", {
            "applicant_id": world["applicant_id"], "loan_type": "personal",
            "amount_requested": 150000.0, "tenure_months": 24, "purpose": "Admin tries to apply",
        }),
        ("post", "/api/v1/applicants", {
            "name": "Admin Made", "email": "adminmade@test.com", "phone": "9876500042",
            "credit_score": 720, "annual_income": 600000.0, "employment_status": "salaried",
        }),
        ("post", f"/api/v1/applications/{world['app_id']}/documents",
         {"doc_type": "income_proof", "file_name": "salary.pdf"}),
        ("patch", f"/api/v1/applications/{world['app_id']}/documents/{world['doc_id']}/verify", None),
        ("patch", f"/api/v1/applications/{world['app_id']}/status",
         {"new_status": "under_review", "remarks": "Admin tries to move it"}),
        ("post", f"/api/v1/edit-requests/{world['request_id']}/approve", {"note": None}),
        ("post", f"/api/v1/edit-requests/{world['request_id']}/refuse",
         {"note": "Admin tries to refuse this"}),
        ("post", "/api/v1/applications/check-eligibility", {
            "applicant_id": world["applicant_id"], "loan_type": "personal",
            "amount_requested": 150000.0, "tenure_months": 24,
        }),
        ("get", "/api/v1/briefing", None),
        ("post", f"/api/v1/applications/{world['app_id']}/edit-requests",
         {"fields": ["tenure_months"], "reason": GOOD_REASON}),
        ("patch", f"/api/v1/applications/{world['app_id']}", {"amount_requested": 150000.0}),
        # Piece 32d: replacing a document.
        ("post", f"/api/v1/applications/{world['app_id']}/documents/{world['doc_id']}/replace",
         {"file_name": "newer.pdf"}),
        # Piece 33: a document's details. The guard answers before the id is
        # even looked up, so extraction 1 needn't exist.
        ("post", f"/api/v1/applications/{world['app_id']}/documents/{world['doc_id']}/extraction",
         {"kind": "aadhaar"}),
        ("patch", "/api/v1/extractions/1/fields", {"values": {"name": "Admin Tries"}}),
        ("post", "/api/v1/extractions/1/confirm", None),
        ("post", "/api/v1/extractions/1/discard", None),
        # Pieces 37 + 38: attaching documents from the Assistant (customers only).
        ("post", "/api/v1/chat/attachments",
         {"application_id": world["app_id"], "document_ids": [world["doc_id"]],
          "attach_key": "admin-tries-0001"}),
    ]


def test_the_admin_can_act_on_nothing(client, world):
    refused = {}
    for method, address, body in _act_addresses(world):
        kwargs = {"headers": _headers(world["admin"])}
        if body is not None:
            kwargs["json"] = body
        response = getattr(client, method)(address, **kwargs)
        refused[f"{method.upper()} {address}"] = response.status_code

    allowed = {k: v for k, v in refused.items() if v != 403}
    assert not allowed, f"These answered something other than 403 for the admin: {allowed}"


@pytest.mark.parametrize("address", [
    "/api/v1/applications",
    "/api/v1/applications/check-eligibility",
])
def test_the_admin_is_told_why(client, world, address):
    """The three actions that were open to any login now say plainly why the admin is refused."""
    body = {"applicant_id": world["applicant_id"], "loan_type": "personal",
            "amount_requested": 150000.0, "tenure_months": 24, "purpose": "Admin tries"}
    response = client.post(address, json=body, headers=_headers(world["admin"]))
    assert response.status_code == 403
    assert response.json()["detail"] == ADMIN_REFUSAL


def test_nothing_changed_after_the_admin_tried_everything(client, world):
    for method, address, body in _act_addresses(world):
        kwargs = {"headers": _headers(world["admin"])}
        if body is not None:
            kwargs["json"] = body
        getattr(client, method)(address, **kwargs)

    officer = _headers(world["officer"])
    applications = client.get("/api/v1/applications", headers=officer).json()
    assert applications["total_count"] == 1

    application = client.get(f"/api/v1/applications/{world['app_id']}", headers=officer).json()
    assert application["status"] == "submitted"
    assert application["amount_requested"] == 200000.0

    documents = client.get(f"/api/v1/applications/{world['app_id']}/documents", headers=officer).json()
    assert len(documents["items"]) == 1
    assert documents["items"][0]["verified"] is False

    requests = client.get(f"/api/v1/applications/{world['app_id']}/edit-requests", headers=officer).json()
    assert [r["status"] for r in requests] == ["pending"]

    applicants = client.get("/api/v1/applicants", headers=officer).json()
    assert applicants["total_count"] == 1


# ---------------------------------------------------------------------------
# The admin's own screen is the admin's alone
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("who", ["customer", "officer", "manager"])
def test_only_the_admin_can_list_accounts(client, world, who):
    response = client.get("/api/v1/admin/users", headers=_headers(world[who]))
    assert response.status_code == 403


def test_the_account_list_needs_a_login(client):
    assert client.get("/api/v1/admin/users").status_code == 401


def test_the_officer_and_manager_keep_their_access(client, world):
    """The guards were widened for the admin, not narrowed for anyone else."""
    for who in ("officer", "manager"):
        headers = _headers(world[who])
        assert client.get("/api/v1/dashboard/summary", headers=headers).status_code == 200
        assert client.get("/api/v1/edit-requests", headers=headers).status_code == 200
        assert client.get("/api/v1/applicants", headers=headers).status_code == 200
    manager = _headers(world["manager"])
    assert client.get("/api/v1/activity", headers=manager).status_code == 200
    # The audit log is still not the officer's.
    assert client.get("/api/v1/activity", headers=_headers(world["officer"])).status_code == 403


# ---------------------------------------------------------------------------
# The chatbot: read-only for the admin
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_chat():
    pending_actions._pending.clear()
    chat_router._agents.clear()
    yield
    pending_actions._pending.clear()
    chat_router._agents.clear()


def test_the_admin_is_not_bank_staff_to_the_chatbot():
    """STAFF_ROLES decides who gets the write tools and the review. The admin must stay out of it."""
    assert rules.ADMIN_ROLE not in rules.STAFF_ROLES
    write_names = {t.name for t in WRITE_TOOLS}
    assert not write_names & {t.name for t in tools_for("admin")}


def test_each_role_gets_its_own_prompt():
    """Three kinds of person, three prompts. The customer's is untouched by the other two."""
    assert template_for("admin") is ADMIN_REACT_TEMPLATE
    for staff_role in ("loan_officer", "branch_manager"):
        assert template_for(staff_role) is STAFF_REACT_TEMPLATE
    # A customer, and the no-role default the trainer's Phase 3 tests use.
    assert template_for("applicant") is REACT_TEMPLATE
    assert template_for(None) is REACT_TEMPLATE

    # The customer's prompt must not pick up either of the other paragraphs.
    assert "system administrator" not in REACT_TEMPLATE
    assert "CONFIRMATION NEEDED" not in REACT_TEMPLATE
    # And the admin gets no instructions about tools it hasn't got.
    assert "CONFIRMATION NEEDED" not in ADMIN_REACT_TEMPLATE


@pytest.mark.parametrize("template", [REACT_TEMPLATE, STAFF_REACT_TEMPLATE, ADMIN_REACT_TEMPLATE])
def test_every_prompt_still_renders(template):
    """
    A stray { or } in a prompt is a crash at the first message, not a typo.
    This is the check that would have caught it before a demo.
    """
    rendered = PromptTemplate.from_template(template).format(
        tools="tool list", tool_names="tool_name_list",
        input="change application 21 to under review", agent_scratchpad="",
    )
    assert "change application 21 to under review" in rendered


@pytest.mark.parametrize("must_mention", [
    # The wording that went wrong: the admin was told to email customer support
    # about "your application".
    "your application", "support@bank.com",
    # Every action it has to refuse, and who does it instead.
    "under review", "Disbursing", "edit request", "verified", "borrower profile",
    "underwriting review",
    # Things nobody can do through the assistant.
    "password", "activity log", "interest rate", "notification", "on behalf of",
])
def test_the_admin_prompt_covers_what_it_must(must_mention):
    assert must_mention in ADMIN_REACT_TEMPLATE


def test_the_admin_cannot_run_a_review(client, monkeypatch, clean_chat):
    """Refused before the graph starts, with a sentence that fits an admin rather than a customer."""
    calls = []
    monkeypatch.setattr("multi_agent.graph.evaluate_loan_application",
                        lambda application_id: calls.append(application_id))

    response = client.post("/api/v1/chat", json={"message": "assess application 1"},
                           headers=_headers(_admin_token(client)))

    assert response.status_code == 200
    body = response.json()
    assert calls == []
    assert body["mode"] == "review"
    assert "administrator" in body["answer"]
    assert "your own application" not in body["answer"]


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def test_seeding_the_admin_twice_makes_one(db_session):
    """ensure_admin runs on every seed, including old databases, so it must be safe to repeat."""
    import seed

    assert seed.ensure_admin(db_session) is True
    assert seed.ensure_admin(db_session) is False

    admins = db_session.query(User).filter(User.role == UserRole.admin).all()
    assert len(admins) == 1
    assert admins[0].email == "admin@bank.com"
