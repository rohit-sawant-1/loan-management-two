"""
Piece 30: the app's own notifications, and the bell's unread count.

Three triggers and no others. The tests that matter most are the negative
ones: a customer must never receive a member of staff's notice, staff must
never receive a customer's, and nothing outside the three triggers may produce
one at all.

The last test in the file is the one that keeps the two systems apart: the
activity log must have exactly the same number of rows whether notifications
happen or not.

Offline. No AI.
"""

import pytest

from app.models.activity_log import ActivityLog
from app.models.notification import Notification, NotificationAudience, NotificationType
from app.models.user import User, UserRole
from app.services import notification_service
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


def _staff_with_role(client, email, role, *, active=True):
    client.post("/api/v1/auth/register", json={"name": "Staff Test", "email": email, "password": PASSWORD})
    token = _login(client, email)          # log in first: a switched-off account cannot
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    user.role = role
    user.is_active = active
    db.commit()
    db.close()
    return token


def _customer(client, email, phone, name="Priya Notify"):
    response = client.post("/api/v1/auth/register-applicant", json={
        "name": name, "email": email, "password": PASSWORD, "phone": phone,
        "annual_income": 600000.0, "employment_status": "salaried",
        "credit_score": 760, "date_of_birth": "1994-03-15", "years_with_employer": 3.0,
    })
    assert response.status_code in (200, 201), response.text
    return _login(client, email)


def _apply(client, token):
    me = client.get("/api/v1/applicants/me", headers=_headers(token)).json()
    response = client.post("/api/v1/applications", json={
        "applicant_id": me["id"], "loan_type": "personal",
        "amount_requested": 200000.0, "tenure_months": 24, "purpose": "Home renovation",
    }, headers=_headers(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _rows(email=None):
    """Every notification row, or just one person's, newest last."""
    db = TestingSessionLocal()
    query = db.query(Notification)
    if email is not None:
        user = db.query(User).filter(User.email == email).first()
        query = query.filter(Notification.recipient_user_id == user.id)
    rows = query.order_by(Notification.id).all()
    out = [(r.audience, r.type, r.title, r.body, r.link, r.read_at) for r in rows]
    db.close()
    return out


def _activity_count():
    db = TestingSessionLocal()
    count = db.query(ActivityLog).count()
    db.close()
    return count


@pytest.fixture
def world(client, auth_token):
    """An officer (the trainer's), a manager, a switched-off officer, an admin, two customers."""
    people = {
        "officer": ("officer@test.com", auth_token),
        "manager": ("notif.manager@test.com", _staff_with_role(client, "notif.manager@test.com", UserRole.branch_manager)),
        "retired": ("notif.retired@test.com", _staff_with_role(client, "notif.retired@test.com", UserRole.loan_officer, active=False)),
        "admin": ("notif.admin@test.com", _staff_with_role(client, "notif.admin@test.com", UserRole.admin)),
        "priya": ("notif.priya@test.com", _customer(client, "notif.priya@test.com", "9876500061", "Priya Notify")),
        "rahul": ("notif.rahul@test.com", _customer(client, "notif.rahul@test.com", "9876500062", "Rahul Notify")),
    }
    return {name: {"email": email, "token": token} for name, (email, token) in people.items()}


# ---------------------------------------------------------------------------
# Trigger 3: the customer hears about their own application
# ---------------------------------------------------------------------------

def test_submitting_tells_the_customer_and_nobody_else(client, world):
    app_id = _apply(client, world["priya"]["token"])

    mine = _rows(world["priya"]["email"])
    assert len(mine) == 1
    audience, type_, title, body, link, read_at = mine[0]
    assert audience == NotificationAudience.applicant
    assert type_ == NotificationType.application_status_changed
    assert title == "Application submitted"
    assert body == f"Application {app_id} has been submitted."
    assert link == f"/applications/{app_id}"
    assert read_at is None

    for who in ("officer", "manager", "admin", "rahul"):
        assert _rows(world[who]["email"]) == [], who


def test_a_status_change_tells_only_that_customer(client, world):
    app_id = _apply(client, world["priya"]["token"])
    _apply(client, world["rahul"]["token"])

    response = client.patch(f"/api/v1/applications/{app_id}/status",
                            json={"new_status": "under_review", "remarks": "Picked up"},
                            headers=_headers(world["officer"]["token"]))
    assert response.status_code == 200, response.text

    mine = _rows(world["priya"]["email"])
    assert len(mine) == 2
    assert mine[-1][2] == "Application updated"
    assert mine[-1][3] == f"Application {app_id} is now Under review."

    # Rahul has only his own submission notice; the other customer's move is not his business.
    assert len(_rows(world["rahul"]["email"])) == 1
    for who in ("officer", "manager", "admin"):
        assert _rows(world[who]["email"]) == [], who


def test_a_profile_with_no_login_gets_nothing(client, world):
    """Staff can create a borrower profile that has no account behind it."""
    made = client.post("/api/v1/applicants", json={
        "name": "No Login", "email": "nologin@test.com", "phone": "9876500063",
        "credit_score": 720, "annual_income": 600000.0, "employment_status": "salaried",
    }, headers=_headers(world["officer"]["token"]))
    assert made.status_code == 201, made.text

    created = client.post("/api/v1/applications", json={
        "applicant_id": made.json()["id"], "loan_type": "personal",
        "amount_requested": 200000.0, "tenure_months": 24, "purpose": "Staff submitted this",
    }, headers=_headers(world["officer"]["token"]))
    assert created.status_code == 201, created.text

    # Nobody at all: there is no user to address it to, and staff are not told.
    db = TestingSessionLocal()
    assert db.query(Notification).count() == 0
    db.close()


# ---------------------------------------------------------------------------
# Trigger 1: staff hear about an edit request
# ---------------------------------------------------------------------------

def test_an_edit_request_tells_every_working_member_of_staff(client, world):
    app_id = _apply(client, world["priya"]["token"])
    asked = client.post(f"/api/v1/applications/{app_id}/edit-requests",
                        json={"fields": ["amount_requested"], "reason": GOOD_REASON},
                        headers=_headers(world["priya"]["token"]))
    assert asked.status_code == 201, asked.text

    for who in ("officer", "manager"):
        rows = _rows(world[who]["email"])
        assert len(rows) == 1, who
        audience, type_, title, body, link, _ = rows[0]
        assert audience == NotificationAudience.staff
        assert type_ == NotificationType.edit_requested
        assert title == "Edit request"
        assert f"asked to change application {app_id}" in body
        assert link == "/edit-requests"

    # A switched-off account, the administrator and the customer get nothing.
    assert _rows(world["retired"]["email"]) == []
    assert _rows(world["admin"]["email"]) == []
    # Priya still has only her own submission notice.
    assert len(_rows(world["priya"]["email"])) == 1


def test_the_message_names_no_money(client, world):
    """A bell gets read over somebody's shoulder. No amounts, no private numbers."""
    app_id = _apply(client, world["priya"]["token"])
    client.post(f"/api/v1/applications/{app_id}/edit-requests",
                json={"fields": ["amount_requested"], "reason": GOOD_REASON},
                headers=_headers(world["priya"]["token"]))

    for _, _, title, body, _, _ in _rows(world["officer"]["email"]):
        assert "200000" not in body and "200,000" not in body
        assert "₹" not in body and "₹" not in title


# ---------------------------------------------------------------------------
# Trigger 2: built here, called by Piece 32
# ---------------------------------------------------------------------------

def test_a_test_document_tells_staff_only(client, world):
    app_id = _apply(client, world["priya"]["token"])
    added = client.post(f"/api/v1/applications/{app_id}/documents",
                        json={"doc_type": "id_proof", "file_name": "aadhaar.pdf"},
                        headers=_headers(world["priya"]["token"]))
    assert added.status_code == 201, added.text

    # Adding it normally tells nobody: an ordinary upload is not a trigger.
    assert _rows(world["officer"]["email"]) == []

    db = TestingSessionLocal()
    from app.models.document import Document
    document = db.query(Document).filter(Document.id == added.json()["id"]).first()
    notification_service.notify_staff_test_document(db, document, applicant_name="Priya Test")
    db.commit()
    db.close()

    rows = _rows(world["officer"]["email"])
    assert len(rows) == 1
    assert rows[0][1] == NotificationType.test_document_uploaded
    assert "TEST id proof" in rows[0][3]
    assert _rows(world["priya"]["email"])[-1][1] == NotificationType.application_status_changed


# ---------------------------------------------------------------------------
# Everything that must NOT make one
# ---------------------------------------------------------------------------

def test_the_quiet_events_notify_nobody(client, world):
    app_id = _apply(client, world["priya"]["token"])
    before = len(_rows())

    # A document added the ordinary way.
    added = client.post(f"/api/v1/applications/{app_id}/documents",
                        json={"doc_type": "id_proof", "file_name": "aadhaar.pdf"},
                        headers=_headers(world["priya"]["token"]))
    # Staff verifying it.
    client.patch(f"/api/v1/applications/{app_id}/documents/{added.json()['id']}/verify",
                 headers=_headers(world["officer"]["token"]))
    # The admin changing a setting.
    client.put("/api/v1/admin/settings/real-uploads", json={"enabled": True},
               headers=_headers(world["admin"]["token"]))
    # Somebody signing in.
    _login(client, world["rahul"]["email"])
    # Staff reading the dashboard.
    client.get("/api/v1/dashboard/summary", headers=_headers(world["officer"]["token"]))

    assert len(_rows()) == before


# ---------------------------------------------------------------------------
# The database keeps the audiences apart itself
# ---------------------------------------------------------------------------

def test_a_staff_message_cannot_be_filed_as_a_customers(db_session):
    from sqlalchemy.exc import DatabaseError

    db_session.add(Notification(
        recipient_user_id=1,
        audience=NotificationAudience.applicant,      # wrong audience for this type
        type=NotificationType.edit_requested,
        title="Edit request", body="Should never be stored",
    ))
    with pytest.raises(DatabaseError):
        db_session.commit()
    db_session.rollback()


def test_an_empty_message_is_refused(db_session):
    from sqlalchemy.exc import DatabaseError

    db_session.add(Notification(
        recipient_user_id=1,
        audience=NotificationAudience.applicant,
        type=NotificationType.application_status_changed,
        title="   ", body="Nothing in the title",
    ))
    with pytest.raises(DatabaseError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Reading them: always your own
# ---------------------------------------------------------------------------

def test_the_bell_counts_and_clears(client, world):
    app_id = _apply(client, world["priya"]["token"])
    client.patch(f"/api/v1/applications/{app_id}/status",
                 json={"new_status": "under_review", "remarks": "Picked up"},
                 headers=_headers(world["officer"]["token"]))
    priya = _headers(world["priya"]["token"])

    assert client.get("/api/v1/notifications/unread-count", headers=priya).json()["count"] == 2

    listed = client.get("/api/v1/notifications", headers=priya).json()
    assert listed["unread_count"] == 2
    assert [i["title"] for i in listed["items"]] == ["Application updated", "Application submitted"]

    first = listed["items"][0]["id"]
    assert client.post(f"/api/v1/notifications/{first}/read", headers=priya).status_code == 204
    assert client.get("/api/v1/notifications/unread-count", headers=priya).json()["count"] == 1

    assert client.post("/api/v1/notifications/read-all", headers=priya).status_code == 204
    assert client.get("/api/v1/notifications/unread-count", headers=priya).json()["count"] == 0
    # Reading it twice does not count twice.
    assert client.post("/api/v1/notifications/read-all", headers=priya).status_code == 204


def test_unread_only_filters(client, world):
    app_id = _apply(client, world["priya"]["token"])
    client.patch(f"/api/v1/applications/{app_id}/status",
                 json={"new_status": "under_review", "remarks": "Picked up"},
                 headers=_headers(world["officer"]["token"]))
    priya = _headers(world["priya"]["token"])

    newest = client.get("/api/v1/notifications", headers=priya).json()["items"][0]["id"]
    client.post(f"/api/v1/notifications/{newest}/read", headers=priya)

    unread = client.get("/api/v1/notifications", params={"unread_only": True}, headers=priya).json()
    assert [i["title"] for i in unread["items"]] == ["Application submitted"]


def test_you_cannot_read_somebody_elses(client, world):
    app_id = _apply(client, world["priya"]["token"])
    client.post(f"/api/v1/applications/{app_id}/edit-requests",
                json={"fields": ["amount_requested"], "reason": GOOD_REASON},
                headers=_headers(world["priya"]["token"]))

    officer_notice = client.get("/api/v1/notifications",
                                headers=_headers(world["officer"]["token"])).json()["items"][0]["id"]

    # Priya cannot mark the officer's notice as read, and is told it does not
    # exist rather than that it is forbidden.
    refused = client.post(f"/api/v1/notifications/{officer_notice}/read",
                          headers=_headers(world["priya"]["token"]))
    assert refused.status_code == 404

    # And it is still unread for the officer.
    assert client.get("/api/v1/notifications/unread-count",
                      headers=_headers(world["officer"]["token"])).json()["count"] == 1


def test_the_bell_needs_a_login(client):
    assert client.get("/api/v1/notifications").status_code == 401
    assert client.get("/api/v1/notifications/unread-count").status_code == 401
    assert client.post("/api/v1/notifications/read-all").status_code == 401


# ---------------------------------------------------------------------------
# The two systems are independent
# ---------------------------------------------------------------------------

def test_the_activity_log_is_untouched_by_notifications(client, world):
    """
    The point of the whole design. Notifications are not activity rows, and
    creating them adds nothing to the log — a status change writes exactly the
    log rows it always wrote.
    """
    app_id = _apply(client, world["priya"]["token"])
    before = _activity_count()
    notices_before = len(_rows())

    client.patch(f"/api/v1/applications/{app_id}/status",
                 json={"new_status": "under_review", "remarks": "Picked up"},
                 headers=_headers(world["officer"]["token"]))

    # One new log row for the status change, and one new notification.
    assert _activity_count() == before + 1
    assert len(_rows()) == notices_before + 1

    db = TestingSessionLocal()
    actions = {row.action for row in db.query(ActivityLog).all()}
    db.close()
    # No notification ever appears in the log under its own name.
    assert not {a for a in actions if "notification" in a}
