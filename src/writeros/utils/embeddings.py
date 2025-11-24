import os
from typing import Callable, List
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
import logging

# Setup Logging
logger = logging.getLogger(__name__)

load_dotenv()

# Factory used to create or return the embedding service singleton. This indirection
# allows tests to swap in mocks without triggering API calls at import time.
_embedding_service_factory: Callable[[], "EmbeddingService"]

class EmbeddingService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("❌ OPENAI_API_KEY not found in environment variables.")
            raise ValueError("OPENAI_API_KEY is missing.")
        
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=api_key
        )
        logger.info("🧠 Embedding Service initialized (text-embedding-3-small)")

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        return self.embeddings.embed_documents(texts)
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Async wrapper for embed_documents (for compatibility with async chunker)."""
        return self.embed_documents(texts)


def set_embedding_service_factory(factory: Callable[[], "EmbeddingService"]):
    """Override the factory used to create EmbeddingService instances."""
    global _embedding_service_factory
    _embedding_service_factory = factory


def reset_embedding_service_singleton():
    """Reset the singleton instance (useful for tests)."""
    EmbeddingService._instance = None


def reset_embedding_service_factory():
    """Reset the embedding service factory to the default singleton creator."""
    set_embedding_service_factory(EmbeddingService)


def get_embedding_service() -> EmbeddingService:
    """Get the embedding service via the current factory."""
    return _embedding_service_factory()


# Initialize the default factory
reset_embedding_service_factory()
