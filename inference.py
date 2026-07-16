from __future__ import annotations
import json
import re
from typing import Any
from uuid import uuid4
import chromadb
from sentence_transformers import SentenceTransformer
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_groq import ChatGroq

from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    SIMILARITY_THRESHOLD,
    TOP_K,
)
from logger import logger
from prompt import GENERATION_TOOL_PROMPT, VALIDATION_TOOL_PROMPT, AGENT_PROMPT
from schemas import GenerationToolResponse, ValidationToolResponse


HANDOFF = (
    "Sufficient context not provided. Route this ticket to a human advocate "
    "and consult the relevant SOP."
)

# Short-lived in-process state. The agent passes IDs rather than repeatedly
# copying full issues, ticket chunks, and generated steps through tool JSON.
_REQUESTS: dict[str, dict[str, Any]] = {}
_CONTEXTS: dict[str, dict[str, Any]] = {}
_GENERATIONS: dict[str, dict[str, Any]] = {}


embedding_model = SentenceTransformer(
    EMBEDDING_MODEL,
    trust_remote_code=True,
)
collection = chromadb.PersistentClient(
    path=CHROMA_DB_PATH
).get_collection(
    COLLECTION_NAME
)

agent_model = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0,
    max_tokens=256,
    max_retries=0,
)

generation_model = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0,
    max_tokens=700,
    max_retries=0,
).bind(response_format={"type": "json_object"})

validation_model = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0,
    max_tokens=350,
    max_retries=0,
).bind(response_format={"type": "json_object"})



# pydantic obj to json
def _dump(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _trim_cache(cache: dict[str, Any], limit: int = 100) -> None:
    while len(cache) > limit:
        cache.pop(next(iter(cache)))

#JSON parsing and tool output handling
def _parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, default=str)

    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]

    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return parsed


#reusable wrapper for making a structured LLM call
def _call_json(model: Any, prompt: str, content: str, schema: Any) -> Any:
    response = model.invoke(
        [
            SystemMessage(content=prompt),
            HumanMessage(content=content),
        ]
    )
    return schema.model_validate(_parse_json(response.content))

#retrieved ticket records into one readable evidence block
def _evidence(context_id: str) -> str:
    context = _CONTEXTS.get(context_id)
    if not context:
        return ""
    return "\n\n".join(
        f"Ticket {ticket['ticket_id']}:\n{ticket['document']}"
        for ticket in context["tickets"]
    )

#ensures the message is an actual tool response
def _tool_outputs(messages: list[Any], tool_name: str) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name != tool_name:
            continue
        try:
            outputs.append(_parse_json(message.content))
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Could not parse output from tool %s.", tool_name)
    return outputs


def _clean_steps(steps: list[str]) -> list[str]:
    cleaned: list[str] = []
    for raw_step in steps or []:
        step = str(raw_step).strip()
        step = re.sub(r"^\s*Step\s+\d+\s*:\s*", "", step, flags=re.IGNORECASE)
        step = re.sub(r"^\s*\d+[.)]\s*", "", step)
        if step:
            cleaned.append(step)
    return cleaned


#====================Tools for the autonomous agent====================

@tool
def retrieve_ticket_context(search_string: str, request_id: str) -> str:
    """Retrieve top k similar historical tickets from the knowledge base and return a compact context_id."""

    request = _REQUESTS.get(request_id)
    if not request:
        return _dump(
            {
                "status": "error",
                "message": "Invalid or expired request_id.",
                "next_action": "Stop and reply HANDOFF.",
            }
        )

    #reads the number of retrieval attempts from the request, defaults to 0 if not present
    attempt = int(request.get("retrieval_attempts", 0))
    original_issue = str(request["issue"])
    query = original_issue if attempt == 0 else (search_string or original_issue).strip()
    request["retrieval_attempts"] = attempt + 1

    try:
        query_embedding = embedding_model.encode(query).tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=TOP_K,
            include=["documents", "distances"],
        )
    except Exception as exc:
        logger.exception("Retrieval failed.")
        return _dump(
            {
                "status": "error",
                "search_string": query,
                "message": f"Retrieval failed: {type(exc).__name__}: {str(exc)[:300]}",
                "next_action": "Stop and reply HANDOFF.",
            }
        )

    ids = (results.get("ids") or [[]])[0]
    documents = (results.get("documents") or [[]])[0] #nested lists for multiple queries, we only have one query so we take the first list
    distances = (results.get("distances") or [[]])[0]

    tickets: list[dict[str, Any]] = []
    for ticket_id, document, distance in zip(ids, documents, distances):
        if document is None:
            continue
        tickets.append(
            {
                "ticket_id": str(ticket_id),
                "similarity_distance": round(float(distance), 4),
                "document": " ".join(str(document).split()),
            }
        )

    if not tickets:
        return _dump(
            {
                "status": "context_insufficient",
                "search_string": query,
                "message": "No historical tickets were returned.",
                "next_action": "Retry once with a focused query, then stop.",
            }
        )

    best_distance = min(ticket["similarity_distance"] for ticket in tickets)
    ticket_summary = [
        {
            "ticket_id": ticket["ticket_id"],
            "similarity_distance": ticket["similarity_distance"],
        }
        for ticket in tickets
    ]

    if best_distance > SIMILARITY_THRESHOLD:
        return _dump(
            {
                "status": "context_insufficient",
                "search_string": query,
                "best_distance": best_distance,
                "threshold": SIMILARITY_THRESHOLD,
                "tickets": ticket_summary,
                "message": "No sufficiently similar historical ticket was found.",
                "next_action": (
                    "Retry retrieval once with a focused query and the same request_id. "
                    "If still insufficient, stop and reply HANDOFF."
                ),
            }
        )

    context_id = uuid4().hex[:12]
    _CONTEXTS[context_id] = {
        "member_issue": original_issue,
        "tickets": tickets,
    }
    _trim_cache(_CONTEXTS)

    return _dump(
        {
            "status": "context_found",
            "context_id": context_id,
            "search_string": query,
            "best_distance": best_distance,
            "threshold": SIMILARITY_THRESHOLD,
            "tickets": ticket_summary,
            "next_action": "Call generate_advocate_resolution with this context_id.",
        }
    )


@tool
def generate_advocate_resolution(
    context_id: str,
    validation_feedback: str = "",
) -> str:
    """Generate evidence-grounded generalised resolution steps for a stored context_id."""

    context = _CONTEXTS.get(context_id)
    if not context:
        return _dump(
            {
                "status": "generation_failed",
                "message": "Invalid or expired context_id.",
                "next_action": "Stop and reply HANDOFF.",
            }
        )

    try:
        result = _call_json(
            generation_model,
            GENERATION_TOOL_PROMPT,
            (
                f"CURRENT ISSUE:\n{context['member_issue']}\n\n"
                f"HISTORICAL EVIDENCE:\n{_evidence(context_id)}\n\n"
                f"VALIDATION FEEDBACK:\n{validation_feedback or 'None'}"
            ),
            GenerationToolResponse,
        )
    except Exception as exc:
        logger.exception("Generation failed.")
        return _dump(
            {
                "status": "generation_failed",
                "message": f"Generation failed: {type(exc).__name__}: {str(exc)[:300]}",
                "next_action": "Stop and reply HANDOFF.",
            }
        )

    steps = _clean_steps(result.resolution_steps)

    #precaution to ensure that only valid ticket IDs are cited in the generation, in case the model hallucinated a ticket ID that doesn't exist in the context
    valid_ticket_ids = {ticket["ticket_id"] for ticket in context["tickets"]}
    cited_ticket_ids = [
        ticket_id
        for ticket_id in result.cited_ticket_ids
        if ticket_id in valid_ticket_ids
    ]

    generation_id = uuid4().hex[:12]
    _GENERATIONS[generation_id] = {
        "context_id": context_id,
        "resolution_available": bool(result.resolution_available),
        "confidence": float(result.confidence),
        "resolution_steps": steps,
        "cited_ticket_ids": list(dict.fromkeys(cited_ticket_ids)),
        "reasoning": str(result.reasoning),
    }
    _trim_cache(_GENERATIONS)

    available = bool(result.resolution_available and steps)
    return _dump(
        {
            "status": "generated" if available else "generation_failed",
            "generation_id": generation_id,
            "context_id": context_id,
            "resolution_available": available,
            "confidence": float(result.confidence),
            "step_count": len(steps),
            "message": str(result.reasoning),
            "next_action": (
                "Call validate_advocate_resolution using only this generation_id."
                if available
                else "Stop and reply HANDOFF."
            ),
        }
    )


@tool
def validate_advocate_resolution(generation_id: str) -> str:
    """Validate a stored generation whether its addressing all member issue or not using only its compact generation_id."""

    generation = _GENERATIONS.get(generation_id)
    if not generation:
        return _dump(
            {
                "generation_id": generation_id,
                "verdict": "human_handoff",
                "all_issues_addressed": False,
                "grounded_in_retrieval": False,
                "missing_issues": [],
                "unsupported_steps": [],
                "feedback": "Invalid or expired generation_id.",
                "recommended_action": "human_handoff",
                "next_action": "Stop and reply HANDOFF.",
            }
        )

    context_id = str(generation["context_id"])
    context = _CONTEXTS.get(context_id)
    if not context:
        return _dump(
            {
                "generation_id": generation_id,
                "context_id": context_id,
                "verdict": "human_handoff",
                "all_issues_addressed": False,
                "grounded_in_retrieval": False,
                "missing_issues": [],
                "unsupported_steps": [],
                "feedback": "Retrieval context was unavailable.",
                "recommended_action": "human_handoff",
                "next_action": "Stop and reply HANDOFF.",
            }
        )

    advocate_steps_json = json.dumps(
        generation["resolution_steps"],
        ensure_ascii=False,
    )

    try:
        result = _call_json(
            validation_model,
            VALIDATION_TOOL_PROMPT,
            (
                f"CURRENT ISSUE:\n{context['member_issue']}\n\n"
                f"HISTORICAL EVIDENCE:\n{_evidence(context_id)}\n\n"
                f"PROPOSED STEPS:\n{advocate_steps_json}"
            ),
            ValidationToolResponse,
        )
    except Exception as exc:
        logger.exception("Validation failed.")
        return _dump(
            {
                "generation_id": generation_id,
                "context_id": context_id,
                "verdict": "human_handoff",
                "all_issues_addressed": False,
                "grounded_in_retrieval": False,
                "missing_issues": [],
                "unsupported_steps": [],
                "feedback": f"Validation failed: {type(exc).__name__}: {str(exc)[:300]}",
                "recommended_action": "human_handoff",
                "next_action": "Stop and reply HANDOFF.",
            }
        )

    payload = result.model_dump()
    payload["generation_id"] = generation_id
    payload["context_id"] = context_id
    payload["next_action"] = (
        "Stop now. Call no more tools. Reply DONE."
        if result.verdict == "approved" and result.recommended_action == "finalize"
        else "Follow recommended_action once, then stop."
    )
    return _dump(payload)


resolution_agent = create_agent(
    model=agent_model,
    tools=[
        retrieve_ticket_context,
        generate_advocate_resolution,
        validate_advocate_resolution,
    ],
    system_prompt=AGENT_PROMPT,
    middleware=[
        ToolCallLimitMiddleware(
            tool_name="retrieve_ticket_context",
            run_limit=3,
            exit_behavior="end",
        ),
        ToolCallLimitMiddleware(
            tool_name="generate_advocate_resolution",
            run_limit=3,
            exit_behavior="end",
        ),
        ToolCallLimitMiddleware(
            tool_name="validate_advocate_resolution",
            run_limit=3,
            exit_behavior="end",
        ),
        ModelCallLimitMiddleware(
            run_limit=7,
            exit_behavior="end",
        ),
    ],
)


def _failure(reason: str, diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "human_handoff_required",
        "resolution_available": False,
        "confidence": 0.0,
        "recommended_resolution": [HANDOFF],
        "reasoning": reason,
        "source_tickets": [],
        "validation_feedback": reason,
        "human_handoff": True,
        "handoff_reason": reason,
        "agent_diagnostics": diagnostics or {},
    }


def resolve_issue(issue_description: str) -> dict[str, Any]:
    """Run the autonomous agent and return the API response expected by ticket_api.py."""

    issue = (issue_description or "").strip()
    if not issue:
        return _failure("The ticket issue description was empty.")

    request_id = uuid4().hex[:12]
    _REQUESTS[request_id] = {
        "issue": issue,
        "retrieval_attempts": 0,
    }
    _trim_cache(_REQUESTS)

    try:
        state = resolution_agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"request_id: {request_id}\n"
                            "Resolve this ticket with the three tools. Use the complete member issue verbatim for the first retrieval.\n\n"
                            f"MEMBER ISSUE:\n{issue}"
                        ),
                    }
                ]
            },
            config={"recursion_limit": 50},
        )
    except Exception as exc:
        logger.exception("Autonomous resolution failed.")
        return _failure(
            f"The autonomous agent failed: {type(exc).__name__}: {str(exc)[:500]}"
        )

    #Read all agent messages
    messages = list(state.get("messages", []))

    #code extracts the outputs of each too
    retrievals = _tool_outputs(messages, "retrieve_ticket_context")
    generations = _tool_outputs(messages, "generate_advocate_resolution")
    validations = _tool_outputs(messages, "validate_advocate_resolution")

    executed_sequence: list[str] = []
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name not in {
            "retrieve_ticket_context",
            "generate_advocate_resolution",
            "validate_advocate_resolution",
        }:
            continue
        try:
            _parse_json(message.content)
            executed_sequence.append(str(message.name))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    diagnostics = {
        "tool_sequence": executed_sequence,
        "retrieval_attempts": [
            {
                "search_string": item.get("search_string"),
                "status": item.get("status"),
                "best_distance": item.get("best_distance"),
                "threshold": item.get("threshold"),
                "tickets": item.get("tickets", []),
                "message": item.get("message"),
            }
            for item in retrievals
        ],
    }

    if not retrievals:
        return _failure("The agent did not call the retrieval tool.", diagnostics)
    if not generations:
        return _failure(
            str(retrievals[-1].get("message") or "Retrieval context was insufficient."),
            diagnostics,
        )
    if not validations:
        return _failure(
            str(generations[-1].get("message") or "Resolution generation was not validated."),
            diagnostics,
        )
    
    #If validation ran more than once, this uses the latest result.
    validation = validations[-1]
    generation_id = str(validation.get("generation_id") or "")
    generation = _GENERATIONS.get(generation_id)
    if not generation:
        return _failure("The validated generation could not be loaded.", diagnostics)

    approved = (
        bool(generation.get("resolution_available"))
        and bool(generation.get("resolution_steps"))
        and validation.get("verdict") == "approved"
        and validation.get("recommended_action") == "finalize"
        and validation.get("all_issues_addressed") is True
        and validation.get("grounded_in_retrieval") is True
    )
    if not approved:
        return _failure(
            str(validation.get("feedback") or generation.get("reasoning") or HANDOFF),
            diagnostics,
        )

    context = _CONTEXTS.get(str(generation["context_id"]))
    if not context:
        return _failure("The approved retrieval context could not be loaded.", diagnostics)

    cited_ids = set(generation.get("cited_ticket_ids", []))
    references = [
        {
            "ticket_id": ticket["ticket_id"],
            "similarity_distance": ticket["similarity_distance"],
        }
        for ticket in context["tickets"]
        if not cited_ids or ticket["ticket_id"] in cited_ids
    ]

    return {
        "status": "resolved",
        "resolution_available": True,
        "confidence": float(generation.get("confidence", 0.0)),
        "recommended_resolution": [
            f"Step {index}:\n{step}"
            for index, step in enumerate(generation["resolution_steps"], start=1)
        ],
        "reasoning": str(generation.get("reasoning", "")),
        "source_tickets": references,
        "validation_feedback": str(validation.get("feedback", "")),
        "human_handoff": False,
        "handoff_reason": None,
        "agent_diagnostics": diagnostics,
    }


def diagnose_retrieval(issue_description: str) -> dict[str, Any]:
    """Run only the existing retrieval logic for API diagnostics."""

    issue = (issue_description or "").strip()
    if not issue:
        return {
            "status": "context_insufficient",
            "message": "The issue description was empty.",
        }

    request_id = uuid4().hex[:12]
    _REQUESTS[request_id] = {
        "issue": issue,
        "retrieval_attempts": 0,
    }
    _trim_cache(_REQUESTS)

    result = retrieve_ticket_context.invoke(
        {
            "search_string": issue,
            "request_id": request_id,
        }
    )
    return _parse_json(result)