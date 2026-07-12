"""Pydantic contracts used by the autonomous ticket-resolution agent."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReferenceTicket(BaseModel):
    """A historical ticket used as evidence for the proposed resolution."""

    ticket_id: str = Field(description="Historical ticket identifier")
    similarity_distance: float = Field(
        description="Vector distance returned by Chroma; lower is more similar",
        ge=0,
    )


class RetrievedTicketChunk(ReferenceTicket):
    """A retrieved historical ticket plus the text supplied to downstream tools."""

    document: str = Field(description="Historical issue and resolution text")


class RetrievalToolResponse(BaseModel):
    """Machine-readable output from the vector retrieval tool."""

    status: Literal["context_found", "context_insufficient", "error"]
    search_string: str
    context_sufficient: bool
    best_distance: float | None = None
    embedding_mode: Literal["plain", "query_prompt"] | None = None
    retrieved_chunks: list[RetrievedTicketChunk] = Field(default_factory=list)
    message: str


class GenerationToolResponse(BaseModel):
    """Output produced only by the LLM-backed resolution-generation tool."""

    resolution_available: bool
    confidence: float = Field(ge=0, le=1)
    resolution_steps: list[str] = Field(default_factory=list)
    cited_ticket_ids: list[str] = Field(default_factory=list)
    reasoning: str

    @field_validator("resolution_steps")
    @classmethod
    def remove_empty_steps(cls, value: list[str]) -> list[str]:
        return [step.strip() for step in value if step and step.strip()]


class ValidationToolResponse(BaseModel):
    """Quality verdict used by the central agent to decide its next action."""

    verdict: Literal[
        "approved",
        "context_missing",
        "generation_issue",
        "human_handoff",
    ]
    all_issues_addressed: bool
    grounded_in_retrieval: bool
    missing_issues: list[str] = Field(default_factory=list)
    unsupported_steps: list[str] = Field(default_factory=list)
    feedback: str
    recommended_action: Literal[
        "finalize",
        "retrieve_again",
        "regenerate",
        "human_handoff",
    ]


class AgentResolutionResponse(BaseModel):
    """Hard response contract returned by the autonomous central agent."""

    status: Literal["resolved", "human_handoff_required"]
    resolution_available: bool
    confidence: float = Field(ge=0, le=1)
    resolution_steps: list[str] = Field(default_factory=list)
    reference_tickets: list[ReferenceTicket] = Field(default_factory=list)
    validation_feedback: str
    reasoning: str
    human_handoff: bool
    handoff_reason: str | None = None

    @field_validator("resolution_steps")
    @classmethod
    def remove_empty_final_steps(cls, value: list[str]) -> list[str]:
        return [step.strip() for step in value if step and step.strip()]