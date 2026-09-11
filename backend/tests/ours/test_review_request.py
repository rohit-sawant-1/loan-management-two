"""
The phrase that starts a four-agent review, and the many that must not.

This is the smallest file in the project and one of the most important. The
trigger decides whether a question costs ten seconds and two AI calls or
answers instantly, and getting it slightly wrong is not obvious until it
happens in front of somebody.

Pure string matching — no AI, no network, no database. The whole file runs in
well under a second, so there is no reason not to be thorough.
"""

import pytest

from app.services.review_request import review_target


@pytest.mark.parametrize("message, expected", [
    # The plain form, and the capitalisation people actually type.
    ("assess application 7", "7"),
    ("Assess Application 7", "7"),
    ("ASSESS APPLICATION 7", "7"),

    # All four verbs mean the same thing.
    ("review application 12", "12"),
    ("evaluate application 3", "3"),
    ("underwrite application 5", "5"),

    # The near-misses a demo audience will genuinely type.
    ("evaluate application #3", "3"),
    ("underwrite loan application 5", "5"),
    ("please assess application 8", "8"),
    ("please assess application 8.", "8"),
    ("assess application 7!", "7"),
    ("  assess application 7  ", "7"),
])
def test_these_are_review_requests(message, expected):
    assert review_target(message) == expected


@pytest.mark.parametrize("message", [
    # The one this whole design exists to get right. It contains "application 7"
    # and it is a question, not an instruction.
    "what happened to application 7",
    "why was application 7 rejected",
    "tell me about application 7",
    "show me application 7",

    # "review" is also a status word. This is an instruction to change a
    # record, and must reach the write tools rather than the reviewer.
    "set application 7 to under review",
    "move application 7 to under_review",

    # Verbs that belong to other tools entirely.
    "approve application 1, looks fine",
    "reject application 7, income too low",
    "disburse application 5",

    # A review of something that is not one numbered application.
    "assess my eligibility",
    "review the manual",
    "assess all pending applications",

    # Ambiguous: two numbers is not one review, so let the agent ask.
    "assess application 7 and 9",
    "assess application 7 and application 9",

    # A number we cannot use.
    "assess application seven",
    "assess application",

    # Confirmations, which must keep reaching the pending-action check.
    "yes",
    "no",

    # Nothing at all.
    "",
    "   ",
])
def test_these_are_not(message):
    assert review_target(message) is None


def test_a_silly_long_number_is_refused_rather_than_passed_on():
    """
    Capped at nine digits on purpose. Without the cap this would be handed
    straight to int() and then into a URL, which is a pointless thing to allow
    when no real application id is ever that long.
    """
    assert review_target("assess application " + "9" * 400) is None


def test_none_and_nonsense_do_not_raise():
    """Called on every chat message, so it must never be the thing that breaks."""
    assert review_target(None) is None
    assert review_target("🙂") is None
