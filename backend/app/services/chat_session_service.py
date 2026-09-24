"""
The logic behind saved conversations (Piece 36).

Every function here takes the person asking and only ever touches their own
conversations. Anyone else's, whoever is asking (a customer, staff, the
admin), is "not found", so its existence isn't even given away.
"""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.services.errors import NotFound

# How many chats the side list shows. A person rarely needs more than the
# latest few; anything older can simply be started again.
LIST_LIMIT = 50


def _own_session(db: Session, session_id, user: User) -> ChatSession:
    """The person's own conversation, or NotFound. Accepts the id as text too."""
    try:
        sid = int(session_id)
    except (TypeError, ValueError):
        raise NotFound("Conversation not found") from None
    session = db.query(ChatSession).filter(ChatSession.id == sid).first()
    if session is None or session.user_id != user.id:
        raise NotFound("Conversation not found")
    return session


def open_or_start(db: Session, user: User, session_id, first_message: str) -> ChatSession:
    """
    The conversation a message belongs to. No id means a new conversation,
    titled with the first 60 characters of its first question. (Which chat a
    waiting "reply YES" belongs to is handled by the chat route.)
    """
    if session_id:
        return _own_session(db, session_id, user)
    session = ChatSession(user_id=user.id, title=first_message.strip()[:60] or "New chat")
    db.add(session)
    db.flush()
    return session


def save_turn(db: Session, session: ChatSession, question: str, response) -> None:
    """Save the question and the answer, in that order, and move the chat to the top of the list."""
    db.add(ChatMessage(session_id=session.id, role="user", content=question))
    db.add(ChatMessage(
        session_id=session.id, role="assistant", content=response.answer,
        mode=response.mode,
        sources=json.dumps([s.model_dump() for s in response.sources]),
        tools_used=json.dumps([t.model_dump() for t in response.tools_used]),
        duration_ms=response.duration_ms,
        ai_notice=(response.ai_notice or None),
    ))
    session.updated_at = datetime.now(timezone.utc)
    db.commit()


def list_sessions(db: Session, user: User) -> list[ChatSession]:
    """The person's chats that aren't archived, the most recently used first."""
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.archived.is_(False))
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .limit(LIST_LIMIT)
        .all()
    )


def messages(db: Session, session_id, user: User, limit: int = 30,
             before_id: int | None = None) -> tuple[list[ChatMessage], bool]:
    """
    The latest `limit` messages of one of the person's chats, oldest first,
    and whether there are older ones. `before_id` fetches the page before it
    ("Load earlier").
    """
    session = _own_session(db, session_id, user)
    query = db.query(ChatMessage).filter(ChatMessage.session_id == session.id)
    if before_id is not None:
        query = query.filter(ChatMessage.id < before_id)
    # One extra row tells us whether anything older exists.
    rows = query.order_by(ChatMessage.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    return list(reversed(rows[:limit])), has_more


def update(db: Session, session_id, user: User, title: str | None = None,
           archived: bool | None = None) -> ChatSession:
    """Rename or archive one of the person's chats."""
    session = _own_session(db, session_id, user)
    if title is not None:
        session.title = title
    if archived is not None:
        session.archived = archived
    db.commit()
    db.refresh(session)
    return session


def message_out(message: ChatMessage) -> dict:
    """A saved message in the shape the screen uses, JSON lists turned back into lists."""
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "mode": message.mode,
        "sources": json.loads(message.sources) if message.sources else [],
        "tools_used": json.loads(message.tools_used) if message.tools_used else [],
        "duration_ms": message.duration_ms,
        "ai_notice": message.ai_notice or "",
        "created_at": message.created_at,
    }
