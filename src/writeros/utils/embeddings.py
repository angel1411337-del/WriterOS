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
    """
    Unified embedding service supporting both FastEmbed (local) and OpenAI (API).

    Automatically detects provider based on model name:
    - OpenAI models: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
    - FastEmbed models: BAAI/bge-*, snowflake/*, mixedbread-ai/*, etc.
    """
    _instances = {}

    def __new__(cls, model: Optional[str] = None):
        embedding_model = model or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

        if embedding_model not in cls._instances:
            instance = super().__new__(cls)
            instance._initialize(embedding_model)
            cls._instances[embedding_model] = instance

        return cls._instances[embedding_model]

    def _initialize(self, model: str):
        self.model = model

        # Detect provider based on model name
        if model.startswith("text-embedding-"):
            # OpenAI model
            self.provider = "openai"
            self._init_openai(model)
        else:
            # FastEmbed model (default)
            self.provider = "fastembed"
            self._init_fastembed(model)

    def _init_fastembed(self, model: str):
        """Initialize FastEmbed (local, free)."""
        self.embeddings = TextEmbedding(model_name=model)
        logger.info("FastEmbed Embedding Service initialized (%s)", model)

    def _init_openai(self, model: str):
        """Initialize OpenAI API (requires API key)."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI library not installed. "
                "Install with: pip install openai"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Please set it in your .env file."
            )

        self.client = OpenAI(api_key=api_key)

        # Get dimensions for this model
        self.dimensions = self._get_openai_dimensions(model)

        logger.info(
            "OpenAI Embedding Service initialized (%s, %d dimensions)",
            model,
            self.dimensions
        )

    def _get_openai_dimensions(self, model: str) -> int:
        """Get default dimensions for OpenAI model."""
        if model == "text-embedding-3-small":
            return 1536
        elif model == "text-embedding-3-large":
            return 3072
        elif model == "text-embedding-ada-002":
            return 1536
        else:
            # Default to 1536 for unknown models
            logger.warning(f"Unknown OpenAI model {model}, assuming 1536 dimensions")
            return 1536

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        if self.provider == "openai":
            return self._embed_openai([text])[0]
        else:
            # FastEmbed returns a generator, convert to list
            return list(self.embeddings.embed([text]))[0].tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        if self.provider == "openai":
            return self._embed_openai(texts)
        else:
            # FastEmbed returns a generator of numpy arrays, convert to list of lists
            return [embedding.tolist() for embedding in self.embeddings.embed(texts)]

    def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using OpenAI API."""
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float"
        )

        # Extract embeddings from response
        embeddings = [item.embedding for item in response.data]

        logger.debug(
            "OpenAI embedding created: %d texts, %d dimensions",
            len(texts),
            len(embeddings[0]) if embeddings else 0
        )

        return embeddings

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Async wrapper for embed_documents (for compatibility with async chunker)."""
        return self.embed_documents(texts)

    async def embed_documents_async(self, texts: List[str]) -> List[List[float]]:
        """Async wrapper for embed_documents (for pipeline compatibility)."""
        return self.embed_documents(texts)

    def get_dimensions(self) -> int:
        """Get the dimensionality of embeddings produced by this model."""
        if self.provider == "openai":
            return self.dimensions
        else:
            # For FastEmbed, embed a test string to get dimensions
            test_embedding = self.embed_query("test")
            return len(test_embedding)


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
