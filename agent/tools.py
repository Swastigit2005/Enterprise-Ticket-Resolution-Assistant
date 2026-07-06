from typing import Any, Dict
import time

from langchain_core.tools import tool
from langchain_groq import ChatGroq

from config import GROQ_MODEL, GROQ_API_KEY
from schemas import ResolutionResponse, ValidationResult
from .prompts import GENERATOR_INSTRUCTION, VALIDATOR_INSTRUCTION
from logger import logger

llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.0)

MAX_CONTEXT_CHARS = 2500
MAX_RETRIES = 3


def _invoke_with_retry(model, prompt: str, tool_name: str):
    delay = 0.2
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return model.invoke(prompt)
        except Exception as exc:
            last_error = exc
            error_text = str(exc).lower()

            if ("429" in error_text or "rate limit" in error_text) and attempt < MAX_RETRIES:
                logger.warning(
                    "%s rate limited on attempt %s/%s; retrying in %.1fs",
                    tool_name,
                    attempt,
                    MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
                continue

            raise

    raise last_error


@tool
def retrieve_similar_tickets(issue_description: str) -> Dict[str, Any]:
    """Tool 1: Retrieve data from vector DB."""
    try:
        from inference import retrieve_context, build_context

        retrieval_data = retrieve_context(issue_description)
        if retrieval_data is None:
            return {"status": "no_results", "message": "No similar tickets found."}

        context = build_context(retrieval_data["chroma_results"])
        context = context[:MAX_CONTEXT_CHARS]

        return {
            "status": "success",
            "retrieved_context": context,
            "source_tickets": retrieval_data.get("source_tickets", []),
            "num_results": len(retrieval_data.get("source_tickets", [])),
        }
    except Exception as exc:
        logger.exception("Retrieval tool failed")
        return {"status": "error", "error": str(exc)}


@tool
def generate_resolution_tool(issue_description: str, retrieved_context: str) -> Dict[str, Any]:
    """Tool 2: Generate resolution from context."""
    try:
        prompt = f"""{GENERATOR_INSTRUCTION}

Current Issue:
{issue_description}

Historical Context:
{retrieved_context[:MAX_CONTEXT_CHARS]}"""

        structured_llm = llm.with_structured_output(ResolutionResponse)
        response = _invoke_with_retry(structured_llm, prompt, "Generation tool")
        return response.model_dump()
    except Exception as exc:
        logger.exception("Generation tool failed")
        return {
            "resolution_available": False,
            "recommended_resolution": ["Generation error"],
            "reasoning": str(exc),
            "confidence": 0.0,
        }


@tool
def validate_resolution_tool(issue_description: str, proposed_resolution: str) -> Dict[str, Any]:
    """Tool 3: Validate completeness."""
    try:
        prompt = f"""{VALIDATOR_INSTRUCTION}

Issue:
{issue_description}

Proposed Resolution:
{proposed_resolution}"""

        structured_llm = llm.with_structured_output(ValidationResult)
        response = _invoke_with_retry(structured_llm, prompt, "Validation tool")
        return response.model_dump()
    except Exception as exc:
        logger.exception("Validation tool failed")
        return {"is_valid": False, "feedback": str(exc), "missing_issues": []}