"""Autonomous, single-agent RAG inference for enterprise ticket resolution.

The central agent is created with LangChain's ``create_agent``. This is the current
supported high-level API and produces a compiled LangGraph agent under the hood.
There are no hard-coded graph nodes or conditional edges in this module.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

import chromadb
from sentence_transformers import SentenceTransformer

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.tools import tool
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    CONFIDENCE_THRESHOLD,
    EMBEDDING_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    SIMILARITY_THRESHOLD,
    TOP_K,
)
from logger import logger
from prompt import (
    AUTONOMOUS_AGENT_SYSTEM_PROMPT,
    GENERATION_TOOL_PROMPT,
    VALIDATION_TOOL_PROMPT,
)
from schemas import (
    AgentResolutionResponse,
    GenerationToolResponse,
    ReferenceTicket,
    RetrievalToolResponse,
    RetrievedTicketChunk,
    ValidationToolResponse,
)


AGENT_RECURSION_LIMIT = 35


# -----------------------------------------------------------------------------
# Shared clients
# -----------------------------------------------------------------------------

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL,
    trust_remote_code=True,
)

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_collection(name=COLLECTION_NAME)

llm = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0,
    max_retries=2,
)

_generation_llm = llm.with_structured_output(GenerationToolResponse)
_validation_llm = llm.with_structured_output(ValidationToolResponse)

_generation_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", GENERATION_TOOL_PROMPT),
        (
            "human",
            """
Member issue:
{member_issue}

Retrieved historical ticket chunks:
{retrieved_chunks}

Validation feedback from a previous attempt, if any:
{validation_feedback}
""",
        ),
    ]
)

_validation_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", VALIDATION_TOOL_PROMPT),
        (
            "human",
            """
Member issue:
{member_issue}

Retrieved historical ticket chunks:
{retrieved_chunks}

Proposed advocate steps:
{advocate_steps}
""",
        ),
    ]
)

_generation_chain = _generation_prompt | _generation_llm
_validation_chain = _validation_prompt | _validation_llm


# -----------------------------------------------------------------------------
# Tool helpers
# -----------------------------------------------------------------------------


def _json_string(payload: Any) -> str:
    """Serialize a tool payload predictably for the central agent."""

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _normalise_steps(steps: list[str]) -> list[str]:
    """Strip accidental numbering so the API wrapper can number steps once."""

    normalised: list[str] = []
    for raw_step in steps:
        step = raw_step.strip()
        if not step:
            continue

        # Remove common model-produced prefixes such as "Step 1:" or "1.".
        lowered = step.lower()
        if lowered.startswith("step ") and ":" in step:
            step = step.split(":", 1)[1].strip()
        elif "." in step:
            prefix, remainder = step.split(".", 1)
            if prefix.strip().isdigit():
                step = remainder.strip()

        if step:
            normalised.append(step)

    return normalised


def _tool_records(
    messages: list[BaseMessage],
    tool_name: str,
) -> list[tuple[int, dict[str, Any]]]:
    """Parse indexed JSON payloads emitted by one named tool from agent history."""

    records: list[tuple[int, dict[str, Any]]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, ToolMessage) or message.name != tool_name:
            continue

        try:
            payload = json.loads(message_text(message))
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Could not parse %s tool output as JSON.", tool_name)
            continue

        if isinstance(payload, dict):
            records.append((index, payload))

    return records


def _enforce_tool_evidence(
    response: AgentResolutionResponse,
    messages: list[BaseMessage],
) -> AgentResolutionResponse:
    """Reconstruct the final answer from real tool evidence.

    The orchestration model may summarize its own execution imperfectly. The wrapper
    therefore treats the latest generation followed by the latest validation as the
    source of truth. A validator-approved generation is returned even when the
    orchestration model accidentally labels its final structured response as a human
    handoff. This avoids false fallbacks while keeping the agent autonomous.
    """

    retrieval_records = _tool_records(messages, "retrieve_ticket_context")
    generation_records = _tool_records(messages, "generate_advocate_resolution")
    validation_records = _tool_records(messages, "validate_advocate_resolution")

    if not generation_records or not validation_records:
        reason = "The agent did not complete both generation and validation tools."
        return AgentResolutionResponse(
            status="human_handoff_required",
            resolution_available=False,
            confidence=0.0,
            resolution_steps=[
                "Sufficient context not provided. Route this ticket to a human advocate and consult the relevant SOP."
            ],
            reference_tickets=[],
            validation_feedback=reason,
            reasoning=reason,
            human_handoff=True,
            handoff_reason=reason,
        )

    latest_generation_index, latest_generation_payload = generation_records[-1]

    # The latest validation that occurred after the latest generation is the only
    # validation that can approve the final set of steps.
    validations_after_generation = [
        record for record in validation_records if record[0] > latest_generation_index
    ]
    if not validations_after_generation:
        reason = "The latest generated resolution was not validated."
        return AgentResolutionResponse(
            status="human_handoff_required",
            resolution_available=False,
            confidence=0.0,
            resolution_steps=[
                "Sufficient context not provided. Route this ticket to a human advocate and consult the relevant SOP."
            ],
            reference_tickets=[],
            validation_feedback=reason,
            reasoning=reason,
            human_handoff=True,
            handoff_reason=reason,
        )

    latest_validation_index, latest_validation_payload = validations_after_generation[-1]

    try:
        latest_generation = GenerationToolResponse.model_validate(
            latest_generation_payload
        )
        latest_validation = ValidationToolResponse.model_validate(
            latest_validation_payload
        )
    except Exception as exc:
        reason = f"Generation or validation output was malformed: {type(exc).__name__}."
        return AgentResolutionResponse(
            status="human_handoff_required",
            resolution_available=False,
            confidence=0.0,
            resolution_steps=[
                "Sufficient context not provided. Route this ticket to a human advocate and consult the relevant SOP."
            ],
            reference_tickets=[],
            validation_feedback=reason,
            reasoning=reason,
            human_handoff=True,
            handoff_reason=reason,
        )

    validation_approved = (
        latest_validation.verdict == "approved"
        and latest_validation.all_issues_addressed
        and latest_validation.grounded_in_retrieval
    )

    if (
        not validation_approved
        or not latest_generation.resolution_available
        or not latest_generation.resolution_steps
    ):
        reason = latest_validation.feedback or latest_generation.reasoning
        return AgentResolutionResponse(
            status="human_handoff_required",
            resolution_available=False,
            confidence=0.0,
            resolution_steps=[
                "Sufficient context not provided. Route this ticket to a human advocate and consult the relevant SOP."
            ],
            reference_tickets=[],
            validation_feedback=reason,
            reasoning=(
                "The latest validator did not approve a complete, grounded resolution. "
                f"Generation: {latest_generation.reasoning}"
            ),
            human_handoff=True,
            handoff_reason=reason,
        )

    # Only retrieval calls made before the approved generation can be evidence for it.
    actual_references: dict[str, ReferenceTicket] = {}
    for retrieval_index, payload in retrieval_records:
        if retrieval_index > latest_generation_index:
            continue
        for chunk in payload.get("retrieved_chunks", []):
            try:
                reference = ReferenceTicket.model_validate(chunk)
            except Exception:
                continue
            actual_references[reference.ticket_id] = reference

    cited_ids = list(
        dict.fromkeys(
            ticket_id
            for ticket_id in latest_generation.cited_ticket_ids
            if ticket_id in actual_references
        )
    )

    # Some orchestration models omit cited_ticket_ids even though the generation and
    # validator used real retrieved chunks. In that case use the verified retrieval
    # references instead of discarding an otherwise approved resolution.
    if cited_ids:
        approved_references = [actual_references[ticket_id] for ticket_id in cited_ids]
    else:
        approved_references = list(actual_references.values())

    if not approved_references:
        reason = "Validation approved the steps, but no verified retrieval references were available."
        return AgentResolutionResponse(
            status="human_handoff_required",
            resolution_available=False,
            confidence=0.0,
            resolution_steps=[
                "Sufficient context not provided. Route this ticket to a human advocate and consult the relevant SOP."
            ],
            reference_tickets=[],
            validation_feedback=reason,
            reasoning=reason,
            human_handoff=True,
            handoff_reason=reason,
        )

    if latest_generation.confidence < CONFIDENCE_THRESHOLD:
        logger.warning(
            "Validator approved a resolution below configured confidence threshold | "
            "confidence=%s | threshold=%s",
            latest_generation.confidence,
            CONFIDENCE_THRESHOLD,
        )

    return AgentResolutionResponse(
        status="resolved",
        resolution_available=True,
        confidence=latest_generation.confidence,
        resolution_steps=latest_generation.resolution_steps,
        reference_tickets=approved_references,
        validation_feedback=latest_validation.feedback,
        reasoning=latest_generation.reasoning,
        human_handoff=False,
        handoff_reason=None,
    )


def _execution_diagnostics(messages: list[BaseMessage]) -> dict[str, Any]:
    """Return compact, non-sensitive diagnostics for API and log troubleshooting."""

    retrieval_records = _tool_records(messages, "retrieve_ticket_context")
    generation_records = _tool_records(messages, "generate_advocate_resolution")
    validation_records = _tool_records(messages, "validate_advocate_resolution")

    retrieval_attempts = []
    for _, payload in retrieval_records:
        retrieval_attempts.append(
            {
                "status": payload.get("status"),
                "search_string": payload.get("search_string"),
                "best_distance": payload.get("best_distance"),
                "embedding_mode": payload.get("embedding_mode"),
                "retrieved_count": len(payload.get("retrieved_chunks", [])),
                "message": payload.get("message"),
            }
        )

    latest_generation = generation_records[-1][1] if generation_records else None
    latest_validation = validation_records[-1][1] if validation_records else None

    return {
        "retrieval_attempts": retrieval_attempts,
        "generation_calls": len(generation_records),
        "validation_calls": len(validation_records),
        "latest_generation": (
            {
                "resolution_available": latest_generation.get("resolution_available"),
                "confidence": latest_generation.get("confidence"),
                "step_count": len(latest_generation.get("resolution_steps", [])),
                "cited_ticket_ids": latest_generation.get("cited_ticket_ids", []),
                "reasoning": latest_generation.get("reasoning"),
            }
            if latest_generation
            else None
        ),
        "latest_validation": (
            {
                "verdict": latest_validation.get("verdict"),
                "all_issues_addressed": latest_validation.get("all_issues_addressed"),
                "grounded_in_retrieval": latest_validation.get("grounded_in_retrieval"),
                "recommended_action": latest_validation.get("recommended_action"),
                "feedback": latest_validation.get("feedback"),
            }
            if latest_validation
            else None
        ),
    }


# -----------------------------------------------------------------------------
# Tool 1: vector retrieval
# -----------------------------------------------------------------------------


@tool
def retrieve_ticket_context(search_string: str) -> str:
    """Retrieve relevant historical ticket chunks from Chroma.

    Args:
        search_string: A focused natural-language search query describing the
            member issue or a missing sub-issue identified by validation.

    Returns:
        A JSON string with context sufficiency, historical chunks, exact ticket
        IDs, and vector distances. Lower distance means greater similarity.
    """

    query = (search_string or "").strip()
    if not query:
        return _json_string(
            RetrievalToolResponse(
                status="context_insufficient",
                search_string="",
                context_sufficient=False,
                message="A non-empty search string is required.",
            )
        )

    try:
        # Keep backward compatibility with the original plain encoding, but also
        # try the Qwen/SentenceTransformer query prompt when the model provides it.
        # The result set with the lowest nearest-neighbor distance is used.
        query_variants: list[tuple[str, list[float]]] = [
            ("plain", embedding_model.encode(query).tolist())
        ]

        model_prompts = getattr(embedding_model, "prompts", {}) or {}
        if "query" in model_prompts:
            try:
                query_variants.append(
                    (
                        "query_prompt",
                        embedding_model.encode(query, prompt_name="query").tolist(),
                    )
                )
            except Exception:
                logger.warning(
                    "Embedding model exposes a query prompt but prompted encoding failed; "
                    "continuing with plain encoding.",
                    exc_info=True,
                )

        candidate_results: list[tuple[float, str, dict[str, Any]]] = []
        for embedding_mode, query_embedding in query_variants:
            candidate = collection.query(
                query_embeddings=[query_embedding],
                n_results=TOP_K,
                include=["documents", "distances", "metadatas"],
            )
            candidate_distances = (candidate.get("distances") or [[]])[0]
            if candidate_distances:
                candidate_results.append(
                    (float(min(candidate_distances)), embedding_mode, candidate)
                )

        if not candidate_results:
            response = RetrievalToolResponse(
                status="context_insufficient",
                search_string=query,
                context_sufficient=False,
                message="The vector database returned no historical tickets.",
            )
            return _json_string(response)

        _, embedding_mode, results = min(candidate_results, key=lambda item: item[0])

        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        if not ids or not distances:
            response = RetrievalToolResponse(
                status="context_insufficient",
                search_string=query,
                context_sufficient=False,
                message="The vector database returned no historical tickets.",
            )
            return _json_string(response)

        best_distance = round(float(min(distances)), 4)

        # Preserve the behavior of the original RAG pipeline: use the best match to
        # decide whether retrieval is relevant, then pass all TOP_K neighbors to the
        # generation tool. Filtering every chunk independently was too strict and
        # removed supporting workflow stages that the validator expected.
        context_sufficient = best_distance <= SIMILARITY_THRESHOLD
        retrieved_chunks: list[RetrievedTicketChunk] = []
        if context_sufficient:
            for ticket_id, document, distance in zip(ids, documents, distances):
                retrieved_chunks.append(
                    RetrievedTicketChunk(
                        ticket_id=str(ticket_id),
                        similarity_distance=round(float(distance), 4),
                        document=str(document),
                    )
                )

        response = RetrievalToolResponse(
            status="context_found" if context_sufficient else "context_insufficient",
            search_string=query,
            context_sufficient=context_sufficient,
            best_distance=best_distance,
            embedding_mode=embedding_mode,
            retrieved_chunks=retrieved_chunks,
            message=(
                f"Best match passed the configured threshold; returned "
                f"the top {len(retrieved_chunks)} historical ticket(s)."
                if context_sufficient
                else (
                    "No retrieved ticket met the configured similarity threshold; "
                    "refine the query or route to a human advocate."
                )
            ),
        )

        logger.info(
            "Agent retrieval completed | query=%r | accepted=%s | best_distance=%s",
            query,
            len(retrieved_chunks),
            best_distance,
        )
        return _json_string(response)

    except Exception as exc:
        logger.exception("Autonomous agent retrieval tool failed.")
        return _json_string(
            RetrievalToolResponse(
                status="error",
                search_string=query,
                context_sufficient=False,
                message=f"Retrieval failed: {type(exc).__name__}",
            )
        )


# -----------------------------------------------------------------------------
# Tool 2: LLM resolution generation
# -----------------------------------------------------------------------------


@tool
def generate_advocate_resolution(
    member_issue: str,
    retrieved_chunks: str,
    validation_feedback: str = "",
) -> str:
    """Generate evidence-grounded advocate resolution steps with an LLM.

    Args:
        member_issue: The complete current member issue/question.
        retrieved_chunks: JSON or text returned by the retrieval tool. It must
            include the historical chunks used as evidence.
        validation_feedback: Optional feedback from a failed validation attempt.

    Returns:
        A JSON string containing resolution availability, confidence, ordered
        steps, cited ticket IDs, and concise reasoning.
    """

    issue = (member_issue or "").strip()
    context = (retrieved_chunks or "").strip()

    if not issue or not context:
        return _json_string(
            GenerationToolResponse(
                resolution_available=False,
                confidence=0.0,
                resolution_steps=[],
                cited_ticket_ids=[],
                reasoning="Member issue or retrieved evidence was missing.",
            )
        )

    try:
        response = _generation_chain.invoke(
            {
                "member_issue": issue,
                "retrieved_chunks": context,
                "validation_feedback": validation_feedback or "None",
            }
        )
        response.resolution_steps = _normalise_steps(response.resolution_steps)
        logger.info(
            "Agent generation tool completed | available=%s | steps=%s",
            response.resolution_available,
            len(response.resolution_steps),
        )
        return _json_string(response)

    except Exception as exc:
        logger.exception("Autonomous agent generation tool failed.")
        return _json_string(
            GenerationToolResponse(
                resolution_available=False,
                confidence=0.0,
                resolution_steps=[],
                cited_ticket_ids=[],
                reasoning=f"Resolution generation failed: {type(exc).__name__}",
            )
        )


# -----------------------------------------------------------------------------
# Tool 3: LLM validation
# -----------------------------------------------------------------------------


@tool
def validate_advocate_resolution(
    member_issue: str,
    retrieved_chunks: str,
    advocate_steps: list[str],
) -> str:
    """Validate issue coverage and evidence grounding with an LLM.

    Args:
        member_issue: The complete member issue/question to be addressed.
        retrieved_chunks: The historical chunks used to produce the resolution.
        advocate_steps: The proposed ordered advocate resolution steps.

    Returns:
        A JSON string with an approval/correction verdict, missing issues,
        unsupported steps, feedback, and the recommended next agent action.
    """

    issue = (member_issue or "").strip()
    context = (retrieved_chunks or "").strip()
    steps = _normalise_steps(advocate_steps or [])

    if not issue or not context or not steps:
        return _json_string(
            ValidationToolResponse(
                verdict="context_missing" if not context else "generation_issue",
                all_issues_addressed=False,
                grounded_in_retrieval=False,
                missing_issues=["Complete member issue, retrieval context, and steps are required."],
                unsupported_steps=[],
                feedback="The validation inputs were incomplete.",
                recommended_action="retrieve_again" if not context else "regenerate",
            )
        )

    try:
        response = _validation_chain.invoke(
            {
                "member_issue": issue,
                "retrieved_chunks": context,
                "advocate_steps": json.dumps(steps, ensure_ascii=False, indent=2),
            }
        )
        logger.info(
            "Agent validation tool completed | verdict=%s | next=%s",
            response.verdict,
            response.recommended_action,
        )
        return _json_string(response)

    except Exception as exc:
        logger.exception("Autonomous agent validation tool failed.")
        return _json_string(
            ValidationToolResponse(
                verdict="human_handoff",
                all_issues_addressed=False,
                grounded_in_retrieval=False,
                missing_issues=[],
                unsupported_steps=[],
                feedback=f"Validation failed: {type(exc).__name__}",
                recommended_action="human_handoff",
            )
        )


# -----------------------------------------------------------------------------
# Single central autonomous agent
# -----------------------------------------------------------------------------

resolution_agent = create_agent(
    model=llm,
    tools=[
        retrieve_ticket_context,
        generate_advocate_resolution,
        validate_advocate_resolution,
    ],
    system_prompt=AUTONOMOUS_AGENT_SYSTEM_PROMPT,
    response_format=ToolStrategy(
        schema=AgentResolutionResponse,
        tool_message_content="Final ticket-resolution response captured.",
        handle_errors=(
            "Return exactly one valid AgentResolutionResponse. Copy only approved "
            "resolution steps and real retrieval references."
        ),
    ),
)


# -----------------------------------------------------------------------------
# Public wrapper functions
# -----------------------------------------------------------------------------


def _build_agent_input(issue_description: str) -> dict[str, list[dict[str, str]]]:
    """Build the message state expected by the compiled LangGraph agent."""

    return {
        "messages": [
            {
                "role": "user",
                "content": (
                    "Resolve the following member ticket autonomously. Follow the mandatory "
                    "first iteration, use validation feedback to decide retries, and return the "
                    "required structured response.\n\n"
                    f"Member issue:\n{issue_description.strip()}"
                ),
            }
        ]
    }


def _fallback_response(reason: str) -> dict[str, Any]:
    """Return the legacy API shape when the agent cannot safely complete."""

    return {
        "status": "human_handoff_required",
        "resolution_available": False,
        "confidence": 0.0,
        "recommended_resolution": [
            "Sufficient context not provided. Route this ticket to a human advocate and consult the relevant SOP."
        ],
        "reasoning": reason,
        "source_tickets": [],
        "validation_feedback": reason,
        "human_handoff": True,
        "handoff_reason": reason,
        "agent_diagnostics": {},
    }


def _to_legacy_api_response(
    response: AgentResolutionResponse,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map the typed agent response to the shape already consumed by FastAPI/UI."""

    steps = _normalise_steps(response.resolution_steps)
    numbered_steps = [f"Step {index}:\n{step}" for index, step in enumerate(steps, start=1)]

    references = [reference.model_dump() for reference in response.reference_tickets]

    return {
        "status": response.status,
        "resolution_available": response.resolution_available,
        "confidence": response.confidence,
        "recommended_resolution": numbered_steps,
        "reasoning": response.reasoning,
        "source_tickets": references,
        "validation_feedback": response.validation_feedback,
        "human_handoff": response.human_handoff,
        "handoff_reason": response.handoff_reason,
        "agent_diagnostics": diagnostics or {},
    }


def resolve_issue(issue_description: str) -> dict[str, Any]:
    """Invoke the autonomous agent and return the existing application response shape.

    This is the main synchronous wrapper used by ``ticket_api.py``. It validates the
    input, invokes the single compiled agent, extracts ``structured_response``, and
    maps it to the keys the current UI already expects.
    """

    issue = (issue_description or "").strip()
    if not issue:
        return _fallback_response("The ticket issue description was empty.")

    try:
        state = resolution_agent.invoke(
            _build_agent_input(issue),
            config={"recursion_limit": AGENT_RECURSION_LIMIT},
        )
        structured = state.get("structured_response")

        if structured is None:
            logger.error("Agent completed without structured_response.")
            return _fallback_response("The autonomous agent returned no structured response.")

        if isinstance(structured, dict):
            structured = AgentResolutionResponse.model_validate(structured)
        elif not isinstance(structured, AgentResolutionResponse):
            structured = AgentResolutionResponse.model_validate(structured)

        messages = state.get("messages", [])
        diagnostics = _execution_diagnostics(messages)
        structured = _enforce_tool_evidence(structured, messages)

        result = _to_legacy_api_response(structured, diagnostics)
        logger.info(
            "Autonomous resolution completed | status=%s | references=%s",
            result["status"],
            len(result["source_tickets"]),
        )
        return result

    except Exception as exc:
        logger.exception("Autonomous issue resolution failed.")
        return _fallback_response(
            f"The autonomous agent failed safely and requires human review: {type(exc).__name__}."
        )


def diagnose_retrieval(issue_description: str) -> dict[str, Any]:
    """Run only the retrieval tool so threshold/index problems are easy to inspect."""

    issue = (issue_description or "").strip()
    if not issue:
        return {
            "status": "context_insufficient",
            "context_sufficient": False,
            "message": "The ticket issue description was empty.",
            "retrieved_chunks": [],
        }

    raw = retrieve_ticket_context.invoke({"search_string": issue})
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    return {"status": "error", "message": f"Unexpected retrieval output: {type(raw).__name__}"}


def stream_issue_resolution(issue_description: str) -> Iterator[dict[str, Any]]:
    """Optional streaming wrapper for debugging tool decisions and agent updates.

    The production FastAPI endpoint can continue using ``resolve_issue``. This helper
    mirrors the ``graph.stream(..., stream_mode='updates')`` style and is useful for
    CLI diagnostics or a future streaming endpoint.
    """

    issue = (issue_description or "").strip()
    if not issue:
        yield {"error": "The ticket issue description was empty."}
        return

    yield from resolution_agent.stream(
        _build_agent_input(issue),
        stream_mode="updates",
        config={"recursion_limit": AGENT_RECURSION_LIMIT},
    )


def message_text(message: BaseMessage) -> str:
    """Small diagnostic helper for displaying LangChain message content safely."""

    content = message.content
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, default=str)

