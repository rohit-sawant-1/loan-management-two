"""
The audit, phase 2: one event must never appear at two different times.

The stored eligibility assessment used to open with its own timestamp, written
as a UTC wall clock. The same instant is also stored in `eligibility_checked_at`,
a real datetime field that the browser renders in the reader's own timezone. So
the application card showed the same assessment at two times five and a half
hours apart — the paragraph in IST, the text below it in UTC.

The rule these tests hold in place: a time is stored once, as a datetime, and
formatted where it is read. Never baked into a sentence on the server.
"""

import re

# Any date-and-time written into prose. Deliberately loose — it should match
# anything that looks like a clock reading, so a differently formatted one
# added later still trips this.
CLOCK = re.compile(r"\d{1,2}:\d{2}")


def _make_applicant(client, auth_token):
    response = client.post("/api/v1/applicants", json={
        "name": "Priya Sharma", "email": "priya@example.com",
        "phone": "9876543210", "credit_score": 720,
        "annual_income": 600000.0, "employment_status": "salaried",
    }, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 201, response.text
    return response.json()


def _submit(client, auth_token, applicant_id):
    response = client.post("/api/v1/applications", json={
        "applicant_id": applicant_id, "loan_type": "personal",
        "amount_requested": 200000.0, "tenure_months": 24, "purpose": "Wedding",
    }, headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 201, response.text
    return response.json()


def test_the_summary_text_contains_no_clock_reading(client, auth_token):
    applicant = _make_applicant(client, auth_token)
    body = _submit(client, auth_token, applicant["id"])
    summary = body["eligibility_summary"]

    assert not CLOCK.search(summary), (
        "The assessment text has a time written into it. That time is a UTC "
        "wall clock while the card beside it is shown in the reader's timezone, "
        "so the same event appears twice, hours apart.\n" + summary[:200]
    )
    assert "UTC" not in summary


def test_the_moment_of_the_assessment_is_still_recorded(client, auth_token):
    """Removing the line must not lose the fact. It moves, it does not vanish."""
    applicant = _make_applicant(client, auth_token)
    body = _submit(client, auth_token, applicant["id"])

    assert body["eligibility_checked_at"] is not None
    # Timezone-aware, so the browser knows what to convert from. A naive
    # timestamp is the same bug in a different costume.
    assert body["eligibility_checked_at"].endswith("Z") or "+" in body["eligibility_checked_at"]


def test_the_assessment_itself_is_untouched(client, auth_token):
    """The repair strips one line. Everything the bank relies on stays."""
    applicant = _make_applicant(client, auth_token)
    body = _submit(client, auth_token, applicant["id"])
    summary = body["eligibility_summary"]

    assert summary.startswith("Applicant:")
    assert "ELIGIBLE" in summary
    assert "PASS" in summary
    assert "Priya Sharma" in summary
