"""
Unit tests for EmbeddingService.

Tests singleton pattern, embedding generation, and error handling.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from writeros.utils.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingService,
    reset_embedding_service_factory,
    reset_embedding_service_singleton,
)


@pytest.fixture(autouse=True)
def reset_embedding_service_state():
    """Ensure the singleton and factory are clean between tests."""
    reset_embedding_service_singleton()
    reset_embedding_service_factory()
    yield
    reset_embedding_service_singleton()
    reset_embedding_service_factory()


class TestEmbeddingService:
    """Test suite for EmbeddingService."""
    
    def test_singleton_pattern_same_model(self):
        """Test that EmbeddingService is a singleton per model."""
        service1 = EmbeddingService()
        service2 = EmbeddingService(DEFAULT_EMBEDDING_MODEL)

        assert service1 is service2

    def test_different_models_create_distinct_instances(self):
        """Different embedding models should yield different instances."""
        default_service = EmbeddingService()
        other_service = EmbeddingService("BAAI/bge-base-en-v1.5")

        assert default_service is not other_service

    @patch("writeros.utils.embeddings.TextEmbedding")
    def test_initialization_with_default_model(self, mock_text_embedding):
        """Test successful initialization with default model."""
        service = EmbeddingService()

        assert service is not None
        mock_text_embedding.assert_called_once_with(
            model_name="BAAI/bge-small-en-v1.5"
        )

    @patch("writeros.utils.embeddings.TextEmbedding")
    def test_initialization_with_custom_model(self, mock_text_embedding):
        """Test initialization honors a custom embedding model."""
        service = EmbeddingService("BAAI/bge-base-en-v1.5")

        assert service is not None
        mock_text_embedding.assert_called_once_with(
            model_name="BAAI/bge-base-en-v1.5"
        )
    
    @patch("writeros.utils.embeddings.TextEmbedding")
    def test_embed_query(self, mock_text_embedding):
        """Test single query embedding."""
        # Mock the embeddings object
        mock_embedder = MagicMock()
        mock_array = np.array([0.1, 0.2, 0.3])
        mock_embedder.embed.return_value = [mock_array]
        mock_text_embedding.return_value = mock_embedder

        service = EmbeddingService()
        result = service.embed_query("test query")

        assert result == [0.1, 0.2, 0.3]
        mock_embedder.embed.assert_called_once_with(["test query"])
    
    @patch("writeros.utils.embeddings.TextEmbedding")
    def test_embed_documents(self, mock_text_embedding):
        """Test batch document embedding."""
        # Mock the embeddings object
        mock_embedder = MagicMock()
        mock_array1 = np.array([0.1, 0.2, 0.3])
        mock_array2 = np.array([0.4, 0.5, 0.6])
        mock_embedder.embed.return_value = [mock_array1, mock_array2]
        mock_text_embedding.return_value = mock_embedder

        service = EmbeddingService()
        result = service.embed_documents(["doc1", "doc2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
        mock_embedder.embed.assert_called_once_with(["doc1", "doc2"])
    
    @patch("writeros.utils.embeddings.TextEmbedding")
    def test_embed_empty_string(self, mock_text_embedding):
        """Test embedding of empty string."""
        mock_embedder = MagicMock()
        # FastEmbed models typically have 384 dimensions for bge-small
        mock_array = np.array([0.0] * 384)
        mock_embedder.embed.return_value = [mock_array]
        mock_text_embedding.return_value = mock_embedder

        service = EmbeddingService()
        result = service.embed_query("")

        assert len(result) == 384

    @patch("writeros.utils.embeddings.TextEmbedding")
    def test_embed_documents_empty_list(self, mock_text_embedding):
        """Test embedding of empty document list."""
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = []
        mock_text_embedding.return_value = mock_embedder

        service = EmbeddingService()
        result = service.embed_documents([])

        assert result == []


class TestEmbeddingServiceIntegration:
    """Integration tests for EmbeddingService."""

    @patch("writeros.utils.embeddings.TextEmbedding")
    def test_multiple_calls_use_same_instance(self, mock_text_embedding):
        """Test that multiple calls use the same singleton instance."""
        mock_embedder = MagicMock()
        mock_text_embedding.return_value = mock_embedder

        service1 = EmbeddingService()
        service2 = EmbeddingService()

        # Should only initialize once
        assert mock_text_embedding.call_count == 1
        assert service1 is service2
