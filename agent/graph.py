from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, START, StateGraph

from .tools import (
    generate_resolution_tool,
    retrieve_similar_tickets,
    validate_resolution_tool,
)
from logger import logger, log_event


class AgentState(TypedDict, total=False):
    issue_description: str
    retrieved_context: str
    source_tickets: List[dict]
    generation_result: Dict[str, Any]
    proposed_resolution: str
    validation_result: Dict[str, Any]
    final_resolution: Dict[str, Any]


def _fallback(source_tickets: List[dict] | None = None) -> Dict[str, Any]:
    return {
        "resolution_available": False,
        "confidence": 0.0,
        "recommended_resolution": ["Sufficient context not provided."],
        "reasoning": "No sufficiently similar historical incidents found.",
        "source_tickets": source_tickets or [],
    }


def retrieve_node(state: AgentState) -> Dict[str, Any]:
    issue_description = state["issue_description"]
    log_event("agent_retrieve_started", issue_length=len(issue_description))

    result = retrieve_similar_tickets.invoke({"issue_description": issue_description})

    if result.get("status") != "success":
        return {
            "final_resolution": _fallback([]),
            "source_tickets": [],
        }

    return {
        "retrieved_context": result.get("retrieved_context", ""),
        "source_tickets": result.get("source_tickets", []),
    }


def generate_node(state: AgentState) -> Dict[str, Any]:
    if state.get("final_resolution"):
        return {}

    issue_description = state["issue_description"]
    retrieved_context = state.get("retrieved_context", "")

    if not retrieved_context:
        return {
            "final_resolution": _fallback(state.get("source_tickets", [])),
        }

    result = generate_resolution_tool.invoke(
        {
            "issue_description": issue_description,
            "retrieved_context": retrieved_context,
        }
    )

    if not result.get("resolution_available", False):
        result["source_tickets"] = state.get("source_tickets", [])
        return {"final_resolution": result}

    recommended_resolution = result.get("recommended_resolution", [])
    if isinstance(recommended_resolution, list):
        proposed_resolution = "\n".join(str(item) for item in recommended_resolution)
    else:
        proposed_resolution = str(recommended_resolution)

    return {
        "generation_result": result,
        "proposed_resolution": proposed_resolution,
    }


def validate_node(state: AgentState) -> Dict[str, Any]:
    if state.get("final_resolution") and not state.get("proposed_resolution"):
        return {"final_resolution": state["final_resolution"]}

    issue_description = state["issue_description"]
    proposed_resolution = state.get("proposed_resolution", "")

    if not proposed_resolution:
        return {
            "final_resolution": _fallback(state.get("source_tickets", [])),
        }

    validation = validate_resolution_tool.invoke(
        {
            "issue_description": issue_description,
            "proposed_resolution": proposed_resolution,
        }
    )

    final_resolution = dict(state.get("generation_result") or {})
    if not final_resolution:
        final_resolution = {
            "resolution_available": True,
            "confidence": 0.82,
            "recommended_resolution": [proposed_resolution],
            "reasoning": "Generated and validated by the agent.",
        }

    final_resolution["source_tickets"] = state.get("source_tickets", [])
    final_resolution["validation_result"] = validation

    if validation.get("is_valid", False):
        final_resolution["resolution_available"] = True
    else:
        final_resolution["resolution_available"] = False
        feedback = validation.get("feedback", "Validation failed.")
        final_resolution["reasoning"] = (
            f"{final_resolution.get('reasoning', '')} Validation feedback: {feedback}"
        ).strip()

    return {"final_resolution": final_resolution}


workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_node)
workflow.add_node("validate", validate_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "validate")
workflow.add_edge("validate", END)

agent_graph = workflow.compile()

logger.info("✅ Agentic LangGraph initialized successfully.")
# from typing import TypedDict, Annotated, List
# import operator
# from langgraph.graph import StateGraph, END, START
# from langgraph.prebuilt import ToolNode, tools_condition
# from langchain_core.messages import BaseMessage, HumanMessage
# from langgraph.graph.message import add_messages
# from .tools import retrieve_similar_tickets, generate_resolution_tool, validate_resolution_tool
# from .prompts import AGENT_SUPERVISOR_PROMPT

# from schemas import ResolutionResponse
# from config import GROQ_MODEL, GROQ_API_KEY
# from langchain_groq import ChatGroq
# from logger import logger, log_event

# llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.0)

# tools = [retrieve_similar_tickets, generate_resolution_tool, validate_resolution_tool]

# class AgentState(TypedDict):
#     messages: Annotated[List[BaseMessage], add_messages]
#     issue_description: str
#     final_resolution: dict | None
#     iteration_count: Annotated[int, operator.add]


# def supervisor_node(state: AgentState):
#     """Central reasoning node."""
#     messages = state["messages"]
#     issue = state["issue_description"]
    
#     log_event("supervisor_decision", issue_preview=issue[:80] if issue else "")
    
#     supervisor_prompt = f"{AGENT_SUPERVISOR_PROMPT}\n\nCurrent Ticket Issue:\n{issue}"
    
#     llm_with_tools = llm.bind_tools(tools)
#     response = llm_with_tools.invoke([HumanMessage(content=supervisor_prompt)] + messages)
    
#     return {"messages": [response]}


# def should_continue(state: AgentState):
#     last_message = state["messages"][-1]
#     if not last_message.tool_calls:
#         return END
#     return "tools"


# # Build Graph
# workflow = StateGraph(AgentState)
# workflow.add_node("supervisor", supervisor_node)
# workflow.add_node("tools", ToolNode(tools))

# workflow.add_edge(START, "supervisor")
# workflow.add_conditional_edges("supervisor", should_continue, {"tools": "tools", END: END})
# workflow.add_edge("tools", "supervisor")

# agent_graph = workflow.compile()

# logger.info("✅ Agentic LangGraph initialized successfully.")

# # Add at the end of graph.py
# # if __name__ == "__main__":
# #     print(agent_graph.get_graph().draw_mermaid())