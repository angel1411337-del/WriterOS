"""
Unit tests for ClusterSemanticChunker.

Tests semantic segmentation, clustering logic, chunk size constraints,
and edge cases.
"""
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from writeros.preprocessing.chunker import SemanticChunker, Chunk


class TestSemanticChunker:
    """Test suite for SemanticChunker."""
    
    @pytest.fixture
    def chunker(self):
        """Create a chunker instance."""
        return SemanticChunker(
            min_chunk_size=50,
            max_chunk_size=400,
            embedding_model="text-embedding-3-small"
        )
    
    @pytest.fixture
    def mock_embedder(self, mocker):
        """Mock the embedding service."""
        # Mock the EmbeddingService class itself
        mock_service = MagicMock()
        
        # Return different vectors for different segments
        async def mock_get_embeddings(texts):
            return [[0.1 * i] * 1536 for i in range(len(texts))]
        
        mock_service.get_embeddings = AsyncMock(side_effect=mock_get_embeddings)
        
        # Patch where it's imported
        mocker.patch("writeros.utils.embeddings.EmbeddingService", return_value=mock_service)
        
        return mock_service
    
    # Test Sentence Segmentation
    
    def test_split_into_segments_basic(self, chunker):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence. Third sentence."
        segments = chunker._split_into_segments(text)
        
        assert len(segments) == 3
        assert segments[0] == "First sentence."
        assert segments[1] == "Second sentence."
        assert segments[2] == "Third sentence."
    
    def test_split_into_segments_empty_text(self, chunker):
        """Test handling of empty text."""
        segments = chunker._split_into_segments("")
        assert segments == []
    
    def test_split_into_segments_single_sentence(self, chunker):
        """Test single sentence."""
        text = "Only one sentence here."
        segments = chunker._split_into_segments(text)
        
        assert len(segments) == 1
        assert segments[0] == "Only one sentence here."
    
    # Test Edge Cases
    
    @pytest.mark.asyncio
    async def test_empty_text(self, chunker, mock_embedder):
        """Test handling of empty text."""
        chunks = await chunker.chunk_document("")
        assert chunks == []
    
    @pytest.mark.asyncio
    async def test_single_sentence_text(self, chunker, mock_embedder):
        """Test text with only one sentence."""
        text = "This is a single sentence that is reasonably long and contains enough words to make a chunk."
        chunks = await chunker.chunk_document(text)
        
        assert len(chunks) >= 1
        assert text in chunks[0]["content"]
    
    @pytest.mark.asyncio
    async def test_basic_chunking(self, chunker, mock_embedder):
        """Test basic chunking functionality."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = await chunker.chunk_document(text)
        
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("embedding" in chunk for chunk in chunks)
        assert all("coherence_score" in chunk for chunk in chunks)
    
    @pytest.mark.asyncio
    async def test_coherence_score_present(self, chunker, mock_embedder):
        """Test that coherence scores are calculated."""
        text = "First sentence. Second sentence. Third sentence."
        chunks = await chunker.chunk_document(text)

        for chunk in chunks:
            assert "coherence_score" in chunk
            assert isinstance(chunk["coherence_score"], float)
            assert 0.0 <= chunk["coherence_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_coherence_score_varied_similarity(self, chunker, mocker):
        """Ensure coherence reflects mixed segment similarity."""
        text = (
            "Vector one points on x. Vector two points on negative x. "
            "Vector three points on y."
        )

        diverse_embeddings = [
            [1.0, 0.0],
            [-1.0, 0.0],
            [0.0, 1.0],
        ]

        mock_service = MagicMock()
        mock_service.get_embeddings = AsyncMock(return_value=diverse_embeddings)
        mocker.patch("writeros.utils.embeddings.EmbeddingService", return_value=mock_service)

        chunks = await chunker.chunk_document(text)

        coherence = chunks[0]["coherence_score"]
        assert isinstance(coherence, float)
        assert coherence == pytest.approx(2 / 3, rel=1e-6)
        assert 0.0 < coherence < 1.0
