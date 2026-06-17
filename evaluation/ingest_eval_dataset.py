import pandas as pd
import chromadb

from sentence_transformers import SentenceTransformer

# ==========================================
# CONFIG
# ==========================================

TRAIN_DATASET = "vector_db_dataset.xlsx"

CHROMA_EVAL_DB_PATH = "./chroma_eval_db"

COLLECTION_NAME = "ticket_resolutions_eval"

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"

# ==========================================
# LOAD DATASET
# ==========================================

df = pd.read_excel(
    TRAIN_DATASET
)

print(
    f"Loaded {len(df)} training tickets"
)

# ==========================================
# CHROMA SETUP
# ==========================================

client = chromadb.PersistentClient(
    path=CHROMA_EVAL_DB_PATH
)

try:

    client.delete_collection(
        COLLECTION_NAME
    )

    print(
        "Old evaluation collection deleted."
    )

except Exception:

    pass

collection = client.create_collection(
    name=COLLECTION_NAME
)

# ==========================================
# EMBEDDING MODEL
# ==========================================

model = SentenceTransformer(
    EMBEDDING_MODEL,
    trust_remote_code=True
)

# ==========================================
# DOCUMENT BUILDER
# ==========================================

def build_document(ticket):

    return f"""
Issue Title:
{ticket['Issue_Title']}

Issue Description:
{ticket['Issue_Description']}

Resolution Steps:
{ticket['Resolution_Steps']}
"""

# ==========================================
# INGESTION
# ==========================================

for index, row in df.iterrows():

    ticket_id = row["Ticket_ID"]

    document = build_document(
        row
    )

    embedding = model.encode(
        document
    ).tolist()

    collection.add(
        ids=[
            str(ticket_id)
        ],

        embeddings=[
            embedding
        ],

        documents=[
            document
        ],

        metadatas=[
            {
                "issue_category":
                    str(
                        row["Issue_Category"]
                    ),

                "status":
                    str(
                        row["Status"]
                    )
            }
        ]
    )

    print(
        f"Ingested {index + 1}/{len(df)} : {ticket_id}"
    )

# ==========================================
# COMPLETE
# ==========================================

print(
    "\nEvaluation vector database created successfully."
)

print(
    f"Total tickets ingested: {len(df)}"
)