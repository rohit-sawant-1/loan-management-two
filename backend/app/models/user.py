"""
The `users` table: who can log in.

This is separate from `applicants` (who borrows money). A loan officer has a
user row but no applicant row. A customer who signed up themselves has both,
linked through applicant.user_id. See TRAPS T-07 and decision D-07.
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class UserRole(str, enum.Enum):
    # Same strings as ROLES in app/domain/rules.py
    applicant = "applicant"
    loan_officer = "loan_officer"
    branch_manager = "branch_manager"
    # Piece 27: the System Administrator. Sees everything, can't do loan business.
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    # Never the real password. Always the bcrypt hash of it.
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.loan_officer)
    # Lets a manager switch an account off without deleting its history.
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
