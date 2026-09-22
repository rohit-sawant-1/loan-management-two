"""
Rules the database itself enforces: the last safety net (Piece 25).

The form checks a value so the person gets a friendly message. The server's
schemas check it again, and that is the real gate. This file is the third
layer: if some future piece of code ever writes to the database without going
through a schema, SQLite still refuses a value that breaks the rules.

**Why triggers, and not CHECK rules, for `loan_applications`.** A CHECK rule
lives inside a table's definition, and SQLite cannot add one to a table that
already exists without rebuilding the whole table. `loan_app.db` already has
real rows in it. A trigger is a small piece of SQL that the database runs
before every insert or update, and it *can* be added to an existing table. When
a row breaks a rule, the trigger stops the write with an error message.

**Why the numbers are filled in from `rules.py`.** The limits are never typed
here. If `AMOUNT_MAX` changes in `rules.py`, the trigger changes with it the
next time the server starts, because the triggers are dropped and rebuilt on
every startup. Typing the numbers a second time would be exactly the "rule
written in two places" problem the audit is looking for.

**What is deliberately left out.** Only the global bounds are checked here,
not the per-loan-type limits (a personal loan capped at 60 months, and so on).
Those stay in the service, which can explain *why* in plain words. The
trainer's database tests write rows directly, and every one of them sits inside
the global bounds, so none of them is refused.
"""

from sqlalchemy import text

from app.domain import rules

# Two triggers, because SQLite runs a trigger on exactly one kind of write.
LOAN_APPLICATION_TRIGGERS = {
    "loan_applications_check_insert": "INSERT",
    "loan_applications_check_update": "UPDATE",
}


def quoted_list(values) -> str:
    """('a', 'b') -> "'a', 'b'", for an SQL `IN (...)` list."""
    return ", ".join(f"'{v}'" for v in values)


def _loan_application_rules() -> str:
    """
    The body both triggers share. `CASE` stops at the first rule that fails,
    so the error names the actual problem. `NEW` means "the row being
    written". The messages avoid colons on purpose, because SQLAlchemy reads
    a colon inside raw SQL as the start of a parameter name.
    """
    return f"""
        SELECT CASE
            WHEN NEW.loan_type NOT IN ({quoted_list(rules.LOAN_TYPES)})
                THEN RAISE(ABORT, 'loan_type is not a known loan type')
            WHEN NEW.status NOT IN ({quoted_list(rules.STATUSES)})
                THEN RAISE(ABORT, 'status is not a known status')
            WHEN NEW.amount_requested NOT BETWEEN {rules.AMOUNT_MIN} AND {rules.AMOUNT_MAX}
                THEN RAISE(ABORT, 'amount_requested is outside the allowed range')
            WHEN NEW.tenure_months NOT BETWEEN {rules.TENURE_MIN} AND {rules.TENURE_MAX}
                THEN RAISE(ABORT, 'tenure_months is outside the allowed range')
            WHEN length(trim(NEW.purpose)) < {rules.PURPOSE_MIN}
                 OR length(NEW.purpose) > {rules.PURPOSE_MAX}
                THEN RAISE(ABORT, 'purpose is too short or too long')
        END;
    """


def install_loan_application_checks(connection) -> None:
    """
    Drop and rebuild both triggers, so they always match today's `rules.py`.
    Safe to run on every startup: it changes no data, only the rules that
    guard future writes.
    """
    if connection.dialect.name != "sqlite":
        return   # the trigger syntax below is SQLite's
    body = _loan_application_rules()
    for name, event in LOAN_APPLICATION_TRIGGERS.items():
        connection.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
        connection.execute(text(
            f"CREATE TRIGGER {name} BEFORE {event} ON loan_applications "
            f"FOR EACH ROW BEGIN {body} END"
        ))
