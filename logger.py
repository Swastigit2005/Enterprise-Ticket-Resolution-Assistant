
import logging
import os

# Create logs directory
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("PersistentSystem")

if logger.hasHandlers():
    logger.handlers.clear()

logger.setLevel(logging.INFO)

logger.propagate = False

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s"
)

file_handler = logging.FileHandler(
    "logs/application.log",
    encoding="utf-8"
)

file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.ERROR)

error_handler = logging.FileHandler(
    "logs/error.log",
    encoding="utf-8"
)

error_handler.setLevel(logging.ERROR)

error_handler.setFormatter(formatter)

logger.addHandler(error_handler)