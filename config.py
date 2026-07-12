import os
import configparser

from dotenv import load_dotenv

load_dotenv()

config = configparser.ConfigParser()
config.read("config.ini")

# =====================================================
# API KEY
# =====================================================

GROQ_API_KEY = (
    os.getenv("GROQ_API_KEY")
    or config["GROQ"]["API_KEY"]
)
# =====================================================
# SERVER
# =====================================================

API_URL = config["SERVER"]["API_URL"]

# =====================================================
# MYSQL
# =====================================================

MYSQL_CONFIG = {
    "host": config["DATABASE"]["HOST"],
    "user": config["DATABASE"]["USER"],
    "password": config["DATABASE"]["PASSWORD"],
    "database": config["DATABASE"]["DATABASE"],
}

# =====================================================
# LOGIN
# =====================================================

ADMIN_USERNAME = config["LOGIN"]["ADMIN_USERNAME"]
ADMIN_PASSWORD = config["LOGIN"]["ADMIN_PASSWORD"]

ADVOCATE_USERNAME = config["LOGIN"]["ADVOCATE_USERNAME"]
ADVOCATE_PASSWORD = config["LOGIN"]["ADVOCATE_PASSWORD"]

# =====================================================
# CHROMA
# =====================================================

CHROMA_DB_PATH = config["CHROMA"]["DB_PATH"]
COLLECTION_NAME = config["CHROMA"]["COLLECTION_NAME"]

# =====================================================
# EMBEDDING
# =====================================================

EMBEDDING_MODEL = config["LLM"]["EMBEDDING_MODEL"]

# =====================================================
# LLM
# =====================================================

GROQ_MODEL = config["LLM"]["MODEL"]

# =====================================================
# RETRIEVAL
# =====================================================

TOP_K = int(config["RETRIEVAL"]["TOP_K"])

SIMILARITY_THRESHOLD = float(
    config["RETRIEVAL"]["SIMILARITY_THRESHOLD"]
)

CONFIDENCE_THRESHOLD = float(
    config["RETRIEVAL"]["CONFIDENCE_THRESHOLD"]
)

# =====================================================
# DELTA QUERY
# =====================================================

DELTA_QUERY = """
SELECT
    ticket_id,
    issue_title,
    issue_description,
    resolution_steps
FROM tickets
WHERE ingested = FALSE
AND status='Resolved'
"""


MODEL_NAME = config["LLM"]["MODEL"]