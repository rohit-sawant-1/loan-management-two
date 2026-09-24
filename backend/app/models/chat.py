"""
Piece 36: saved conversations with the Assistant.

`chat_sessions` is one row per conversation; `chat_messages` is one row per
message in it, the question and the answer each saved separately. They live
on the server, tied to the person, never in the browser (Rule 13).

A conversation is private to the person who had it. Not even staff or the
administrator can open someone else's; the service answers "not found".

The AI still sees only the question in front of it (Piece 36, decision 2).
These tables are history for people to reread, not memory for the AI.

Both tables are new, so their rules sit in the table definitions as plain
CHECK constraints, the same as `document_extractions`.
"""

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # The first question's first 60 characters. No AI call to write a title.
    title = Column(String(60), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Moved on every new message, so the list shows the latest chat first.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    archived = Column(Boolean, nullable=False, default=False)

    messages = relationship(
        "ChatMessage", back_populates="session",
        cascade="all, delete-orphan", order_by="ChatMessage.id",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)           # user / assistant
    content = Column(Text, nullable=False)
    # Assistant messages only: what the screen needs to redraw the answer,
    # including the "how this was worked out" panel.
    mode = Column(String(20), nullable=True)
    sources = Column(Text, nullable=True)                # JSON list
    tools_used = Column(Text, nullable=True)             # JSON list
    duration_ms = Column(Float, nullable=True)
    ai_notice = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_message_role"),
    )
