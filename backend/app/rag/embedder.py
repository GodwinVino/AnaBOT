import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_embedder_instance = None
MODEL_NAME = "all-MiniLM-L6-v2"


def get_embedder() -> SentenceTransformer:
    """Lazy singleton embedder."""
    global _embedder_instance
    if _embedder_instance is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _embedder_instance = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded")
    return _embedder_instance
