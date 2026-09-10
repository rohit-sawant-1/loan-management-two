"""
The gate that lets Phases 3, 4 and 5 be reachable from the customer-facing
chat without leaking one customer's data to another (Piece 22, T-75).

These are the tests that had to pass before the agent was wired into
`/api/v1/chat` at all. The agent used to call the Phase 1 API as a branch
manager no matter who was asking — invisible while it was only reachable from
a developer's terminal, and a data breach the moment a customer could type
into it.

The design being tested: `acting_as()` makes the AI call the API **as the
person who asked**, so Phase 1's own owner-scoping does the work. There is no
AI-specific permission logic to get wrong, which is the point.
"""

from jose import jwt          # the same library the app itself signs with (T-88)

from app.config import settings
from app.services.loan_api_client import acting_as, service_token


def _claims(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def test_outside_a_request_it_is_still_the_service_identity():
    """The Phase 5 CLI and a developer at a prompt keep the old behaviour."""
    claims = _claims(service_token())

    assert claims["sub"] == settings.agent_service_email
    assert claims["role"] == "branch_manager"


def test_inside_acting_as_the_token_is_the_caller():
    """A customer's question is asked with a customer's identity, not a manager's."""
    with acting_as("priya@example.com", "applicant"):
        claims = _claims(service_token())

    assert claims["sub"] == "priya@example.com"
    assert claims["role"] == "applicant"


def test_a_customer_never_gets_a_manager_token():
    """
    The specific failure this whole piece exists to prevent: a customer asking
    the assistant something must not be handed the widest role in the bank.
    """
    with acting_as("priya@example.com", "applicant"):
        claims = _claims(service_token())

    assert claims["role"] != "branch_manager"
    assert claims["role"] != "loan_officer"


def test_the_identity_is_put_back_afterwards():
    """
    One person's chat request must not leave its identity behind for the next
    one. If it did, whoever asked next would inherit it.
    """
    with acting_as("priya@example.com", "applicant"):
        pass

    claims = _claims(service_token())
    assert claims["sub"] == settings.agent_service_email


def test_it_is_put_back_even_when_the_agent_raises():
    """An exception mid-answer must not strand the caller's identity either."""
    try:
        with acting_as("priya@example.com", "applicant"):
            raise RuntimeError("the model fell over")
    except RuntimeError:
        pass

    claims = _claims(service_token())
    assert claims["sub"] == settings.agent_service_email


def test_a_customer_asking_about_someone_elses_application_is_refused(client):
    """
    End to end, through the real API: Phase 1's owner-scoping refuses the
    request, so the AI never sees the data. This is the test that proves the
    design — no new permission logic, just the one that was already tested.
    """
    officer = client.post("/api/v1/auth/register", json={
        "name": "Gate Officer", "email": "gate.officer@test.com", "password": "Test@1234",
    })
    assert officer.status_code == 201, officer.text
    officer_token = client.post("/api/v1/auth/login", json={
        "email": "gate.officer@test.com", "password": "Test@1234",
    }).json()["access_token"]

    # Someone else's application, created by staff.
    other = client.post("/api/v1/applicants", json={
        "name": "Someone Else", "email": "someone.else@test.com",
        "phone": "9876500000", "credit_score": 700,
        "annual_income": 900000.0, "employment_status": "salaried",
    }, headers={"Authorization": f"Bearer {officer_token}"}).json()

    their_application = client.post("/api/v1/applications", json={
        "applicant_id": other["id"], "loan_type": "personal",
        "amount_requested": 300000.0, "tenure_months": 24, "purpose": "Not yours",
    }, headers={"Authorization": f"Bearer {officer_token}"}).json()

    # A different customer, signing up for themselves.
    client.post("/api/v1/auth/register-applicant", json={
        "name": "Nosy Customer", "email": "nosy@test.com", "password": "Test@1234",
        "phone": "9876511111", "annual_income": 500000.0,
        "employment_status": "salaried", "credit_score": 700,
    })
    nosy_token = client.post("/api/v1/auth/login", json={
        "email": "nosy@test.com", "password": "Test@1234",
    }).json()["access_token"]

    # This is exactly the call the agent's get_application_details tool makes,
    # with the identity acting_as() would have given it.
    peek = client.get(f"/api/v1/applications/{their_application['id']}",
                       headers={"Authorization": f"Bearer {nosy_token}"})

    assert peek.status_code == 403, (
        "A customer reached another customer's application. The chat must never "
        "be able to do what the browser is refused."
    )
