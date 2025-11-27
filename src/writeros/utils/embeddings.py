import os
from typing import Callable, List, Optional
from fastembed import TextEmbedding
from dotenv import load_dotenv
import logging

# Setup Logging
logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Factory used to create or return the embedding service singleton. This indirection
# allows tests to swap in mocks without triggering API calls at import time.
_embedding_service_factory: Callable[[Optional[str]], "EmbeddingService"]

class EmbeddingService:
    _instances = {}

    def __new__(cls, model: Optional[str] = None):
        embedding_model = model or DEFAULT_EMBEDDING_MODEL

        if embedding_model not in cls._instances:
            instance = super().__new__(cls)
            instance._initialize(embedding_model)
            cls._instances[embedding_model] = instance

        return cls._instances[embedding_model]

    def _initialize(self, model: str):
        # FastEmbed runs locally, no API key needed
        self.embeddings = TextEmbedding(model_name=model)
        self.model = model
        logger.info("FastEmbed Embedding Service initialized (%s)", model)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        # FastEmbed returns a generator, convert to list
        return list(self.embeddings.embed([text]))[0].tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        # FastEmbed returns a generator of numpy arrays, convert to list of lists
        return [embedding.tolist() for embedding in self.embeddings.embed(texts)]
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Async wrapper for embed_documents (for compatibility with async chunker)."""
        return self.embed_documents(texts)


def set_embedding_service_factory(factory: Callable[[Optional[str]], "EmbeddingService"]):
    """Override the factory used to create EmbeddingService instances."""
    global _embedding_service_factory
    _embedding_service_factory = factory


def reset_embedding_service_singleton():
    """Reset the singleton instance (useful for tests)."""
    EmbeddingService._instances = {}


def reset_embedding_service_factory():
    """Reset the embedding service factory to the default singleton creator."""
    set_embedding_service_factory(EmbeddingService)


def get_embedding_service(embedding_model: Optional[str] = None) -> EmbeddingService:
    """Get the embedding service via the current factory."""
    return _embedding_service_factory(embedding_model)


# Initialize the default factory
reset_embedding_service_factory()
