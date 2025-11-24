"""
Unit tests for EmbeddingService.

Tests singleton pattern, embedding generation, and error handling.
"""
import pytest
from unittest.mock import MagicMock, patch
from writeros.utils.embeddings import EmbeddingService


class TestEmbeddingService:
    """Test suite for EmbeddingService."""
    
    def test_singleton_pattern(self):
        """Test that EmbeddingService is a singleton."""
        service1 = EmbeddingService()
        service2 = EmbeddingService()
        
        assert service1 is service2
    
    @patch("writeros.utils.embeddings.OpenAIEmbeddings")
    @patch("writeros.utils.embeddings.os.getenv")
    def test_initialization_with_api_key(self, mock_getenv, mock_openai_embeddings):
        """Test successful initialization with API key."""
        mock_getenv.return_value = "test-api-key"
        
        # Reset singleton
        EmbeddingService._instance = None
        
        service = EmbeddingService()
        
        assert service is not None
        mock_openai_embeddings.assert_called_once_with(
            model="text-embedding-3-small",
            openai_api_key="test-api-key"
        )
    
    @patch("writeros.utils.embeddings.os.getenv")
    def test_initialization_without_api_key(self, mock_getenv):
        """Test that initialization fails without API key."""
        mock_getenv.return_value = None
        
        # Reset singleton
        EmbeddingService._instance = None
        
        with pytest.raises(ValueError, match="OPENAI_API_KEY is missing"):
            EmbeddingService()
    
    @patch("writeros.utils.embeddings.OpenAIEmbeddings")
    @patch("writeros.utils.embeddings.os.getenv")
    def test_embed_query(self, mock_getenv, mock_openai_embeddings):
        """Test single query embedding."""
        mock_getenv.return_value = "test-api-key"
        
        # Reset singleton
        EmbeddingService._instance = None
        
        # Mock the embeddings object
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1, 0.2, 0.3]
        mock_openai_embeddings.return_value = mock_embedder
        
        service = EmbeddingService()
        result = service.embed_query("test query")
        
        assert result == [0.1, 0.2, 0.3]
        mock_embedder.embed_query.assert_called_once_with("test query")
    
    @patch("writeros.utils.embeddings.OpenAIEmbeddings")
    @patch("writeros.utils.embeddings.os.getenv")
    def test_embed_documents(self, mock_getenv, mock_openai_embeddings):
        """Test batch document embedding."""
        mock_getenv.return_value = "test-api-key"
        
        # Reset singleton
        EmbeddingService._instance = None
        
        # Mock the embeddings object
        mock_embedder = MagicMock()
        mock_embedder.embed_documents.return_value = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6]
        ]
        mock_openai_embeddings.return_value = mock_embedder
        
        service = EmbeddingService()
        result = service.embed_documents(["doc1", "doc2"])
        
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
        mock_embedder.embed_documents.assert_called_once_with(["doc1", "doc2"])
    
    @patch("writeros.utils.embeddings.OpenAIEmbeddings")
    @patch("writeros.utils.embeddings.os.getenv")
    def test_embed_empty_string(self, mock_getenv, mock_openai_embeddings):
        """Test embedding of empty string."""
        mock_getenv.return_value = "test-api-key"
        
        # Reset singleton
        EmbeddingService._instance = None
        
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.0] * 1536
        mock_openai_embeddings.return_value = mock_embedder
        
        service = EmbeddingService()
        result = service.embed_query("")
        
        assert len(result) == 1536
    
    @patch("writeros.utils.embeddings.OpenAIEmbeddings")
    @patch("writeros.utils.embeddings.os.getenv")
    def test_embed_documents_empty_list(self, mock_getenv, mock_openai_embeddings):
        """Test embedding of empty document list."""
        mock_getenv.return_value = "test-api-key"
        
        # Reset singleton
        EmbeddingService._instance = None
        
        mock_embedder = MagicMock()
        mock_embedder.embed_documents.return_value = []
        mock_openai_embeddings.return_value = mock_embedder
        
        service = EmbeddingService()
        result = service.embed_documents([])
        
        assert result == []


class TestEmbeddingServiceIntegration:
    """Integration tests for EmbeddingService."""
    
    @patch("writeros.utils.embeddings.OpenAIEmbeddings")
    @patch("writeros.utils.embeddings.os.getenv")
    def test_multiple_calls_use_same_instance(self, mock_getenv, mock_openai_embeddings):
        """Test that multiple calls use the same singleton instance."""
        mock_getenv.return_value = "test-api-key"
        
        # Reset singleton
        EmbeddingService._instance = None
        
        mock_embedder = MagicMock()
        mock_openai_embeddings.return_value = mock_embedder
        
        service1 = EmbeddingService()
        service2 = EmbeddingService()
        
        # Should only initialize once
        assert mock_openai_embeddings.call_count == 1
        assert service1 is service2
