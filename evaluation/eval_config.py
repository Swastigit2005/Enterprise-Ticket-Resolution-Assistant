# ==========================================
# EVALUATION CHROMA CONFIG
# ==========================================

CHROMA_EVAL_DB_PATH = "./chroma_eval_db"

COLLECTION_NAME = "ticket_resolutions_eval"

# ==========================================
# EMBEDDING MODEL
# ==========================================

EMBEDDING_MODEL = (
    "Qwen/Qwen3-Embedding-0.6B"
)

# ==========================================
# RETRIEVAL SETTINGS
# ==========================================

TOP_K = 3

SIMILARITY_THRESHOLD = 0.80

# ==========================================
# LLM SETTINGS
# ==========================================

LLM_MODEL = (
    "llama-3.1-8b-instant"
    # "llama-3.3-70b-versatile"
)

import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ==========================================
# PRODUCTION PROMPT
# ==========================================

from prompt import (
    PRODUCTION_PROMPT_V7
)