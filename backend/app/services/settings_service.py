"""
Reading and changing the system settings (Piece 28).

Everything here goes through `rules.SETTINGS`. A key that isn't in that
registry is refused, both here and by the database's own check, so a typo can
never quietly create a setting that nothing reads.

Changing a setting writes an activity row, because it changes how the app
behaves for everybody and an auditor should be able to see who did it. It
deliberately sends no notification: the three notification triggers are
settled, and this is not one of them.
"""

import json

import structlog
from sqlalchemy.orm import Session

from app.domain import rules
from app.models.app_setting import AppSetting
from app.services import activity_service
from app.services.errors import RuleViolation

logger = structlog.get_logger()


def _row(db: Session, key: str) -> AppSetting | None:
    return db.query(AppSetting).filter(AppSetting.key == key).first()


def _check_known(key: str) -> None:
    if key not in rules.SETTINGS:
        raise RuleViolation(f"'{key}' is not a setting this app has")


def get(db: Session, key: str):
    """The stored value, or the registry default when nobody has set it yet."""
    _check_known(key)
    row = _row(db, key)
    if row is None:
        return rules.setting_default(key)
    try:
        return json.loads(row.value)
    except json.JSONDecodeError:
        # Unreadable text in the column would otherwise take the whole app
        # down on every page load. The default is the safe answer: it is what
        # the app did before the setting existed.
        logger.warning("setting_unreadable", key=key, stored=row.value[:50])
        return rules.setting_default(key)


def get_all(db: Session) -> dict:
    """Every setting and its current value, for the screens that read them."""
    return {key: get(db, key) for key in rules.SETTINGS}


def describe(db: Session, key: str) -> dict:
    """One setting with the extras the admin screen shows: who changed it, and when."""
    _check_known(key)
    row = _row(db, key)
    entry = rules.SETTINGS[key]
    return {
        "key": key,
        "value": get(db, key),
        "label": entry["label"],
        # The words for each position come from the registry too, so the
        # screen never has its own copy of what a setting means.
        "off_text": entry["off_text"],
        "on_text": entry["on_text"],
        "updated_by": row.updated_by if row else None,
        "updated_at": row.updated_at if row else None,
    }


def set_value(db: Session, key: str, value, *, user, meta: dict | None = None) -> dict:
    """
    Store a new value and record who changed it.

    The type is checked against the registry rather than trusted, because this
    is also reachable from anything that imports the service, not only from the
    address with its Pydantic body.
    """
    _check_known(key)
    expected = rules.SETTINGS[key]["type"]
    if expected == "bool" and not isinstance(value, bool):
        raise RuleViolation(f"'{key}' is a yes/no setting")

    before = get(db, key)
    row = _row(db, key)
    if row is None:
        row = AppSetting(key=key)
        db.add(row)
    row.value = json.dumps(value)
    row.updated_by = user.email

    activity_service.record(
        db, action="setting_changed", actor_id=user.email, actor_role=user.role.value,
        entity_type="setting", details={"key": key, "from": before, "to": value},
        **(meta or {}),
    )
    db.commit()
    db.refresh(row)
    logger.info("setting_changed", key=key, value=value, changed_by=user.email)
    return describe(db, key)
