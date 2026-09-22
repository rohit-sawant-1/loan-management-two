"""
Piece 28: the administrator's switch for real document uploads.

The switch itself does nothing yet — Piece 31's uploads will read it. What
matters here is that only the admin can move it, that everyone else can read
it, that OFF is exactly the old behaviour, and that moving it is recorded.

Offline. No AI, no files.
"""

import json

import pytest

from app.domain import rules
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.user import User, UserRole
from app.services import settings_service
from app.services.errors import RuleViolation
from tests.conftest import TestingSessionLocal

PASSWORD = "Test@1234"
KEY = "real_uploads_enabled"


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, email):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _staff_with_role(client, email, role):
    client.post("/api/v1/auth/register", json={"name": "Role Test", "email": email, "password": PASSWORD})
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    user.role = role
    db.commit()
    db.close()
    return _login(client, email)


@pytest.fixture
def people(client, auth_token):
    """The four kinds of login. `auth_token` is the trainer's loan officer."""
    client.post("/api/v1/auth/register-applicant", json={
        "name": "Priya Settings", "email": "priya.settings@test.com", "password": PASSWORD,
        "phone": "9876500051", "annual_income": 600000.0, "employment_status": "salaried",
    })
    return {
        "admin": _staff_with_role(client, "admin.settings@test.com", UserRole.admin),
        "manager": _staff_with_role(client, "manager.settings@test.com", UserRole.branch_manager),
        "officer": auth_token,
        "customer": _login(client, "priya.settings@test.com"),
    }


def _set(client, token, enabled):
    return client.put("/api/v1/admin/settings/real-uploads",
                      json={"enabled": enabled}, headers=_headers(token))


# ---------------------------------------------------------------------------
# The default: a database that has never been touched behaves as it did before
# ---------------------------------------------------------------------------

def test_real_uploads_start_switched_off(client, people):
    """Nothing stored yet, so the app does exactly what it did before Piece 28."""
    for who in ("admin", "manager", "officer", "customer"):
        response = client.get("/api/v1/settings", headers=_headers(people[who]))
        assert response.status_code == 200, response.text
        assert response.json() == {"real_uploads_enabled": False}


def test_the_default_comes_from_the_registry_not_a_stored_row(client, people):
    db = TestingSessionLocal()
    assert db.query(AppSetting).count() == 0
    db.close()
    assert rules.setting_default(KEY) is False


# ---------------------------------------------------------------------------
# Only the admin may move it
# ---------------------------------------------------------------------------

def test_the_admin_can_switch_it_on_and_everyone_sees_it(client, people):
    response = _set(client, people["admin"], True)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["value"] is True
    assert body["key"] == KEY
    assert body["label"] == "Real document uploads"
    assert body["updated_by"] == "admin.settings@test.com"
    assert body["updated_at"] is not None

    for who in ("admin", "manager", "officer", "customer"):
        seen = client.get("/api/v1/settings", headers=_headers(people[who])).json()
        assert seen["real_uploads_enabled"] is True, who


def test_switching_it_back_off_works(client, people):
    _set(client, people["admin"], True)
    assert _set(client, people["admin"], False).json()["value"] is False
    assert client.get("/api/v1/settings",
                      headers=_headers(people["customer"])).json()["real_uploads_enabled"] is False


@pytest.mark.parametrize("who", ["manager", "officer", "customer"])
def test_nobody_else_can_move_it(client, people, who):
    assert _set(client, people[who], True).status_code == 403
    # And it really did not move.
    assert client.get("/api/v1/settings",
                      headers=_headers(people["admin"])).json()["real_uploads_enabled"] is False


@pytest.mark.parametrize("who", ["manager", "officer", "customer"])
def test_nobody_else_can_read_the_admin_view_of_it(client, people, who):
    """Who changed it and when is part of the admin's screen."""
    assert client.get("/api/v1/admin/settings/real-uploads",
                      headers=_headers(people[who])).status_code == 403


def test_it_needs_a_login_at_all(client):
    assert client.get("/api/v1/settings").status_code == 401
    assert client.put("/api/v1/admin/settings/real-uploads", json={"enabled": True}).status_code == 401


# ---------------------------------------------------------------------------
# The body has to be right
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"enabled": "yes"},          # a string, not a yes/no
    {"enabled": 1},              # 1 is not True here
    {},                          # nothing at all
    {"enabled": True, "key": "real_uploads_enabled"},   # an extra field
    {"Enabled": True},           # the wrong spelling, which must not pass quietly
])
def test_a_bad_body_is_refused(client, people, body):
    response = client.put("/api/v1/admin/settings/real-uploads",
                          json=body, headers=_headers(people["admin"]))
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Changing it is recorded
# ---------------------------------------------------------------------------

def test_the_change_is_written_to_the_activity_log(client, people):
    _set(client, people["admin"], True)

    db = TestingSessionLocal()
    rows = db.query(ActivityLog).filter(ActivityLog.action == "setting_changed").all()
    details = [json.loads(r.details) for r in rows]
    actors = [(r.actor_id, r.actor_role, r.entity_type) for r in rows]
    db.close()

    assert len(rows) == 1
    assert details[0] == {"key": KEY, "from": False, "to": True}
    assert actors[0] == ("admin.settings@test.com", "admin", "setting")


def test_the_manager_can_see_that_change_on_the_activity_page(client, people):
    _set(client, people["admin"], True)
    body = client.get("/api/v1/activity", params={"action": "setting_changed"},
                      headers=_headers(people["manager"])).json()
    assert body["total_count"] == 1
    # The activity page can filter by this kind of record.
    assert client.get("/api/v1/activity", params={"entity_type": "setting"},
                      headers=_headers(people["manager"])).json()["total_count"] == 1


def test_a_refused_change_records_nothing(client, people):
    client.put("/api/v1/admin/settings/real-uploads",
               json={"enabled": True}, headers=_headers(people["officer"]))
    db = TestingSessionLocal()
    count = db.query(ActivityLog).filter(ActivityLog.action == "setting_changed").count()
    db.close()
    assert count == 0


# ---------------------------------------------------------------------------
# A setting the app does not have
# ---------------------------------------------------------------------------

def test_an_unknown_setting_is_refused_by_the_service(db_session):
    class _Admin:
        email = "admin@bank.com"
        role = UserRole.admin

    with pytest.raises(RuleViolation):
        settings_service.get(db_session, "made_up_setting")
    with pytest.raises(RuleViolation):
        settings_service.set_value(db_session, "made_up_setting", True, user=_Admin())


def test_an_unknown_setting_is_refused_by_the_database_too(db_session):
    """
    The last safety net, the same idea as Piece 25's checks: if some future
    code ever writes straight to the table, SQLite still refuses a key the app
    doesn't know about.
    """
    from sqlalchemy.exc import DatabaseError

    db_session.add(AppSetting(key="made_up_setting", value="true"))
    with pytest.raises(DatabaseError):
        db_session.commit()
    db_session.rollback()


def test_a_wrong_type_is_refused(db_session):
    class _Admin:
        email = "admin@bank.com"
        role = UserRole.admin

    with pytest.raises(RuleViolation):
        settings_service.set_value(db_session, KEY, "yes please", user=_Admin())


def test_unreadable_stored_text_falls_back_to_the_default(db_session):
    """Broken text in the column must not take every page down; the old behaviour is the safe answer."""
    db_session.add(AppSetting(key=KEY, value="not json at all"))
    db_session.commit()

    assert settings_service.get(db_session, KEY) is False
