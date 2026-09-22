"""
Piece 25: a customer asks to change their application, staff approve or
refuse, and the customer saves the change once.

Everything goes through the real addresses, as a browser would. No AI is
involved anywhere in this feature, so nothing here spends Gemini quota.

The refusals come first, because they are the ones whose failure matters: a
customer must never be able to change an application without a staff yes, or
change more than they were allowed to.
"""

import json

import pytest

from app.models.activity_log import ActivityLog
from app.services.edit_request_service import RECHECK_LINE
from tests.conftest import TestingSessionLocal

PASSWORD = "Test@1234"
GOOD_REASON = "I typed the wrong amount by mistake"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _customer(client, email="priya.edit@test.com", phone="9876500031"):
    """A customer who passes every eligibility rule for a modest personal loan."""
    response = client.post("/api/v1/auth/register-applicant", json={
        "name": "Priya Edit", "email": email, "password": PASSWORD, "phone": phone,
        "annual_income": 600000.0, "employment_status": "salaried",
        "credit_score": 760, "date_of_birth": "1994-03-15", "years_with_employer": 3.0,
    })
    assert response.status_code in (200, 201), response.text
    return _login(client, email)


def _manager(client):
    """Register makes a loan officer, so the role is changed directly (as in test_briefing)."""
    from app.models.user import User, UserRole

    client.post("/api/v1/auth/register", json={
        "name": "Edit Manager", "email": "edit.manager@test.com", "password": PASSWORD,
    })
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "edit.manager@test.com").first()
    user.role = UserRole.branch_manager
    db.commit()
    db.close()
    return _login(client, "edit.manager@test.com")


def _apply(client, token):
    me = client.get("/api/v1/applicants/me", headers=_headers(token)).json()
    response = client.post("/api/v1/applications", json={
        "applicant_id": me["id"], "loan_type": "personal",
        "amount_requested": 200000.0, "tenure_months": 24, "purpose": "Home renovation",
    }, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def _ask(client, token, app_id, fields=("amount_requested",), reason=GOOD_REASON):
    return client.post(f"/api/v1/applications/{app_id}/edit-requests",
                       json={"fields": list(fields), "reason": reason}, headers=_headers(token))


def _approve(client, token, request_id, note=None):
    return client.post(f"/api/v1/edit-requests/{request_id}/approve",
                       json={"note": note}, headers=_headers(token))


def _refuse(client, token, request_id, note):
    return client.post(f"/api/v1/edit-requests/{request_id}/refuse",
                       json={"note": note}, headers=_headers(token))


def _save(client, token, app_id, **fields):
    return client.patch(f"/api/v1/applications/{app_id}", json=fields, headers=_headers(token))


def _move(client, token, app_id, new_status):
    response = client.patch(f"/api/v1/applications/{app_id}/status",
                            json={"new_status": new_status, "remarks": "test"},
                            headers=_headers(token))
    assert response.status_code == 200, response.text


def _activity(app_id, action):
    """The details of every activity row with this action, for this application."""
    db = TestingSessionLocal()
    rows = (db.query(ActivityLog)
            .filter(ActivityLog.entity_type == "application",
                    ActivityLog.entity_id == app_id,
                    ActivityLog.action == action)
            .all())
    db.close()
    return [json.loads(r.details) for r in rows]


@pytest.fixture
def customer(client):
    return _customer(client)


@pytest.fixture
def app_id(client, customer):
    return _apply(client, customer)["id"]


# ---------------------------------------------------------------------------
# 1. Asking
# ---------------------------------------------------------------------------

def test_a_customer_can_ask_while_submitted_and_it_is_logged(client, customer, app_id):
    response = _ask(client, customer, app_id, fields=("amount_requested", "tenure_months"))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["fields"] == ["amount_requested", "tenure_months"]
    assert body["applicant_name"] == "Priya Edit"
    assert body["application_status"] == "submitted"

    logged = _activity(app_id, "edit_requested")
    assert len(logged) == 1
    assert logged[0]["reason"] == GOOD_REASON


def test_a_customer_can_ask_while_under_review(client, auth_token, customer, app_id):
    _move(client, auth_token, app_id, "under_review")
    assert _ask(client, customer, app_id).status_code == 201


@pytest.mark.parametrize("path", [
    ["under_review", "approved"],
    ["under_review", "rejected"],
    ["under_review", "approved", "disbursed"],
])
def test_asking_is_refused_once_a_decision_has_been_made(client, auth_token, customer, app_id, path):
    manager = _manager(client)
    for step in path:
        _move(client, manager, app_id, step)
    response = _ask(client, customer, app_id)
    assert response.status_code == 422
    assert "can no longer be changed" in response.json()["detail"]


def test_a_customer_cannot_ask_about_someone_elses_application(client, app_id):
    stranger = _customer(client, email="stranger@test.com", phone="9876500032")
    assert _ask(client, stranger, app_id).status_code == 403


def test_staff_cannot_ask_on_a_customers_behalf(client, auth_token, app_id):
    assert _ask(client, auth_token, app_id).status_code == 403


@pytest.mark.parametrize("fields, reason", [
    (["loan_type"], GOOD_REASON),
    ([], GOOD_REASON),
    (["purpose"], "too short"),
])
def test_a_badly_formed_request_is_refused(client, customer, app_id, fields, reason):
    assert _ask(client, customer, app_id, fields=fields, reason=reason).status_code == 422


def test_only_one_open_request_at_a_time(client, auth_token, customer, app_id):
    first = _ask(client, customer, app_id).json()
    second = _ask(client, customer, app_id)
    assert second.status_code == 422
    assert "already an open edit request" in second.json()["detail"]

    # Once the first is refused, the customer may ask again.
    _refuse(client, auth_token, first["id"], "Your documents show the original amount")
    assert _ask(client, customer, app_id).status_code == 201


def test_asking_about_a_missing_application_is_a_404(client, customer):
    assert _ask(client, customer, 99999).status_code == 404


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def test_only_staff_see_the_queue(client, auth_token, customer, app_id):
    _ask(client, customer, app_id)
    assert client.get("/api/v1/edit-requests", headers=_headers(customer)).status_code == 403

    response = client.get("/api/v1/edit-requests?status=pending", headers=_headers(auth_token))
    assert response.status_code == 200
    assert response.json()["total_count"] == 1

    bad = client.get("/api/v1/edit-requests?status=banana", headers=_headers(auth_token))
    assert bad.status_code == 400


def test_the_owner_and_staff_can_read_an_applications_requests(client, auth_token, customer, app_id):
    _ask(client, customer, app_id)
    for token in (customer, auth_token):
        response = client.get(f"/api/v1/applications/{app_id}/edit-requests", headers=_headers(token))
        assert response.status_code == 200
        assert len(response.json()) == 1

    stranger = _customer(client, email="stranger@test.com", phone="9876500032")
    response = client.get(f"/api/v1/applications/{app_id}/edit-requests", headers=_headers(stranger))
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 2. Deciding
# ---------------------------------------------------------------------------

def test_a_refusal_must_give_a_reason(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]
    assert _refuse(client, auth_token, request_id, "no").status_code == 422

    note = "Your payslips support the original amount"
    response = _refuse(client, auth_token, request_id, note)
    assert response.status_code == 200
    assert response.json()["status"] == "refused"

    # The customer can read why.
    seen = client.get(f"/api/v1/applications/{app_id}/edit-requests", headers=_headers(customer)).json()
    assert seen[0]["decision_note"] == note
    assert _activity(app_id, "edit_request_refused")[0]["note"] == note


def test_a_customer_cannot_approve_their_own_request(client, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]
    assert _approve(client, customer, request_id).status_code == 403


def test_a_request_cannot_be_decided_twice(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]
    assert _approve(client, auth_token, request_id).status_code == 200
    assert _refuse(client, auth_token, request_id, "Changed my mind about this one").status_code == 422


def test_the_manager_can_decide_too(client, customer, app_id):
    manager = _manager(client)
    request_id = _ask(client, customer, app_id).json()["id"]
    response = _approve(client, manager, request_id, note="Fine, go ahead")
    assert response.status_code == 200
    assert response.json()["decided_by"] == "edit.manager@test.com"
    assert _activity(app_id, "edit_request_approved")[0]["note"] == "Fine, go ahead"


# ---------------------------------------------------------------------------
# 3. Saving
# ---------------------------------------------------------------------------

def test_editing_is_locked_until_staff_approve(client, customer, app_id):
    assert _save(client, customer, app_id, amount_requested=250000).status_code == 403
    _ask(client, customer, app_id)   # asked, but still waiting
    assert _save(client, customer, app_id, amount_requested=250000).status_code == 403


def test_an_approved_edit_saves_once_then_locks_again(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]
    _approve(client, auth_token, request_id)

    response = _save(client, customer, app_id, amount_requested=250000)
    assert response.status_code == 200, response.text
    assert response.json()["amount_requested"] == 250000

    requests = client.get(f"/api/v1/applications/{app_id}/edit-requests",
                          headers=_headers(customer)).json()
    assert requests[0]["status"] == "completed"
    assert requests[0]["completed_at"] is not None

    # The one save is used up.
    assert _save(client, customer, app_id, amount_requested=260000).status_code == 403


def test_only_the_approved_fields_can_change(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id, fields=("amount_requested",)).json()["id"]
    _approve(client, auth_token, request_id)

    response = _save(client, customer, app_id, tenure_months=36)
    assert response.status_code == 403
    assert "amount_requested" in response.json()["detail"]
    # Loan type can never be sent at all.
    assert _save(client, customer, app_id, amount_requested=250000, loan_type="home").status_code == 422


def test_staff_cannot_save_a_customers_edit(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]
    _approve(client, auth_token, request_id)
    assert _save(client, auth_token, app_id, amount_requested=250000).status_code == 403


def test_saving_the_same_values_is_refused(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]
    _approve(client, auth_token, request_id)
    response = _save(client, customer, app_id, amount_requested=200000)
    assert response.status_code == 422
    assert "Nothing changed" in response.json()["detail"]


def test_the_per_type_limits_still_apply(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id, fields=("tenure_months",)).json()["id"]
    _approve(client, auth_token, request_id)

    # A personal loan runs 12 to 60 months.
    response = _save(client, customer, app_id, tenure_months=72)
    assert response.status_code == 422
    assert "between 12 and 60 months" in response.json()["detail"]

    # The refused attempt did not use up the approval.
    assert _save(client, customer, app_id, tenure_months=36).status_code == 200


def test_an_edit_rechecks_eligibility_and_keeps_the_old_result(client, auth_token, customer):
    application = _apply(client, customer)
    assert application["eligibility_passed"] is True
    app_id = application["id"]

    request_id = _ask(client, customer, app_id).json()["id"]
    _approve(client, auth_token, request_id)

    # ₹20 lakh over 24 months is an EMI far above half of ₹50,000 a month.
    response = _save(client, customer, app_id, amount_requested=2000000)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligibility_passed"] is False
    assert RECHECK_LINE in body["eligibility_summary"]

    logged = _activity(app_id, "application_edited")[0]
    assert logged["before"] == {"amount_requested": 200000.0}
    assert logged["after"] == {"amount_requested": 2000000.0}
    assert logged["eligibility_passed_before"] is True
    assert logged["eligibility_passed_after"] is False
    assert "ELIGIBLE" in logged["previous_eligibility_summary"]


def test_a_purpose_edit_is_trimmed(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id, fields=("purpose",)).json()["id"]
    _approve(client, auth_token, request_id)
    response = _save(client, customer, app_id, purpose="   Buying a used car   ")
    assert response.status_code == 200
    assert response.json()["purpose"] == "Buying a used car"


# ---------------------------------------------------------------------------
# 4. The status moves on
# ---------------------------------------------------------------------------

def test_a_waiting_request_is_closed_when_the_loan_is_decided(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]

    # Still editable at under review, so nothing is closed yet.
    _move(client, auth_token, app_id, "under_review")
    queue = client.get("/api/v1/edit-requests?status=pending", headers=_headers(auth_token)).json()
    assert queue["total_count"] == 1

    _move(client, auth_token, app_id, "approved")
    requests = client.get(f"/api/v1/applications/{app_id}/edit-requests",
                          headers=_headers(customer)).json()
    assert requests[0]["status"] == "closed"
    assert "moved to approved" in requests[0]["decision_note"]
    assert len(_activity(app_id, "edit_request_closed")) == 1

    # Nothing can be done with it any more.
    assert _approve(client, auth_token, request_id).status_code == 422


def test_an_unlocked_edit_cannot_be_used_after_the_loan_is_decided(client, auth_token, customer, app_id):
    request_id = _ask(client, customer, app_id).json()["id"]
    _approve(client, auth_token, request_id)
    _move(client, auth_token, app_id, "under_review")
    _move(client, auth_token, app_id, "rejected")

    assert _save(client, customer, app_id, amount_requested=250000).status_code == 403
