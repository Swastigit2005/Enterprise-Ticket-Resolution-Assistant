import json
import asyncio

import chromadb
from sentence_transformers import SentenceTransformer
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

from config import (
    CHROMA_DB_PATH, COLLECTION_NAME, EMBEDDING_MODEL,
    TOP_K, SIMILARITY_THRESHOLD, GROQ_MODEL, GROQ_API_KEY
)

from schemas import ResolutionResponse
from logger import logger, log_event
from agent.graph import agent_graph   # Agentic core

# ==========================================
# INITIALIZATION (Keep for reuse by tools)
# ==========================================

embedding_model = SentenceTransformer(EMBEDDING_MODEL)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = chroma_client.get_collection(COLLECTION_NAME)

# ==========================================
# RETRIEVAL HELPERS (Used by agent tools)
# ==========================================

def retrieve_context(issue_description):
    query_embedding = embedding_model.encode(issue_description).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        include=["documents", "distances"]
    )
    
    distances = results["distances"][0]
    source_tickets = [
        {"ticket_id": results["ids"][0][i], "similarity_distance": round(distances[i], 4)}
        for i in range(len(results["ids"][0]))
    ]
    
    if min(distances) > SIMILARITY_THRESHOLD:
        return None
        
    return {"chroma_results": results, "source_tickets": source_tickets}


def build_context(retrieval_results):
    context = []
    for index, document in enumerate(retrieval_results["documents"][0]):
        ticket_id = retrieval_results["ids"][0][index]
        context.append(f"Ticket ID: {ticket_id}\n\n{document}")
    return "\n\n".join(context)


def fallback_response():
    return {
        "resolution_available": False,
        "confidence": 0.0,
        "recommended_resolution": ["Sufficient context not provided."],
        "reasoning": "No sufficiently similar historical incidents found.",
        "source_tickets": []
    }


# ==========================================
# AGENTIC MAIN PIPELINE
# ==========================================

async def resolve_issue(issue_description: str) -> dict:
    """Agentic Resolution using LangGraph."""
    try:
        log_event("agent_resolution_started", issue_length=len(issue_description))

        initial_state = {
            "issue_description": issue_description,
            "source_tickets": [],
            "retrieved_context": "",
            "generation_result": None,
            "proposed_resolution": "",
            "validation_result": None,
            "final_resolution": None,
        }

        result = await asyncio.to_thread(
            agent_graph.invoke,
            initial_state,
            {"recursion_limit": 6},
        )

        final_resolution = result.get("final_resolution")
        if isinstance(final_resolution, dict) and final_resolution:
            return final_resolution

        if isinstance(result, dict) and result.get("recommended_resolution") is not None:
            return result

        return fallback_response()

    except Exception as exc:
        logger.exception(f"Agentic resolve_issue failed: {str(exc)}")
        return fallback_response()


# import json

# import chromadb

# from sentence_transformers import SentenceTransformer

# from langchain_groq import ChatGroq

# from langchain_core.prompts import ChatPromptTemplate

# from config import (
#     CHROMA_DB_PATH,
#     COLLECTION_NAME,
#     EMBEDDING_MODEL,
#     TOP_K,
#     SIMILARITY_THRESHOLD,
#     GROQ_MODEL,
#     GROQ_API_KEY
# )

# from prompt import PRODUCTION_PROMPT_V5

# from schemas import ResolutionResponse

# # from evaluation_queries import TEST_QUERIES


# # ==========================================
# # INITIALIZATION
# # ==========================================

# embedding_model = SentenceTransformer(
#     EMBEDDING_MODEL
# )

# chroma_client = chromadb.PersistentClient(
#     path=CHROMA_DB_PATH
# )

# collection = chroma_client.get_collection(
#     COLLECTION_NAME
    
# )

# llm = ChatGroq(
#     model=GROQ_MODEL,
#     api_key=GROQ_API_KEY,
#     temperature=0
# )


# # ==========================================
# # RETRIEVAL
# # ==========================================

# def retrieve_context(
#     issue_description
# ):

#     query_embedding = (
#         embedding_model
#         .encode(issue_description)
#         .tolist()
#     )

#     results = collection.query(
#         query_embeddings=[query_embedding],
#         n_results=TOP_K,
#         include=[
#             "documents",
#             "distances"
#         ]
#     )

#     print("\nRETRIEVAL RESULTS")

#     for i in range(
#         len(results["ids"][0])
#     ):

#         print("\n" + "=" * 80)

#         print(
#             f"Ticket ID: {results['ids'][0][i]}"
#         )

#         print(
#             f"Distance: {results['distances'][0][i]}"
#         )

#     distances = (
#         results["distances"][0]
#     )
#     source_tickets = []

#     for i in range(len(results["ids"][0])):

#         source_tickets.append(
#             {
#             "ticket_id":
#                 results["ids"][0][i],

#             "similarity_distance":
#                 round(
#                     results["distances"][0][i],
#                     4
#                 )
#            }
#        )
#     best_distance = min(
#         distances
#     )

#     print(
#         f"\nBest Similarity Distance: {best_distance}"
#     )

#     if (
#         best_distance >
#         SIMILARITY_THRESHOLD
#     ):

#         return None

#     return {
#     "chroma_results": results,
#     "source_tickets": source_tickets
# }


# # ==========================================
# # CONTEXT BUILDER
# # ==========================================

# def build_context(
#     retrieval_results
# ):

#     context = []

#     for index, document in enumerate(
#         retrieval_results["documents"][0]
#     ):

#         ticket_id = (
#             retrieval_results["ids"][0][index]
#         )

#         context.append(
#             f"""
# Ticket ID: {ticket_id}

# {document}
# """
#         )

#     return "\n\n".join(
#         context
#     )
# # ==========================================
# # CHAIN
# # ==========================================

# def create_chain():

#     structured_llm = (
#         llm.with_structured_output(
#             ResolutionResponse
#         )
#     )

#     prompt = (
#         ChatPromptTemplate
#         .from_messages(
#             [
#                 (
#                     "system",
#                     PRODUCTION_PROMPT_V5
#                 ),

#                 (
#                     "human",
#                     """
# Current Issue:

# {issue_description}

# Retrieved Historical Incidents:

# {retrieved_context}
# """
#                 )
#             ]
#         )
#     )

#     return prompt | structured_llm


# # ==========================================
# # FALLBACK RESPONSE
# # ==========================================

# def fallback_response():

#     return {
#         "resolution_available": False,
#         "confidence": 0.0,
#         "recommended_resolution":
#             "Sufficient context not provided.",
#         "reasoning":
#             "No sufficiently similar historical incidents found.",
#         "source_tickets": []
#     }


# # ==========================================
# # MAIN PIPELINE
# # ==========================================

# # ... (keep all existing imports, init, retrieve_context, build_context, etc.)

# from agent.graph import agent_graph
# from schemas import ResolutionResponse
# from logger import logger, log_event

# async def resolve_issue(issue_description: str) -> dict:
#     """Main entry point - now powered by Agentic LangGraph."""
#     try:
#         log_event("agent_invoked", ticket_issue=issue_description[:100])
        
#         initial_state = {
#             "messages": [HumanMessage(content=f"Resolve this ticket: {issue_description}")],
#             "issue_description": issue_description,
#             "final_resolution": None,
#             "iteration_count": 0
#         }
        
#         # Run agent (async compatible via to_thread if needed)
#         result = await asyncio.to_thread(agent_graph.invoke, initial_state, {"recursion_limit": 15})
        
#         final_msg = result["messages"][-1]
        
#         if hasattr(final_msg, "content") and "resolution" in final_msg.content.lower():
#             # Parse or fallback
#             return {
#                 "resolution_available": True,
#                 "recommended_resolution": final_msg.content,
#                 "source_tickets": result.get("source_tickets", []),
#                 "confidence": 0.85
#             }
        
#         # Fallback to old logic if needed
#         return fallback_response()
        
#     except Exception as e:
#         logger.exception(f"Agentic resolution failed: {e}")
#         return fallback_response()