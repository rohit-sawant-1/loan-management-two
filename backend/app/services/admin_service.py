"""
The System Administrator's own reads (Piece 27).

For now it's just the list of accounts. Piece 28 adds the system settings here.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain import rules
from app.models.user import User


def list_users(db: Session) -> tuple[list[User], dict[str, int]]:
    """Every login, oldest first, and how many there are of each role."""
    users = db.query(User).order_by(User.id).all()

    # Every role is present, even at zero, so the screen never has to guess
    # which keys exist. The dashboard follows the same rule.
    counts = {role: 0 for role in rules.ROLES}
    for role, count in db.query(User.role, func.count(User.id)).group_by(User.role).all():
        counts[role.value] = count
    return users, counts
