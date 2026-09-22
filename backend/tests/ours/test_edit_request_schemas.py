"""
Piece 25: the server's own checks on everything an edit request can carry.

Plain schema tests, with no database and no HTTP. They show exactly what the
server refuses before any of our code runs.
"""

import pytest
from pydantic import ValidationError

from app.schemas.application import CreateApplicationSchema
from app.schemas.edit_request import (
    ApplicationEditBody, ApproveBody, EditRequestCreate, RefuseBody,
)

GOOD_REASON = "I typed one zero too many in the amount"


# --- Asking for an edit ------------------------------------------------------

def test_a_good_request_passes_and_the_reason_is_trimmed():
    body = EditRequestCreate(fields=["amount_requested", "tenure_months"],
                             reason=f"   {GOOD_REASON}   ")
    assert body.reason == GOOD_REASON


@pytest.mark.parametrize("payload", [
    {"fields": [], "reason": GOOD_REASON},                                  # nothing asked for
    {"fields": ["loan_type"], "reason": GOOD_REASON},                       # not editable
    {"fields": ["status"], "reason": GOOD_REASON},                          # not editable
    {"fields": ["purpose", "purpose"], "reason": GOOD_REASON},              # listed twice
    {"fields": ["purpose"], "reason": "too short"},                         # 9 characters
    {"fields": ["purpose"], "reason": "     tiny     "},                   # short once trimmed
    {"fields": ["purpose"], "reason": "x" * 1001},                          # too long
    {"fields": ["purpose"], "reason": "Wrong amount\x00 here, sorry"},      # hidden character
    {"fields": ["purpose"], "reason": GOOD_REASON, "status": "approved"},   # unknown key
])
def test_a_bad_request_is_refused(payload):
    with pytest.raises(ValidationError):
        EditRequestCreate(**payload)


def test_a_reason_may_have_line_breaks():
    body = EditRequestCreate(fields=["purpose"], reason="Wrong purpose.\nIt is for a car, not a house.")
    assert "\n" in body.reason


# --- Staff deciding -----------------------------------------------------------

def test_an_approval_note_is_optional_and_blank_means_none():
    assert ApproveBody().note is None
    assert ApproveBody(note="   ").note is None
    assert ApproveBody(note=" Fine, go ahead ").note == "Fine, go ahead"


def test_a_refusal_must_say_why():
    with pytest.raises(ValidationError):
        RefuseBody()
    with pytest.raises(ValidationError):
        RefuseBody(note="no")
    assert RefuseBody(note="Your payslips show a lower income").note


# --- Saving the approved edit -------------------------------------------------

def test_an_edit_keeps_only_the_fields_that_were_sent():
    body = ApplicationEditBody(amount_requested=150000)
    assert body.changed_fields() == {"amount_requested": 150000}


@pytest.mark.parametrize("payload", [
    {},                                                    # nothing to change
    {"amount_requested": 5},                               # under the global minimum
    {"tenure_months": 500},                                # over the global maximum
    {"purpose": "   "},                                    # empty once trimmed
    {"purpose": "x" * 501},
    {"amount_requested": 150000, "loan_type": "home"},     # loan type cannot be changed
    {"amount_requested": 150000, "status": "approved"},    # nor can the status
])
def test_a_bad_edit_is_refused(payload):
    with pytest.raises(ValidationError):
        ApplicationEditBody(**payload)


# --- The tightened purpose check on a brand-new application ------------------

def _new_application(purpose: str):
    return CreateApplicationSchema(applicant_id=1, loan_type="personal",
                                   amount_requested=100000, tenure_months=24, purpose=purpose)


def test_a_purpose_of_only_spaces_is_now_refused():
    with pytest.raises(ValidationError):
        _new_application("     ")


def test_a_purpose_that_was_valid_before_is_still_valid_and_trimmed():
    assert _new_application("  Home renovation  ").purpose == "Home renovation"
    assert _new_application("Test").purpose == "Test"   # the trainer's own value
