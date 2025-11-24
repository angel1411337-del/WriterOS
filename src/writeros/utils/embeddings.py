import os
from typing import List
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
import logging

# Setup Logging
logger = logging.getLogger(__name__)

load_dotenv()

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

# Global instance
embedding_service = EmbeddingService()
