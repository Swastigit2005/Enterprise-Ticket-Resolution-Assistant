import json

import chromadb

from sentence_transformers import SentenceTransformer

from langchain_groq import ChatGroq

from langchain_core.prompts import ChatPromptTemplate

from config import (
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    TOP_K,
    SIMILARITY_THRESHOLD,
    GROQ_MODEL,
    GROQ_API_KEY
)

from prompt import PRODUCTION_PROMPT_V5

from schemas import ResolutionResponse

# from evaluation_queries import TEST_QUERIES


# ==========================================
# INITIALIZATION
# ==========================================

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)

chroma_client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH
)

collection = chroma_client.get_collection(
    COLLECTION_NAME
    
)

llm = ChatGroq(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    temperature=0
)


# ==========================================
# RETRIEVAL
# ==========================================

def retrieve_context(
    issue_description
):

    query_embedding = (
        embedding_model
        .encode(issue_description)
        .tolist()
    )

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        include=[
            "documents",
            "distances"
        ]
    )

    print("\nRETRIEVAL RESULTS")

    for i in range(
        len(results["ids"][0])
    ):

        print("\n" + "=" * 80)

        print(
            f"Ticket ID: {results['ids'][0][i]}"
        )

        print(
            f"Distance: {results['distances'][0][i]}"
        )

    distances = (
        results["distances"][0]
    )
    source_tickets = []

    for i in range(len(results["ids"][0])):

        source_tickets.append(
            {
            "ticket_id":
                results["ids"][0][i],

            "similarity_distance":
                round(
                    results["distances"][0][i],
                    4
                )
           }
       )
    best_distance = min(
        distances
    )

    print(
        f"\nBest Similarity Distance: {best_distance}"
    )

    if (
        best_distance >
        SIMILARITY_THRESHOLD
    ):

        return None

    return {
    "chroma_results": results,
    "source_tickets": source_tickets
}


# ==========================================
# CONTEXT BUILDER
# ==========================================

def build_context(
    retrieval_results
):

    context = []

    for index, document in enumerate(
        retrieval_results["documents"][0]
    ):

        ticket_id = (
            retrieval_results["ids"][0][index]
        )

        context.append(
            f"""
Ticket ID: {ticket_id}

{document}
"""
        )

    return "\n\n".join(
        context
    )
# ==========================================
# CHAIN
# ==========================================

def create_chain():

    structured_llm = (
        llm.with_structured_output(
            ResolutionResponse
        )
    )

    prompt = (
        ChatPromptTemplate
        .from_messages(
            [
                (
                    "system",
                    PRODUCTION_PROMPT_V5
                ),

                (
                    "human",
                    """
Current Issue:

{issue_description}

Retrieved Historical Incidents:

{retrieved_context}
"""
                )
            ]
        )
    )

    return prompt | structured_llm


# ==========================================
# FALLBACK RESPONSE
# ==========================================

def fallback_response():

    return {
        "resolution_available": False,
        "confidence": 0.0,
        "recommended_resolution":
            "Sufficient context not provided.",
        "reasoning":
            "No sufficiently similar historical incidents found.",
        "source_tickets": []
    }


# ==========================================
# MAIN PIPELINE
# ==========================================

def resolve_issue(
    issue_description
):

    retrieval_data = retrieve_context(
    issue_description
    )

    if retrieval_data is None:
        return fallback_response()

    retrieval_results = (
        retrieval_data["chroma_results"]
    )
 
    source_tickets = (
        retrieval_data["source_tickets"]
    )

    retrieved_context = build_context(
        retrieval_results
    )

    chain = create_chain()

    response = chain.invoke(
        {
            "issue_description":
                issue_description,

            "retrieved_context":
                retrieved_context
        }
    )

    result = (
        response.model_dump()
    )

    result[
        "source_tickets"
    ] = source_tickets

    return result


# ==========================================
# EVALUATION
# ==========================================

# if __name__ == "__main__":

#     with open(
#         "evaluation_results.txt",
#         "w",
#         encoding="utf-8"
#     ) as f:

#         for query in TEST_QUERIES:

#             print("\n")
#             print("=" * 120)

#             print("RUNNING QUERY:")
#             print(query)

#             result = resolve_issue(
#                 query
#             )

#             f.write("\n")
#             f.write("=" * 120)
#             f.write("\n")

#             f.write(
#                 f"QUERY:\n{query}\n\n"
#             )

#             f.write(
#                 json.dumps(
#                     result,
#                     indent=4
#                 )
#             )

#             f.write("\n\n")

#     print(
#         "\nEvaluation completed. Results saved to evaluation_results.txt"
#     )


