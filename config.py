import os
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# ==========================================
# MYSQL CONFIG
# ==========================================

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Pihu@123",
    "database": "ticket_system"
}

# ==========================================
# CHROMADB CONFIG
# ==========================================

CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "ticket_resolutions"

# ==========================================
# EMBEDDING MODEL
# ==========================================

EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"

# ==========================================
# RETRIEVAL CONFIG
# ==========================================

TOP_K = 3

SIMILARITY_THRESHOLD = 0.80
CONFIDENCE_THRESHOLD = 0.80



GROQ_MODEL = "llama-3.3-70b-versatile"


# ==========================================
# DELTA QUERY
# ==========================================

DELTA_QUERY = """
SELECT
    ticket_id,
    issue_title,
    issue_description,
    resolution_steps
FROM tickets
WHERE ingested = FALSE
AND status = 'Resolved'
"""
