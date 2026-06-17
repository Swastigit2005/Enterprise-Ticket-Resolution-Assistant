import mysql.connector
import chromadb

from sentence_transformers import SentenceTransformer

from config import (
    MYSQL_CONFIG,
    CHROMA_DB_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    DELTA_QUERY
)

# =========================
# INITIALIZATION
# =========================

conn = mysql.connector.connect(
    **MYSQL_CONFIG
)

cursor = conn.cursor(
    dictionary=True
)

client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH
)

collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)

model = SentenceTransformer(
    EMBEDDING_MODEL,
    trust_remote_code=True
)

# =========================
# DELTA FUNCTION
# =========================

def get_delta_tickets():

    cursor.execute(
        DELTA_QUERY
    )

    return cursor.fetchall()

# =========================
# UPDATE FUNCTION
# =========================

def mark_as_ingested(
    ticket_id
):

    update_query = """
    UPDATE tickets
    SET ingested = TRUE
    WHERE ticket_id = %s
    """

    cursor.execute(
        update_query,
        (ticket_id,)
    )

    conn.commit()

# =========================
# DOCUMENT BUILDER
# =========================

def build_document(
    ticket
):

    return f"""
    Issue Title:
    {ticket['issue_title']}

    Issue Description:
    {ticket['issue_description']}

    Resolution Steps:
    {ticket['resolution_steps']}
    """

# =========================
# EMBEDDING FUNCTION
# =========================

def generate_embedding(
    text
):

    return model.encode(
        text
    ).tolist()

# =========================
# MAIN INGESTION FUNCTION
# =========================

def ingest_tickets():

    tickets = get_delta_tickets()

    print(
        f"Found {len(tickets)} tickets to ingest"
    )

    for ticket in tickets:

        ticket_id = ticket["ticket_id"]

        document = build_document(
            ticket
        )

        embedding = generate_embedding(
            document
        )

        collection.add(
            ids=[ticket_id],

            embeddings=[embedding],

            documents=[document],

             metadatas=[
        {
            "issue_title": ticket["issue_title"]
        }
    ]

        )

        mark_as_ingested(
            ticket_id
        )

        print(
            f"Ingested: {ticket_id}"
        )

    print(
        "Ingestion completed successfully!"
    )

# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":

    ingest_tickets()

    cursor.close()
    conn.close()
    
    
    
    
    
    #earlier script
    
    # import mysql.connector
# import chromadb

# from sentence_transformers import SentenceTransformer

# # =========================
# # MYSQL CONNECTION
# # =========================

# conn = mysql.connector.connect(
#     host="localhost",
#     user="root",
#     password="Pihu@123",
#     database="ticket_system"
# )

# cursor = conn.cursor(dictionary=True)

# # =========================
# # FETCH NON-INGESTED TICKETS
# # =========================

# query = """
# SELECT *
# FROM tickets
# WHERE ingested = FALSE
# """

# cursor.execute(query)

# tickets = cursor.fetchall()

# print(f"Found {len(tickets)} tickets to ingest")

# # =========================
# # CHROMADB SETUP
# # =========================

# client = chromadb.PersistentClient(path="./chroma_db")

# collection = client.get_or_create_collection(
#     name="ticket_resolutions"
# )

# # =========================
# # EMBEDDING MODEL
# # =========================

# model = SentenceTransformer(
#     "all-MiniLM-L6-v2"
# )

# # =========================
# # INGEST TICKETS
# # =========================

# for ticket in tickets:

#     ticket_id = ticket["ticket_id"]

#     combined_text = f"""
#     Issue Title:
#     {ticket['issue_title']}

#     Issue Description:
#     {ticket['issue_description']}

#     Resolution Steps:
#     {ticket['resolution_steps']}
#     """

#     # =====================
#     # GENERATE EMBEDDING
#     # =====================

#     embedding = model.encode(
#         combined_text
#     ).tolist()

#     # =====================
#     # ADD TO VECTOR DB
#     # =====================

#     collection.add(
#         ids=[ticket_id],

#         embeddings=[embedding],

#         documents=[combined_text],

#         metadatas=[
#             {
#                 "status": ticket["status"]
#             }
#         ]
#     )

#     print(f"Ingested: {ticket_id}")

#     # =====================
#     # UPDATE SQL STATUS
#     # =====================

#     update_query = """
#     UPDATE tickets
#     SET ingested = TRUE
#     WHERE ticket_id = %s
#     """

#     cursor.execute(
#         update_query,
#         (ticket_id,)
#     )

#     conn.commit()

# # =========================
# # CLOSE CONNECTION
# # =========================

# cursor.close()
# conn.close()

# print("Ingestion completed successfully!")