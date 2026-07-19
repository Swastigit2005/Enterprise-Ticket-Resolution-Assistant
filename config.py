import streamlit as st
import configparser

# 1. Production Mode: Pull from secure environment parameters if deployed on Streamlit Cloud
if hasattr(st, "secrets") and "DATABASE" in st.secrets:
    DB_HOST = st.secrets["DATABASE"]["HOST"]
    DB_PORT = int(st.secrets["DATABASE"]["PORT"])
    DB_USER = st.secrets["DATABASE"]["USER"]
    DB_PASSWORD = st.secrets["DATABASE"]["PASSWORD"]
    DB_NAME = st.secrets["DATABASE"]["DATABASE"]
    GROQ_API_KEY = st.secrets["GROQ"]["API_KEY"]
    
    ADMIN_USERNAME = st.secrets["LOGIN"]["ADMIN_USERNAME"]
    ADMIN_PASSWORD = st.secrets["LOGIN"]["ADMIN_PASSWORD"]
    ADVOCATE_USERNAME = st.secrets["LOGIN"]["ADVOCATE_USERNAME"]
    ADVOCATE_PASSWORD = st.secrets["LOGIN"]["ADVOCATE_PASSWORD"]
    
    # Safely get API_URL from secrets, or default to localhost if not hosted yet
    if "SERVER" in st.secrets and "API_URL" in st.secrets["SERVER"]:
        API_URL = st.secrets["SERVER"]["API_URL"]
    else:
        API_URL = "http://127.0.0.1:8001"

# 2. Local Mode: Pull from your standard config.ini file when testing locally
else:
    config = configparser.ConfigParser()
    config.read("config.ini")
    
    DB_HOST = config["DATABASE"]["HOST"]
    DB_PORT = int(config["DATABASE"].get("PORT", 3306))
    DB_USER = config["DATABASE"]["USER"]
    DB_PASSWORD = config["DATABASE"]["PASSWORD"]
    DB_NAME = config["DATABASE"]["DATABASE"]
    GROQ_API_KEY = config["GROQ"]["API_KEY"]
    
    ADMIN_USERNAME = config["LOGIN"]["ADMIN_USERNAME"]
    ADMIN_PASSWORD = config["LOGIN"]["ADMIN_PASSWORD"]
    ADVOCATE_USERNAME = config["LOGIN"]["ADVOCATE_USERNAME"]
    ADVOCATE_PASSWORD = config["LOGIN"]["ADVOCATE_PASSWORD"]
    
    # Safe check for local config file sections
    if config.has_section("SERVER") and config.has_option("SERVER", "API_URL"):
        API_URL = config["SERVER"]["API_URL"]
    else:
        API_URL = "http://127.0.0.1:8001"

# Fixed Chroma DB parameter defaults
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "ticket_resolutions"
LLM_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
TOP_K = 3
SIMILARITY_THRESHOLD = 0.70
CONFIDENCE_THRESHOLD = 0.70
