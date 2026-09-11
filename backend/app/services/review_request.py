"""
Did this person ask for a full underwriting review, and of which application?

Phase 5's four-agent review is two AI calls and roughly ten seconds of waiting.
That is worth it when somebody asks for it, and a waste when they did not — so
the decision of *when* to run one is made here, in plain Python, rather than
handed to the model as a tool it may choose.

**Why not a tool.** Given the choice, a model sometimes runs the review and
sometimes does not, for the same question asked twice. On stage that is the
worst possible behaviour: either a ten-second pause nobody asked for, or a quick
lookup when the person wanted a verdict. A phrase check always does the same
thing, and can be tested exhaustively without spending a single AI call.

**Why the pattern is anchored to the whole message.** This is the load-bearing
part. Consider:

    "assess application 7"            -> a review, clearly
    "what happened to application 7"  -> a question, clearly NOT a review

An unanchored search for a verb and a number would fire on both, because the
second sentence contains "application 7" too. Requiring the message to *start*
with the instruction and contain nothing else separates them cleanly. The cost
is that someone must type the instruction on its own, which is exactly the
predictability we want here.
"""

from __future__ import annotations

import re

# The four verbs that mean "run the full underwriting review". A short closed
# list rather than anything fuzzy, in the same spirit as
# `pending_actions.looks_like_yes`: being wrong costs a ten-second wait for
# something nobody asked for, so anything not plainly a review request is left
# to the ordinary agent instead.
#
# `review` is the one to watch, because "under review" is also a status. The
# anchor saves us: "set application 7 to under review" does not *start* with it.
#
# `\d{1,9}` rather than `\d+` so a four-hundred-digit number never reaches
# int() and then a URL.
_TRIGGER = re.compile(
    r"^\s*(?:please\s+)?"           # a polite opener, optional
    r"(?:assess|review|evaluate|underwrite)\s+"
    r"(?:loan\s+)?application\s+"   # "loan application 7" reads naturally too
    r"#?(\d{1,9})"                  # the number, with or without a #
    r"\s*[.!?]?\s*$",               # trailing punctuation, and nothing else
    re.IGNORECASE,
)


def review_target(message: str) -> str | None:
    """
    The application number this person asked for a full review of, or None.

    Returned as a string because that is what `evaluate_loan_application` takes:
    it does its own int() conversion and reports a bad value as an error in its
    result rather than raising.

    A mirror of this lives in `frontend/src/pages/Assistant.jsx`, used only to
    decide whether to show the "this takes about ten seconds" line while
    waiting. If you change the wording here, change it there too.
    """
    match = _TRIGGER.match(message or "")
    return match.group(1) if match else None
