


"""Response schemas for generation and validation tools."""

from typing import Literal
from pydantic import BaseModel, Field, field_validator


class GenerationToolResponse(BaseModel):
    context_id: str = ""
    resolution_available: bool
    confidence: float = Field(ge=0, le=1)
    resolution_steps: list[str] = Field(default_factory=list)
    cited_ticket_ids: list[str] = Field(default_factory=list)
    reasoning: str

    @field_validator("resolution_steps", "cited_ticket_ids")
    @classmethod
    def clean_list(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


class ValidationToolResponse(BaseModel):
    context_id: str = ""
    verdict: Literal["approved", "context_missing", "generation_issue", "human_handoff"]
    all_issues_addressed: bool
    grounded_in_retrieval: bool
    missing_issues: list[str] = Field(default_factory=list)
    unsupported_steps: list[str] = Field(default_factory=list)
    feedback: str
    recommended_action: Literal["finalize", "retrieve_again", "regenerate", "human_handoff"]