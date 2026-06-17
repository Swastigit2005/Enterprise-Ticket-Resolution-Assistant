import chromadb

from sentence_transformers import (
    SentenceTransformer
)

from langchain_core.prompts import (
    ChatPromptTemplate
)

from langchain_groq import (
    ChatGroq
)

from eval_config import (
    CHROMA_EVAL_DB_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    TOP_K,
    SIMILARITY_THRESHOLD,
    PRODUCTION_PROMPT_V7
)

from schemas import (
    ResolutionResponse
)

# ==========================================
# CHROMA
# ==========================================

chroma_client = chromadb.PersistentClient(
    path=CHROMA_EVAL_DB_PATH
)

collection = chroma_client.get_collection(
    COLLECTION_NAME
)

# ==========================================
# EMBEDDING MODEL
# ==========================================

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL,
    trust_remote_code=True
)

# ==========================================
# LLM
# ==========================================

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)

structured_llm = (
    llm.with_structured_output(
        ResolutionResponse
    )
)

# ==========================================
# CHAIN
# ==========================================

prompt = ChatPromptTemplate.from_template(
    PRODUCTION_PROMPT_V7
)

chain = prompt | structured_llm

# ==========================================
# RETRIEVAL
# ==========================================

def retrieve_context(
    query
):

    query_embedding = (
        embedding_model.encode(
            query
        ).tolist()
    )

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=TOP_K
    )

    print(
        "\nRETRIEVAL RESULTS"
    )

    for i in range(
        len(results["ids"][0])
    ):

        print(
            "\n" + "=" * 80
        )

        print(
            f"Ticket ID: "
            f"{results['ids'][0][i]}"
        )

        print(
            f"Distance: "
            f"{results['distances'][0][i]}"
        )

    best_distance = (
        results["distances"][0][0]
    )

    print(
        f"\nBest Similarity Distance: "
        f"{best_distance}"
    )

    if (
        best_distance >
        SIMILARITY_THRESHOLD
    ):
        return None

    return results

# ==========================================
# BUILD CONTEXT
# ==========================================

def build_context(
    retrieval_results
):

    context = []

    for doc in retrieval_results[
        "documents"
    ][0]:

        context.append(doc)

    return "\n\n".join(
        context
    )

# ==========================================
# SOURCE TICKETS
# ==========================================

def get_source_tickets(
    retrieval_results
):

    tickets = []

    ids = retrieval_results[
        "ids"
    ][0]

    docs = retrieval_results[
        "documents"
    ][0]

    distances = retrieval_results[
        "distances"
    ][0]

    for ticket_id, doc, distance in zip(
        ids,
        docs,
        distances
    ):

        tickets.append(
            {
                "ticket_id":
                    ticket_id,

                "issue_description":
                    doc,

                "similarity_distance":
                    round(
                        distance,
                        4
                    )
            }
        )

    return tickets

# ==========================================
# FALLBACK
# ==========================================

def fallback_response():

    return {
        "resolution_available":
            False,

        "confidence":
            0.0,

        "recommended_resolution":
            "Sufficient context not provided.",

        "reasoning":
            "No sufficiently similar historical incidents found.",

        "source_tickets":
            []
    }

# ==========================================
# MAIN FUNCTION
# ==========================================

def resolve_issue(
    issue_description
):

    retrieval_results = (
        retrieve_context(
            issue_description
        )
    )

    if retrieval_results is None:

        return fallback_response()

    retrieved_context = (
        build_context(
            retrieval_results
        )
    )

    source_tickets = (
        get_source_tickets(
            retrieval_results
        )
    )

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