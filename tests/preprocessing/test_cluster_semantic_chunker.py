"""
Comprehensive tests for ClusterSemanticChunker.

Test Coverage:
1. Unit tests for each component (similarity matrix, DP, etc.)
2. Integration tests with real embeddings
3. Edge cases (empty text, single sentence, etc.)
4. Performance benchmarks
5. Comparison with baseline chunkers
"""
import pytest
import numpy as np
from unittest.mock import MagicMock
from writeros.preprocessing.cluster_semantic_chunker import (
    ClusterSemanticChunker,
    ChunkResult
)


# Module-level fixture for mock embedding function
@pytest.fixture
def mock_embedding_function():
    """Create mock embedding function that returns deterministic vectors."""
    def mock_embed(text: str) -> list:
        # Create embedding based on text content
        # Similar texts get similar embeddings
        words = text.lower().split()

        # Topic 1: "history", "past", "ancient" → [1.0, 0.0, 0.0, ...]
        # Topic 2: "product", "feature", "software" → [0.0, 1.0, 0.0, ...]
        # Topic 3: "legal", "terms", "rights" → [0.0, 0.0, 1.0, ...]

        vec = [0.0] * 1536

        if any(w in words for w in ["history", "past", "ancient", "founded"]):
            vec[0] = 1.0
        if any(w in words for w in ["product", "feature", "software", "app"]):
            vec[1] = 1.0
        if any(w in words for w in ["legal", "terms", "rights", "disclaimer"]):
            vec[2] = 1.0

        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    return mock_embed


class TestClusterSemanticChunkerUnit:
    """Unit tests for individual components."""

    def test_initialization(self):
        """Test chunker initializes with correct parameters."""
        chunker = ClusterSemanticChunker(
            min_chunk_size=50,
            max_chunk_size=400
        )

        assert chunker.min_chunk_size == 50
        assert chunker.max_chunk_size == 400
        assert chunker.max_cluster == 8  # 400 // 50
        assert chunker.tokenizer is not None

    def test_split_into_base_segments_simple(self):
        """Test splitting simple text into segments."""
        chunker = ClusterSemanticChunker(min_chunk_size=10)

        text = "First sentence. Second sentence. Third sentence."
        segments = chunker._split_into_base_segments(text)

        assert len(segments) > 0
        assert all(isinstance(s, str) for s in segments)
        assert all(len(s.strip()) > 0 for s in segments)

    def test_split_into_base_segments_paragraphs(self):
        """Test paragraph-aware splitting."""
        chunker = ClusterSemanticChunker(min_chunk_size=20)

        text = """First paragraph with multiple sentences. It has more content.

Second paragraph here. Also with sentences.

Third paragraph."""

        segments = chunker._split_into_base_segments(text)

        # Should create segments respecting paragraphs
        assert len(segments) >= 3

    def test_split_sentences(self):
        """Test sentence splitting."""
        chunker = ClusterSemanticChunker()

        text = "First sentence. Second sentence! Third sentence? Fourth."
        sentences = chunker._split_sentences(text)

        assert len(sentences) == 4
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence!"

    def test_build_similarity_matrix(self):
        """Test similarity matrix construction."""
        chunker = ClusterSemanticChunker()

        # Create mock embeddings (3 vectors, 4 dimensions)
        embeddings = np.array([
            [1.0, 0.0, 0.0, 0.0],  # v0
            [0.9, 0.1, 0.0, 0.0],  # v1: similar to v0
            [0.0, 0.0, 1.0, 0.0],  # v2: different from v0, v1
        ], dtype=np.float32)

        similarity = chunker._build_similarity_matrix(embeddings)

        # Check properties
        assert similarity.shape == (3, 3)
        assert np.allclose(np.diag(similarity), 0)  # Diagonal is zero

        # v0 and v1 should be similar (high value)
        # v0/v1 and v2 should be dissimilar (low/negative value)
        assert similarity[0, 1] > similarity[0, 2]

    def test_compute_chunk_reward(self):
        """Test reward computation for a chunk."""
        chunker = ClusterSemanticChunker()

        # Create similarity matrix with known values
        similarity = np.array([
            [0.0, 0.8, 0.2],
            [0.8, 0.0, 0.1],
            [0.2, 0.1, 0.0]
        ], dtype=np.float32)

        # Reward for chunk [0, 1]
        reward = chunker._compute_chunk_reward(similarity, 0, 1)

        # Should sum sub-matrix: [0, 0.8; 0.8, 0] = 1.6
        assert np.isclose(reward, 1.6, atol=0.01)

        # Reward for chunk [0, 2] (all three)
        reward_all = chunker._compute_chunk_reward(similarity, 0, 2)

        # Sum of entire matrix
        expected = similarity.sum()
        assert np.isclose(reward_all, expected, atol=0.01)

    def test_find_optimal_segmentation_simple(self):
        """Test DP segmentation with simple case."""
        chunker = ClusterSemanticChunker(max_chunk_size=100, min_chunk_size=50)
        # max_cluster = 2

        # Create similarity matrix favoring grouping [0,1] and [2,3]
        # High intra-group similarity, low inter-group
        similarity = np.array([
            [0.0, 0.9, 0.1, 0.1],  # 0: similar to 1
            [0.9, 0.0, 0.1, 0.1],  # 1: similar to 0
            [0.1, 0.1, 0.0, 0.9],  # 2: similar to 3
            [0.1, 0.1, 0.9, 0.0],  # 3: similar to 2
        ], dtype=np.float32)

        boundaries = chunker._find_optimal_segmentation(similarity)

        # Should create chunks: [0,1] and [2,3]
        assert len(boundaries) == 2
        assert boundaries[0] == (0, 1)
        assert boundaries[1] == (2, 3)

    def test_merge_segments(self):
        """Test merging base segments into final chunks."""
        chunker = ClusterSemanticChunker()

        segments = ["First.", "Second.", "Third.", "Fourth."]
        boundaries = [(0, 1), (2, 3)]

        chunks = chunker._merge_segments(segments, boundaries)

        assert len(chunks) == 2
        assert chunks[0] == "First. Second."
        assert chunks[1] == "Third. Fourth."

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunker = ClusterSemanticChunker()

        result = chunker.chunk("")

        assert result.chunks == []
        assert result.metadata["segments"] == 0
        assert result.metadata["chunks"] == 0

    def test_chunk_single_segment(self):
        """Test chunking text that fits in one segment."""
        chunker = ClusterSemanticChunker(min_chunk_size=100)

        text = "Short text."
        result = chunker.chunk(text)

        assert len(result.chunks) == 1
        assert result.chunks[0] == text

    def test_fallback_without_embedding_function(self):
        """Test fallback chunking when no embedding function provided."""
        chunker = ClusterSemanticChunker(
            min_chunk_size=10,
            max_chunk_size=50
        )

        # Longer text to create multiple segments
        text = ". ".join([f"Sentence number {i} with some content here" for i in range(20)])
        result = chunker.chunk(text)

        # Should fall back to token overlap when no embedding function
        assert len(result.chunks) > 0
        assert "algorithm" in result.metadata
        assert result.metadata["algorithm"] == "token_overlap_fallback"


class TestClusterSemanticChunkerIntegration:
    """Integration tests with mock embeddings."""

    def test_chunk_with_topic_shifts(self, mock_embedding_function):
        """Test chunking text with clear topic shifts."""
        chunker = ClusterSemanticChunker(
            min_chunk_size=20,
            max_chunk_size=100,
            embedding_function=mock_embedding_function
        )

        text = """
        Our company was founded in 1995. The history of our organization spans decades.
        We started as a small startup in the past. Ancient traditions guide our values.

        Today we offer cutting-edge software products. Our app features real-time collaboration.
        The product includes advanced tools. These features make development faster.

        Legal disclaimer: All rights reserved. Terms and conditions apply here.
        This legal notice protects our rights. Please read these terms carefully.
        """

        result = chunker.chunk(text)

        # Should create ~3 chunks (history, product, legal)
        assert 2 <= len(result.chunks) <= 4

        # First chunk should contain history words
        assert any(word in result.chunks[0].lower()
                   for word in ["history", "founded", "past"])

        # One chunk should contain product words
        product_chunk = [c for c in result.chunks
                         if any(w in c.lower() for w in ["product", "software", "app"])]
        assert len(product_chunk) >= 1

        # One chunk should contain legal words
        legal_chunk = [c for c in result.chunks
                       if any(w in c.lower() for w in ["legal", "rights", "terms"])]
        assert len(legal_chunk) >= 1

    def test_chunk_coherent_text(self, mock_embedding_function):
        """Test chunking semantically coherent text."""
        chunker = ClusterSemanticChunker(
            min_chunk_size=15,
            max_chunk_size=80,
            embedding_function=mock_embedding_function
        )

        # All about history - should stay together
        text = """
        The company history began in 1995. Our past achievements are remarkable.
        Ancient wisdom guides our decisions. The historical context matters.
        Founded on strong principles, we grew steadily. Past experiences shaped us.
        """

        result = chunker.chunk(text)

        # Should create fewer chunks since all text is coherent
        # (Might be 1-2 chunks depending on token limits)
        assert 1 <= len(result.chunks) <= 2

    def test_metadata_accuracy(self, mock_embedding_function):
        """Test that metadata is accurate."""
        chunker = ClusterSemanticChunker(
            min_chunk_size=20,
            max_chunk_size=100,
            embedding_function=mock_embedding_function
        )

        text = "First sentence. " * 50  # Repeating text

        result = chunker.chunk(text)

        # Check metadata
        assert result.metadata["segments"] > 0
        assert result.metadata["chunks"] > 0
        assert result.metadata["chunks"] <= result.metadata["segments"]
        assert result.metadata["avg_chunk_size"] > 0
        assert result.metadata["algorithm"] == "cluster_semantic"


class TestClusterSemanticChunkerEdgeCases:
    """Edge case tests."""

    def test_very_long_text(self):
        """Test handling of very long text."""
        chunker = ClusterSemanticChunker(
            min_chunk_size=50,
            max_chunk_size=200
        )

        # Generate long text
        text = ". ".join([f"Sentence number {i}" for i in range(500)])

        result = chunker.chunk(text)

        # Should handle without crashing
        assert len(result.chunks) > 0

        # All chunks should respect max size (with some tolerance)
        for chunk in result.chunks:
            token_count = len(chunker.tokenizer.encode(chunk))
            assert token_count <= chunker.max_chunk_size * 1.2  # 20% tolerance

    def test_unicode_text(self):
        """Test handling of unicode characters."""
        chunker = ClusterSemanticChunker(min_chunk_size=10)

        text = "Hello 世界! Émojis 🎉 are fun. Über cool."

        result = chunker.chunk(text)

        # Should handle unicode without crashing
        assert len(result.chunks) > 0
        assert all(isinstance(c, str) for c in result.chunks)

    def test_text_with_special_characters(self):
        """Test text with special punctuation."""
        chunker = ClusterSemanticChunker(min_chunk_size=10)

        text = """
        Question? Answer! Exclamation...
        (Parentheses) [brackets] {braces}
        Dash—dash – hyphen-hyphen.
        Quote "test" 'test' end.
        """

        result = chunker.chunk(text)

        assert len(result.chunks) > 0

    def test_chunk_size_boundaries(self):
        """Test behavior at chunk size boundaries."""
        # min_chunk_size = max_chunk_size (edge case)
        chunker = ClusterSemanticChunker(
            min_chunk_size=50,
            max_chunk_size=50
        )

        assert chunker.max_cluster == 1  # Only 1 segment per chunk

        text = "Sentence. " * 100
        result = chunker.chunk(text)

        # Should create many single-segment chunks
        assert result.metadata["chunks"] == result.metadata["segments"]


class TestClusterSemanticChunkerPerformance:
    """Performance and benchmark tests."""

    def test_performance_medium_text(self, mock_embedding_function):
        """Test performance on medium-sized text (~1000 tokens)."""
        import time

        chunker = ClusterSemanticChunker(
            min_chunk_size=50,
            max_chunk_size=400,
            embedding_function=mock_embedding_function
        )

        # Generate ~1000 token text
        text = ". ".join([f"This is sentence number {i} with some content" for i in range(100)])

        start = time.time()
        result = chunker.chunk(text)
        duration = time.time() - start

        # Should complete reasonably fast (< 5 seconds for medium text)
        assert duration < 5.0

        assert len(result.chunks) > 0

    def test_similarity_matrix_efficiency(self):
        """Test that similarity matrix computation is efficient."""
        import time

        chunker = ClusterSemanticChunker()

        # Create 100 random embeddings
        embeddings = np.random.rand(100, 1536).astype(np.float32)

        start = time.time()
        similarity = chunker._build_similarity_matrix(embeddings)
        duration = time.time() - start

        # Should be fast (< 1 second for 100 embeddings)
        assert duration < 1.0

        assert similarity.shape == (100, 100)

    @pytest.mark.slow
    def test_performance_large_text(self, mock_embedding_function):
        """Test performance on large text (~5000 tokens)."""
        import time

        chunker = ClusterSemanticChunker(
            min_chunk_size=50,
            max_chunk_size=400,
            embedding_function=mock_embedding_function
        )

        # Generate ~5000 token text
        text = ". ".join([f"This is a longer sentence number {i} with more content to test" for i in range(500)])

        start = time.time()
        result = chunker.chunk(text)
        duration = time.time() - start

        # Should complete in reasonable time (< 30 seconds)
        assert duration < 30.0

        assert len(result.chunks) > 0
        print(f"Large text chunked in {duration:.2f}s into {len(result.chunks)} chunks")


class TestClusterSemanticChunkerComparison:
    """Compare ClusterSemanticChunker with baseline methods."""

    def test_vs_fixed_size_chunking(self, mock_embedding_function):
        """Compare output with fixed-size chunking."""
        # Text with clear topic shift in the middle
        text = """
        History paragraph one. Past events shaped us. Ancient traditions guide us.
        Founded long ago we started small. Historical records show our growth.

        Product features include speed. Software capabilities are extensive.
        The app provides real-time updates. Modern tools help developers.
        """

        # Semantic chunking
        semantic_chunker = ClusterSemanticChunker(
            min_chunk_size=20,
            max_chunk_size=100,
            embedding_function=mock_embedding_function
        )
        semantic_result = semantic_chunker.chunk(text)

        # Fixed-size chunking (simple baseline)
        tokens = semantic_chunker.tokenizer.encode(text)
        chunk_size = 50
        fixed_chunks = []
        for i in range(0, len(tokens), chunk_size):
            chunk_tokens = tokens[i:i+chunk_size]
            fixed_chunks.append(semantic_chunker.tokenizer.decode(chunk_tokens))

        # Semantic chunking should create fewer, more coherent chunks
        # (This is a qualitative test - actual behavior depends on text)
        print(f"Semantic chunks: {len(semantic_result.chunks)}")
        print(f"Fixed chunks: {len(fixed_chunks)}")

        assert len(semantic_result.chunks) > 0
        assert len(fixed_chunks) > 0


@pytest.mark.integration
class TestClusterSemanticChunkerRealEmbeddings:
    """Integration tests with real embedding service (requires API key)."""

    @pytest.fixture
    def real_embedding_function(self):
        """Get real embedding function from EmbeddingService."""
        try:
            from writeros.utils.embeddings import embedding_service
            return embedding_service.embed_query
        except Exception as e:
            pytest.skip(f"EmbeddingService not available: {e}")

    def test_chunk_real_document(self, real_embedding_function):
        """Test chunking a real document with actual embeddings."""
        chunker = ClusterSemanticChunker(
            min_chunk_size=50,
            max_chunk_size=400,
            embedding_function=real_embedding_function
        )

        # Real document with topic shifts
        text = """
        The Byzantine Empire, also referred to as the Eastern Roman Empire,
        was the continuation of the Roman Empire in its eastern provinces.
        It survived the fragmentation of the Western Roman Empire in the 5th century.
        Constantinople was the capital and it lasted for over a thousand years.

        Modern software development practices emphasize continuous integration and deployment.
        DevOps tools enable teams to ship code faster and more reliably.
        Cloud infrastructure provides scalability and flexibility for applications.
        Microservices architecture allows independent development of system components.

        Climate change poses significant challenges for the 21st century.
        Rising global temperatures affect weather patterns worldwide.
        Renewable energy sources offer solutions to reduce carbon emissions.
        International cooperation is essential for environmental protection.
        """

        result = chunker.chunk(text)

        # Should create separate chunks for different topics
        assert 2 <= len(result.chunks) <= 5

        # Verify chunks are coherent
        for i, chunk in enumerate(result.chunks):
            print(f"\n--- Chunk {i+1} ---")
            print(chunk[:100] + "...")

        assert all(len(c) > 0 for c in result.chunks)
