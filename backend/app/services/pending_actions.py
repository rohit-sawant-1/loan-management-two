"""
The one change a person has been asked to confirm, held between two messages.

A write tool in `agent/write_tools.py` does not perform its change. It records
it here and asks the person to reply yes. This module holds that recorded call
until they do, then runs it — the exact arguments that were proposed, never a
fresh guess from the model.

Three deliberate choices
------------------------

**Kept on the server, never in the browser.** Rule 13: the browser holds a login
token and nothing else that matters. A pending "disburse application 7" sitting
in a customer's local storage would be both customer data and something worth
tampering with.

**One per person, not a queue.** If someone proposes a change and then types a
different instruction before confirming, the newer one replaces the older. A
queue would let a forgotten "yes" land on something they typed five minutes ago,
which is precisely the accident the confirmation exists to prevent.

**It expires.** Five minutes. An abandoned confirmation must not be completable
an hour later, when the screen has scrolled and nobody remembers what
application 5 even was.

Held in memory rather than in the database on purpose. It is scratch state worth
seconds, and a restart losing it is correct behaviour — after a restart nobody
should be able to confirm a change they proposed before it.
"""

from __future__ import annotations

import time
from contextvars import ContextVar

import structlog

logger = structlog.get_logger()

# How long a proposed change stays confirmable.
EXPIRY_SECONDS = 300

# Who the current request belongs to. Set by the chat endpoint, the same way
# `acting_as()` does it, so a write tool deep inside the agent knows whose
# pending action it is writing without every layer having to pass it down.
_current_owner: ContextVar[str | None] = ContextVar("_pending_owner", default=None)

# owner email -> the one change they have been asked to confirm.
_pending: dict[str, dict] = {}


def owned_by(email: str):
    """
    Mark every pending action created in this block as belonging to this person.

    Used by the chat endpoint as a context manager, around the agent call.
    """
    class _Owner:
        def __enter__(self):
            self._token = _current_owner.set(email)
            return self

        def __exit__(self, *exc):
            _current_owner.reset(self._token)
            return False

    return _Owner()


def remember(tool_name: str, arguments: dict, description: str) -> None:
    """Hold a proposed change until its owner confirms it."""
    owner = _current_owner.get()
    if owner is None:
        # No owner means nobody can ever confirm it, so recording it would be a
        # slow leak of things that can never happen. Only reachable from a
        # developer's prompt, never from the endpoint.
        logger.warning("pending_action_without_owner", operation="write_proposed",
                       tool=tool_name)
        return

    _pending[owner] = {
        "tool": tool_name,
        "arguments": arguments,
        "description": description,
        "created_at": time.monotonic(),
    }


def peek(email: str) -> dict | None:
    """The change this person has been asked to confirm, if it has not expired."""
    action = _pending.get(email)
    if action is None:
        return None

    if time.monotonic() - action["created_at"] > EXPIRY_SECONDS:
        _pending.pop(email, None)
        logger.info("pending_action_expired", operation="write_expired",
                    tool=action["tool"])
        return None

    return action


def clear(email: str) -> None:
    _pending.pop(email, None)


def looks_like_yes(message: str) -> bool:
    """
    Did this person just agree?

    Deliberately a short, closed list rather than anything clever. The cost of
    reading "no, not that one" as agreement is a wrongly rejected loan, so
    anything not plainly affirmative is treated as a new instruction instead —
    the safe direction to be wrong in.
    """
    said = message.strip().lower().rstrip(".!")
    return said in {
        "yes", "y", "yes please", "yep", "yeah", "ok", "okay", "confirm",
        "confirmed", "go ahead", "do it", "proceed", "yes go ahead",
        "yes do it", "yes confirm", "sure",
    }


def looks_like_no(message: str) -> bool:
    """An explicit refusal, so we can drop the action and say so."""
    said = message.strip().lower().rstrip(".!")
    return said in {
        "no", "n", "nope", "cancel", "stop", "don't", "dont", "no thanks",
        "nevermind", "never mind", "abort", "no cancel",
    }


def run(action: dict) -> tuple[bool, str]:
    """
    Perform a confirmed change.

    Calls the same MCP tool Phase 4 exposes, so there is one definition of each
    operation rather than a second one written for the chat. Returns
    (worked, sentence-to-show).

    The arguments are the ones recorded when the change was proposed. The model
    is not consulted again, which is the whole point: it cannot change its mind
    about which application this was.
    """
    from mcp_server import mcp_app

    handlers = {
        "update_application_status": mcp_app.update_application_status,
        "submit_loan_application": mcp_app.submit_loan_application,
        "upload_document_metadata": mcp_app.upload_document_metadata,
    }

    handler = handlers.get(action["tool"])
    if handler is None:
        return False, "That change is no longer available."

    result = handler(**action["arguments"])

    if isinstance(result, dict) and "error" in result:
        detail = result.get("detail", result["error"])
        logger.warning("write_refused", operation="write_confirmed",
                       tool=action["tool"], error=str(detail)[:200])
        # The API refused it — most often a permission rule, such as an officer
        # trying to disburse. Read it back plainly rather than dressing it up.
        return False, f"That did not go through. {detail}"

    logger.info("write_confirmed", operation="write_confirmed",
                tool=action["tool"], arguments=action["arguments"])
    return True, f"Done. {action['description'].replace('About to ', '', 1).capitalize()}"
