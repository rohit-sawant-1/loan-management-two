"""
What goes in and out of the one chat address.

Kept deliberately open at the edges so the later phases can add to it without
changing what the screens already send. `mode` tells the screen which brain
answered, and `sources` lets it show the manual extracts the answer came from —
which is what turns "trust the AI" into "check the AI".
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import UtcDateTime, clean_free_text


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=0, max_length=2000,
                         description="What the person typed")
    session_id: str | None = Field(
        None, max_length=64,
        description="Which saved conversation this message belongs to (Piece 36). "
                    "Left out, a new conversation is started. Someone else's is refused.",
    )


class ChatSource(BaseModel):
    """One extract from the manual that the answer was based on."""
    chunk_id: str | None = None
    source: str | None = None
    excerpt: str


class ChatToolCall(BaseModel):
    """One tool the agent decided to use while working out its answer."""
    tool: str = Field(..., description="The tool's name, e.g. search_loan_policy")
    tool_input: str = Field("", description="What the agent passed to it, shortened")


class ChatResponse(BaseModel):
    answer: str
    # Which brain answered: "rag" from the manual, "empty" for a blank message,
    # "agent" for the Phase 3 tool-using agent. Phase 5 adds "review".
    mode: str
    sources: list[ChatSource] = []
    duration_ms: float
    # Which tools ran, in the order the agent called them. Empty when no tool
    # was needed, or when the answer came straight from the manual chain.
    # Defaulted so nothing that already reads this response has to change.
    tools_used: list[ChatToolCall] = []

    # How the AI behaved while answering this (Piece 23, D-20).
    #
    # `ai_status` is the machine-readable code we grep the logs for; `ai_notice`
    # is the one sentence a customer reads. Two fields rather than one because
    # the screen must never print a code like `ai_quota_exhausted` at a person,
    # and we must never grep logs for a sentence someone may reword later.
    #
    # Both are quiet on a normal answer: "ai_ok" and an empty notice, so the
    # screen shows nothing at all unless something actually went wrong.
    ai_status: str = "ai_ok"
    ai_notice: str = ""

    # Piece 36: the saved conversation this answer went into. The screen
    # sends it back with the next message to carry on in the same chat.
    session_id: int | None = None


# ---------------------------------------------------------------------------
# Piece 36: saved conversations
# ---------------------------------------------------------------------------

class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: UtcDateTime | None = None
    updated_at: UtcDateTime | None = None
    archived: bool = False


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    mode: str | None = None
    sources: list[ChatSource] = []
    tools_used: list[ChatToolCall] = []
    duration_ms: float | None = None
    ai_notice: str = ""
    created_at: UtcDateTime | None = None
    # Piece 37: set only on a message that records attached documents.
    application_id: int | None = None
    document_ids: list[int] = []


class ChatAttachRequest(BaseModel):
    """
    Piece 37: record documents, already uploaded through the normal upload
    address, as an attachment in a chat. Nothing here is a document's contents.
    """
    session_id: str | None = Field(None, max_length=64)
    application_id: int = Field(..., gt=0)
    document_ids: list[int] = Field(..., min_length=1, max_length=3)
    # One per attachment event, reused on its retries (retry-safe).
    attach_key: str = Field(..., pattern=r"^[A-Za-z0-9-]{8,40}$")

    @field_validator("document_ids")
    @classmethod
    def _distinct_ids(cls, ids):
        if len(set(ids)) != len(ids) or any(i <= 0 for i in ids):
            raise ValueError("Each document may be listed once, by its id")
        return ids


class ChatAttachResponse(BaseModel):
    session_id: int
    message: ChatMessageOut


class ChatMessagesPage(BaseModel):
    items: list[ChatMessageOut]
    has_more: bool      # are there older messages to "Load earlier"?


class ChatSessionUpdate(BaseModel):
    """Rename or archive a chat. Both optional; only what's sent changes."""
    title: str | None = Field(None, max_length=60)
    archived: bool | None = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, value):
        return None if value is None else clean_free_text(value, 1, 60, "Title")
