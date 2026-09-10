"""
What goes in and out of the one chat address.

Kept deliberately open at the edges so the later phases can add to it without
changing what the screens already send. `mode` tells the screen which brain
answered, and `sources` lets it show the manual extracts the answer came from —
which is what turns "trust the AI" into "check the AI".
"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=0, max_length=2000,
                         description="What the person typed")
    session_id: str | None = Field(
        None, max_length=64,
        description="Groups messages into one conversation. Phase 4 uses it for "
                    "session memory; Phase 2 accepts and ignores it.",
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
