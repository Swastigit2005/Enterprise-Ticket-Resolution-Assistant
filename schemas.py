from typing import List
from pydantic import BaseModel, Field

class ResolutionResponse(BaseModel):

    resolution_available: bool = Field(
        description="Whether a resolution is available"
    )

    confidence: float = Field(
        description="Confidence score between 0 and 1"
    )

    recommended_resolution: List[str] = Field(
        description="Ordered workflow steps"
    )

    reasoning: str = Field(
        description="Brief explanation"
    )