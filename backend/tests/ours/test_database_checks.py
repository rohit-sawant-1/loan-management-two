"""
Piece 25: the database refuses bad values on its own, even when our code is
skipped.

Every insert here is raw SQL, not a model or a schema, on purpose. The point is
to prove the third layer works by itself: if some future piece of code ever
writes to the database without going through the schemas, SQLite still says no.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db_checks import LOAN_APPLICATION_TRIGGERS, install_loan_application_checks
from app.models.application import ApplicationStatus, LoanApplication

GOOD_APPLICATION = {
    "applicant_id": 1, "loan_type": "personal", "amount_requested": 100000,
    "tenure_months": 24, "purpose": "Home renovation", "status": "submitted",
}


def _insert_application(db, **overrides) -> int:
    row = {**GOOD_APPLICATION, **overrides}
    result = db.execute(text(
        "INSERT INTO loan_applications "
        "(applicant_id, loan_type, amount_requested, tenure_months, purpose, status) "
        "VALUES (:applicant_id, :loan_type, :amount_requested, :tenure_months, :purpose, :status)"
    ), row)
    db.commit()
    return result.lastrowid


def _insert_edit_request(db, application_id, **overrides):
    row = {
        "application_id": application_id, "requested_by": "priya@example.com",
        "fields": '["amount_requested"]', "reason": "I typed one zero too many",
        "status": "pending", "decision_note": None,
    }
    row.update(overrides)
    db.execute(text(
        "INSERT INTO application_edit_requests "
        "(application_id, requested_by, fields, reason, status, decision_note) "
        "VALUES (:application_id, :requested_by, :fields, :reason, :status, :decision_note)"
    ), row)
    db.commit()


# --- loan_applications: the triggers ----------------------------------------

def test_a_good_application_row_still_saves(db_session):
    assert _insert_application(db_session) > 0


def test_the_trainers_style_of_row_still_saves(db_session):
    """The trainer's DB tests build rows through the model like this one."""
    app = LoanApplication(applicant_id=1, loan_type="personal",
                          amount_requested=50000, tenure_months=12, purpose="Test")
    db_session.add(app)
    db_session.commit()
    assert app.status == ApplicationStatus.submitted


@pytest.mark.parametrize("overrides, message", [
    ({"amount_requested": 5}, "amount_requested"),
    ({"amount_requested": 20_000_000}, "amount_requested"),
    ({"tenure_months": 1}, "tenure_months"),
    ({"tenure_months": 500}, "tenure_months"),
    ({"purpose": "x" * 600}, "purpose"),
    ({"purpose": "   "}, "purpose"),
    ({"loan_type": "boat"}, "loan_type"),
    ({"status": "banana"}, "status"),
])
def test_a_bad_application_row_is_refused(db_session, overrides, message):
    with pytest.raises(IntegrityError) as caught:
        _insert_application(db_session, **overrides)
    db_session.rollback()
    assert message in str(caught.value)


def test_an_update_to_a_bad_value_is_refused_too(db_session):
    app_id = _insert_application(db_session)
    with pytest.raises(IntegrityError):
        db_session.execute(text("UPDATE loan_applications SET amount_requested = 5 WHERE id = :id"),
                           {"id": app_id})
        db_session.commit()
    db_session.rollback()

    # A good update on the same row still works.
    db_session.execute(text("UPDATE loan_applications SET amount_requested = 150000 WHERE id = :id"),
                       {"id": app_id})
    db_session.commit()


def test_installing_the_checks_again_does_not_duplicate_them(db_session):
    """They are rebuilt on every startup, so running this twice must be harmless."""
    connection = db_session.connection()
    install_loan_application_checks(connection)
    install_loan_application_checks(connection)
    names = {row[0] for row in connection.execute(
        text("SELECT name FROM sqlite_master WHERE type = 'trigger'"))}
    assert set(LOAN_APPLICATION_TRIGGERS) <= names


# --- application_edit_requests: the CHECK rules -----------------------------

def test_a_good_edit_request_row_saves(db_session):
    _insert_edit_request(db_session, _insert_application(db_session))


def test_a_refusal_with_a_note_saves(db_session):
    _insert_edit_request(db_session, _insert_application(db_session),
                         status="refused", decision_note="Your documents show the original amount")


@pytest.mark.parametrize("overrides", [
    {"reason": "short"},                       # under 10 characters
    {"reason": "          x"},                 # only 1 character once trimmed
    {"fields": "[]"},                          # asks to change nothing
    {"fields": "amount_requested"},            # not a JSON list
    {"status": "banana"},
    {"status": "refused"},                     # a refusal with no note
    {"status": "refused", "decision_note": "no"},   # a note too short to be a reason
    {"decision_note": "x" * 1001},
])
def test_a_bad_edit_request_row_is_refused(db_session, overrides):
    app_id = _insert_application(db_session)
    with pytest.raises(IntegrityError):
        _insert_edit_request(db_session, app_id, **overrides)
    db_session.rollback()
