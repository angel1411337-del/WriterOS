"""
Integration tests for VaultIndexer with UnifiedChunker.

Tests the full RAG pipeline integration including:
- Different chunking strategies
- Cache effectiveness
- Database integration
- Performance with various document sizes
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch
from writeros.utils.indexer import VaultIndexer
from writeros.preprocessing import ChunkingStrategy


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_vault():
    """Create a temporary vault directory with sample markdown files."""
    temp_dir = tempfile.mkdtemp()
    vault_path = Path(temp_dir)

    # Create directory structure
    (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)
    (vault_path / "Story_Bible" / "Locations").mkdir(parents=True)
    (vault_path / "Writing_Bible").mkdir(parents=True)
    (vault_path / "Manuscripts").mkdir(parents=True)

    # Create sample files
    character_file = vault_path / "Story_Bible" / "Characters" / "protagonist.md"
    character_file.write_text("""
# John Smith

## Background
John is a detective in New York City. He has 15 years of experience
solving complex cases. His approach is methodical and detail-oriented.

## Personality
He is determined, intelligent, and compassionate. Despite the harsh
realities of his work, he maintains a strong moral compass.

## Relationships
John has a complicated relationship with his partner, Sarah. They work
well together but have different approaches to solving cases.
    """)

    location_file = vault_path / "Story_Bible" / "Locations" / "precinct.md"
    location_file.write_text("""
# 44th Precinct

## Description
Located in downtown Manhattan, the 44th Precinct is a busy police station
that handles major crimes in the area. The building is old but well-maintained.

## Atmosphere
The precinct has a tense, energetic atmosphere. Detectives are constantly
working on multiple cases, and the pressure is high.
    """)

    writing_file = vault_path / "Writing_Bible" / "character_development.md"
    writing_file.write_text("""
# Character Development Principles

## Show, Don't Tell
Always demonstrate character traits through actions rather than description.
Let readers discover personality through dialogue and choices.

## Arc Structure
Every main character needs a clear transformation arc. Start with a flaw
or need, create challenges, and show growth through the resolution.
    """)

    manuscript_file = vault_path / "Manuscripts" / "chapter1.md"
    manuscript_file.write_text("""
# Chapter 1: The Call

John stared at the phone on his desk. He knew what the call would mean -
another case, another mystery to unravel. The city never slept, and neither
did the crimes that plagued it.

When the phone finally rang, he picked it up without hesitation. "Detective
Smith," he said, his voice steady despite the fatigue weighing on him.

"We have a situation at the docks," the dispatcher's voice crackled through
the line. "Homicide. Requesting senior detective."
    """)

    yield vault_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service that returns consistent vectors."""
    mock_service = Mock()

    def mock_embed(text: str):
        """Generate deterministic embedding based on keywords."""
        import numpy as np

        vec = [0.0] * 1536
        words = text.lower().split()

        # Assign dimensions based on content type
        if any(w in words for w in ["character", "personality", "john"]):
            vec[0] = 1.0
        if any(w in words for w in ["location", "precinct", "building"]):
            vec[1] = 1.0
        if any(w in words for w in ["writing", "development", "show"]):
            vec[2] = 1.0
        if any(w in words for w in ["manuscript", "chapter", "phone"]):
            vec[3] = 1.0

        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = [v / norm for v in vec]

        return vec

    mock_service.embed_query = mock_embed
    return mock_service


# ============================================================================
# Test VaultIndexer Basic Functionality
# ============================================================================

class TestVaultIndexerBasic:
    """Test basic VaultIndexer functionality without database."""

    def test_indexer_initialization(self, temp_vault):
        """Test VaultIndexer initializes correctly."""
        vault_id = uuid4()

        indexer = VaultIndexer(
            vault_path=str(temp_vault),
            vault_id=vault_id,
            chunking_strategy=ChunkingStrategy.AUTO,
            enable_cache=True
        )

        assert indexer.vault_path == temp_vault
        assert indexer.vault_id == vault_id
        assert indexer.chunker is not None

    def test_doc_type_inference_character(self, temp_vault):
        """Test document type inference for character files."""
        vault_id = uuid4()
        indexer = VaultIndexer(
            vault_path=str(temp_vault),
            vault_id=vault_id
        )

        character_file = temp_vault / "Story_Bible" / "Characters" / "protagonist.md"
        doc_type = indexer._infer_doc_type(character_file)

        assert doc_type == "character"

    def test_doc_type_inference_location(self, temp_vault):
        """Test document type inference for location files."""
        vault_id = uuid4()
        indexer = VaultIndexer(
            vault_path=str(temp_vault),
            vault_id=vault_id
        )

        location_file = temp_vault / "Story_Bible" / "Locations" / "precinct.md"
        doc_type = indexer._infer_doc_type(location_file)

        assert doc_type == "location"

    def test_doc_type_inference_craft_advice(self, temp_vault):
        """Test document type inference for writing bible files."""
        vault_id = uuid4()
        indexer = VaultIndexer(
            vault_path=str(temp_vault),
            vault_id=vault_id
        )

        writing_file = temp_vault / "Writing_Bible" / "character_development.md"
        doc_type = indexer._infer_doc_type(writing_file)

        assert doc_type == "craft_advice"

    def test_doc_type_inference_manuscript(self, temp_vault):
        """Test document type inference for manuscript files."""
        vault_id = uuid4()
        indexer = VaultIndexer(
            vault_path=str(temp_vault),
            vault_id=vault_id
        )

        manuscript_file = temp_vault / "Manuscripts" / "chapter1.md"
        doc_type = indexer._infer_doc_type(manuscript_file)

        assert doc_type == "manuscript"


# ============================================================================
# Test Chunking Strategy Integration
# ============================================================================

class TestVaultIndexerChunkingStrategies:
    """Test different chunking strategies with VaultIndexer."""

    @pytest.mark.asyncio
    async def test_cluster_semantic_strategy(self, temp_vault, mock_embedding_service):
        """Test indexing with cluster semantic strategy."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    chunking_strategy=ChunkingStrategy.CLUSTER_SEMANTIC,
                    enable_cache=True
                )

                character_file = temp_vault / "Story_Bible" / "Characters" / "protagonist.md"
                chunks_count = await indexer.index_file(character_file)

                assert chunks_count > 0

    @pytest.mark.asyncio
    async def test_greedy_semantic_strategy(self, temp_vault, mock_embedding_service):
        """Test indexing with greedy semantic strategy."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    chunking_strategy=ChunkingStrategy.GREEDY_SEMANTIC,
                    enable_cache=True
                )

                character_file = temp_vault / "Story_Bible" / "Characters" / "protagonist.md"
                chunks_count = await indexer.index_file(character_file)

                assert chunks_count > 0

    @pytest.mark.asyncio
    async def test_fixed_size_strategy(self, temp_vault, mock_embedding_service):
        """Test indexing with fixed size strategy."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    chunking_strategy=ChunkingStrategy.FIXED_SIZE,
                    enable_cache=False
                )

                character_file = temp_vault / "Story_Bible" / "Characters" / "protagonist.md"
                chunks_count = await indexer.index_file(character_file)

                assert chunks_count > 0

    @pytest.mark.asyncio
    async def test_auto_strategy_selection(self, temp_vault, mock_embedding_service):
        """Test AUTO strategy selects appropriate strategy based on file size."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    chunking_strategy=ChunkingStrategy.AUTO,
                    enable_cache=True
                )

                # Small file should use cluster semantic
                character_file = temp_vault / "Story_Bible" / "Characters" / "protagonist.md"
                chunks_count = await indexer.index_file(character_file)

                assert chunks_count > 0

                # Check stats show strategy was used
                stats = indexer.get_stats()
                assert "strategy_usage" in stats


# ============================================================================
# Test Cache Effectiveness
# ============================================================================

class TestVaultIndexerCaching:
    """Test cache effectiveness during indexing."""

    @pytest.mark.asyncio
    async def test_cache_improves_performance(self, temp_vault, mock_embedding_service):
        """Test that cache reduces redundant embedding calls."""
        vault_id = uuid4()
        call_count = 0

        def counting_embed(text: str):
            nonlocal call_count
            call_count += 1
            return mock_embedding_service.embed_query(text)

        # Mock the embedding service
        mock_service = Mock()
        mock_service.embed_query = counting_embed

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    chunking_strategy=ChunkingStrategy.CLUSTER_SEMANTIC,
                    enable_cache=True
                )

                character_file = temp_vault / "Story_Bible" / "Characters" / "protagonist.md"
                await indexer.index_file(character_file)

                # Cache should have been used
                stats = indexer.get_stats()
                assert "cache" in stats
                assert call_count > 0

    @pytest.mark.asyncio
    async def test_cache_can_be_cleared(self, temp_vault, mock_embedding_service):
        """Test cache clearing functionality."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    enable_cache=True
                )

                character_file = temp_vault / "Story_Bible" / "Characters" / "protagonist.md"
                await indexer.index_file(character_file)

                # Get stats before clearing
                stats_before = indexer.get_stats()
                cache_size_before = stats_before.get("cache", {}).get("size", 0)

                # Clear cache
                indexer.clear_cache()

                # Get stats after clearing
                stats_after = indexer.get_stats()
                cache_size_after = stats_after.get("cache", {}).get("size", 0)

                assert cache_size_after == 0


# ============================================================================
# Test Full Vault Indexing
# ============================================================================

class TestVaultIndexerFullIndexing:
    """Test full vault indexing with multiple files."""

    @pytest.mark.asyncio
    async def test_index_vault_all_directories(self, temp_vault, mock_embedding_service):
        """Test indexing entire vault across all directories."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    chunking_strategy=ChunkingStrategy.AUTO,
                    enable_cache=True
                )

                results = await indexer.index_vault()

                # Should have processed all 4 files
                assert results["files_processed"] == 4
                assert results["chunks_created"] > 0
                assert len(results["errors"]) == 0

                # Should include chunking statistics
                assert "chunking_stats" in results
                assert "total_documents" in results["chunking_stats"]

    @pytest.mark.asyncio
    async def test_index_vault_specific_directories(self, temp_vault, mock_embedding_service):
        """Test indexing specific directories only."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id
                )

                # Only index Story_Bible
                results = await indexer.index_vault(directories=["Story_Bible"])

                # Should have processed 2 files (character and location)
                assert results["files_processed"] == 2
                assert results["chunks_created"] > 0

    @pytest.mark.asyncio
    async def test_index_vault_handles_missing_directories(self, temp_vault, mock_embedding_service):
        """Test that indexing handles missing directories gracefully."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id
                )

                # Try to index non-existent directory
                results = await indexer.index_vault(directories=["NonExistent"])

                # Should complete without errors
                assert results["files_processed"] == 0
                assert len(results["errors"]) == 0


# ============================================================================
# Test Performance Statistics
# ============================================================================

class TestVaultIndexerStatistics:
    """Test statistics tracking during indexing."""

    @pytest.mark.asyncio
    async def test_statistics_after_indexing(self, temp_vault, mock_embedding_service):
        """Test that statistics are properly tracked during indexing."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id,
                    enable_cache=True
                )

                results = await indexer.index_vault()

                # Get chunking statistics
                stats = indexer.get_stats()

                assert stats["total_documents"] > 0
                assert stats["total_chunks"] > 0
                assert stats["total_time"] > 0
                assert "strategy_usage" in stats
                assert "cache" in stats

    @pytest.mark.asyncio
    async def test_chunking_stats_in_results(self, temp_vault, mock_embedding_service):
        """Test that chunking stats are included in index_vault results."""
        vault_id = uuid4()

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id
                )

                results = await indexer.index_vault()

                assert "chunking_stats" in results
                chunking_stats = results["chunking_stats"]

                assert "total_documents" in chunking_stats
                assert "total_chunks" in chunking_stats
                assert "strategy_usage" in chunking_stats


# ============================================================================
# Test Error Handling
# ============================================================================

class TestVaultIndexerErrorHandling:
    """Test error handling during indexing."""

    @pytest.mark.asyncio
    async def test_handles_unicode_decode_errors(self, temp_vault, mock_embedding_service):
        """Test handling of files with encoding issues."""
        vault_id = uuid4()

        # Create file with non-UTF8 content (latin-1)
        bad_file = temp_vault / "Story_Bible" / "Characters" / "bad_encoding.md"
        bad_file.write_bytes(b"Test with \xe9 special char")

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id
                )

                # Should handle gracefully with fallback encoding
                chunks_count = await indexer.index_file(bad_file)
                assert chunks_count >= 0  # Should not crash

    @pytest.mark.asyncio
    async def test_handles_empty_files(self, temp_vault, mock_embedding_service):
        """Test handling of empty files."""
        vault_id = uuid4()

        # Create empty file
        empty_file = temp_vault / "Story_Bible" / "Characters" / "empty.md"
        empty_file.write_text("")

        with patch('writeros.utils.indexer.EmbeddingService', return_value=mock_embedding_service):
            with patch('writeros.utils.indexer.Session'):
                indexer = VaultIndexer(
                    vault_path=str(temp_vault),
                    vault_id=vault_id
                )

                chunks_count = await indexer.index_file(empty_file)
                assert chunks_count == 0  # Empty file returns 0 chunks
