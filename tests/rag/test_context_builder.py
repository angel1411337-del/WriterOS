"""
Unit tests for entity context builder.

Design Decision:
Tests organized by class with Given-When-Then structure for clarity.

Reasoning:
- Clear test organization mirrors production code structure
- Given-When-Then makes test intent immediately obvious
- Each test class focuses on one component (single responsibility)
"""
import pytest
from uuid import uuid4, UUID
from datetime import datetime
from sqlmodel import Session

from writeros.schema import Entity, Chunk, Relationship, EntityType
from writeros.rag.context_builder import (
    EntityContextBuilder,
    ContextBuildResult,
    UsageBasedPriority,
    RecencyBasedPriority,
    NarrativeSequencePriority
)


# ============================================================================
# PRIORITY STRATEGY TESTS
# ============================================================================

class TestUsageBasedPriority:
    """
    Test suite for UsageBasedPriority strategy.

    Design Decision:
    Test sorting behavior with different usage patterns.

    Reasoning:
    Sorting is the core functionality, so we test various scenarios:
    - Different usage counts (normal case)
    - Same usage counts (tie-breaking)
    - Zero usage counts (edge case)
    """

    def test_prioritize_chunks_by_usage_count_descending(self):
        """
        Test that chunks are sorted by usage_count in descending order.

        GIVEN: A list of chunks with different usage counts
        WHEN: Prioritizing chunks using UsageBasedPriority
        THEN: Chunks are sorted with highest usage_count first
        """
        # GIVEN: Chunks with different usage counts
        chunks = [
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Low usage",
                content_hash="hash1",
                file_path="/test1.md",
                file_hash="fhash1",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=5,  # Low
                indexed_at=datetime.utcnow()
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="High usage",
                content_hash="hash2",
                file_path="/test2.md",
                file_hash="fhash2",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=50,  # High
                indexed_at=datetime.utcnow()
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Medium usage",
                content_hash="hash3",
                file_path="/test3.md",
                file_hash="fhash3",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=20,  # Medium
                indexed_at=datetime.utcnow()
            ),
        ]

        # WHEN: Prioritizing chunks
        strategy = UsageBasedPriority()
        prioritized = strategy.prioritize_chunks(chunks, uuid4())

        # THEN: Chunks are sorted by usage_count (descending)
        assert prioritized[0].usage_count == 50
        assert prioritized[1].usage_count == 20
        assert prioritized[2].usage_count == 5

    def test_prioritize_chunks_with_zero_usage(self):
        """
        Test that chunks with zero usage are handled correctly.

        GIVEN: Chunks with zero and non-zero usage counts
        WHEN: Prioritizing chunks
        THEN: Non-zero usage chunks come first
        """
        # GIVEN
        chunks = [
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Never used",
                content_hash="hash1",
                file_path="/test1.md",
                file_hash="fhash1",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,  # Zero
                indexed_at=datetime.utcnow()
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Used once",
                content_hash="hash2",
                file_path="/test2.md",
                file_hash="fhash2",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=1,  # Non-zero
                indexed_at=datetime.utcnow()
            ),
        ]

        # WHEN
        strategy = UsageBasedPriority()
        prioritized = strategy.prioritize_chunks(chunks, uuid4())

        # THEN
        assert prioritized[0].usage_count == 1
        assert prioritized[1].usage_count == 0


class TestRecencyBasedPriority:
    """Test suite for RecencyBasedPriority strategy."""

    def test_prioritize_chunks_by_recency_descending(self):
        """
        Test that chunks are sorted by indexed_at in descending order.

        GIVEN: Chunks indexed at different times
        WHEN: Prioritizing chunks using RecencyBasedPriority
        THEN: Most recently indexed chunks come first
        """
        # GIVEN
        old_time = datetime(2025, 1, 1, 12, 0, 0)
        medium_time = datetime(2025, 6, 1, 12, 0, 0)
        recent_time = datetime(2025, 11, 28, 12, 0, 0)

        chunks = [
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Old chunk",
                content_hash="hash1",
                file_path="/test1.md",
                file_hash="fhash1",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=old_time
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Recent chunk",
                content_hash="hash2",
                file_path="/test2.md",
                file_hash="fhash2",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=recent_time
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Medium chunk",
                content_hash="hash3",
                file_path="/test3.md",
                file_hash="fhash3",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=medium_time
            ),
        ]

        # WHEN
        strategy = RecencyBasedPriority()
        prioritized = strategy.prioritize_chunks(chunks, uuid4())

        # THEN: Most recent first
        assert prioritized[0].indexed_at == recent_time
        assert prioritized[1].indexed_at == medium_time
        assert prioritized[2].indexed_at == old_time


class TestNarrativeSequencePriority:
    """Test suite for NarrativeSequencePriority strategy."""

    def test_prioritize_chunks_by_narrative_sequence_ascending(self):
        """
        Test that chunks are sorted by narrative_sequence in ascending order.

        GIVEN: Chunks with different narrative sequences
        WHEN: Prioritizing chunks using NarrativeSequencePriority
        THEN: Earlier chapters come first
        """
        # GIVEN
        chunks = [
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Chapter 10",
                content_hash="hash1",
                file_path="/test1.md",
                file_hash="fhash1",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=datetime.utcnow(),
                narrative_sequence=10
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Chapter 1",
                content_hash="hash2",
                file_path="/test2.md",
                file_hash="fhash2",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=datetime.utcnow(),
                narrative_sequence=1
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Chapter 5",
                content_hash="hash3",
                file_path="/test3.md",
                file_hash="fhash3",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=datetime.utcnow(),
                narrative_sequence=5
            ),
        ]

        # WHEN
        strategy = NarrativeSequencePriority()
        prioritized = strategy.prioritize_chunks(chunks, uuid4())

        # THEN: Chronological order
        assert prioritized[0].narrative_sequence == 1
        assert prioritized[1].narrative_sequence == 5
        assert prioritized[2].narrative_sequence == 10

    def test_prioritize_chunks_without_sequence_last(self):
        """
        Test that chunks without narrative_sequence are placed last.

        GIVEN: Mix of sequenced and non-sequenced chunks
        WHEN: Prioritizing chunks
        THEN: Sequenced chunks come first, non-sequenced last
        """
        # GIVEN
        chunks = [
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="No sequence",
                content_hash="hash1",
                file_path="/test1.md",
                file_hash="fhash1",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=datetime.utcnow(),
                narrative_sequence=None
            ),
            Chunk(
                id=uuid4(),
                vault_id=uuid4(),
                content="Chapter 1",
                content_hash="hash2",
                file_path="/test2.md",
                file_hash="fhash2",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=10,
                usage_count=0,
                indexed_at=datetime.utcnow(),
                narrative_sequence=1
            ),
        ]

        # WHEN
        strategy = NarrativeSequencePriority()
        prioritized = strategy.prioritize_chunks(chunks, uuid4())

        # THEN: Sequenced chunk first
        assert prioritized[0].narrative_sequence == 1
        assert prioritized[1].narrative_sequence is None


# ============================================================================
# CONTEXT BUILDER TESTS
# ============================================================================

class TestEntityContextBuilder:
    """Test suite for EntityContextBuilder class."""

    def test_initialization_with_default_strategy(self):
        """
        Test that builder initializes with default UsageBasedPriority.

        GIVEN: No priority strategy specified
        WHEN: Creating EntityContextBuilder
        THEN: UsageBasedPriority is used by default
        """
        # GIVEN / WHEN
        builder = EntityContextBuilder(max_tokens=4000)

        # THEN
        assert isinstance(builder.priority_strategy, UsageBasedPriority)
        assert builder.max_tokens == 4000

    def test_initialization_with_custom_strategy(self):
        """
        Test that builder accepts custom priority strategy.

        GIVEN: Custom priority strategy
        WHEN: Creating EntityContextBuilder with strategy
        THEN: Custom strategy is used
        """
        # GIVEN
        custom_strategy = RecencyBasedPriority()

        # WHEN
        builder = EntityContextBuilder(
            max_tokens=4000,
            priority_strategy=custom_strategy
        )

        # THEN
        assert builder.priority_strategy is custom_strategy

    def test_initialization_rejects_negative_max_tokens(self):
        """
        Test that builder rejects negative max_tokens.

        GIVEN: Negative max_tokens value
        WHEN: Creating EntityContextBuilder
        THEN: ValueError is raised
        """
        # GIVEN / WHEN / THEN
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            EntityContextBuilder(max_tokens=-100)

    def test_initialization_rejects_zero_max_tokens(self):
        """
        Test that builder rejects zero max_tokens.

        GIVEN: Zero max_tokens value
        WHEN: Creating EntityContextBuilder
        THEN: ValueError is raised
        """
        # GIVEN / WHEN / THEN
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            EntityContextBuilder(max_tokens=0)

    @pytest.mark.asyncio
    async def test_build_context_with_only_primary_source(
        self,
        db_session,
        db_vault
    ):
        """
        Test building context for entity with only primary source chunk.

        GIVEN: Entity with primary source chunk but no relationships or attributes
        WHEN: Building context
        THEN: Only primary source chunk is included

        Design Decision:
        Use db_vault fixture instead of sample_vault_id to ensure Vault exists.

        Reasoning:
        Chunks and Entities have foreign key constraints to vaults table.
        Without a real Vault record, database insertion fails.
        """
        # GIVEN: Create entity with primary source
        entity = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Test Entity",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536
        )

        primary_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Primary source content",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=50,
            usage_count=10,
            indexed_at=datetime.utcnow()
        )

        entity.primary_source_chunk_id = primary_chunk.id

        db_session.add(entity)
        db_session.add(primary_chunk)
        db_session.commit()

        # WHEN: Building context
        builder = EntityContextBuilder(max_tokens=1000, session=db_session)
        result = await builder.build_context(entity.id, db_vault.id)

        # THEN: Only primary source included
        assert len(result.chunks) == 1
        assert result.chunks[0].id == primary_chunk.id
        assert result.total_tokens == 50
        assert result.chunks_by_source["primary_source"] == 1
        assert result.budget_utilized == 0.05  # 50/1000

    @pytest.mark.asyncio
    async def test_build_context_respects_token_budget(
        self,
        db_session,
        db_vault
    ):
        """
        Test that context builder respects token budget.

        GIVEN: Entity with multiple chunks exceeding token budget
        WHEN: Building context with limited budget
        THEN: Chunks are added until budget is exhausted

        Design Decision:
        Use db_vault fixture to ensure foreign key constraints are satisfied.

        Reasoning:
        Same as test_build_context_with_only_primary_source - need real Vault.
        """
        # GIVEN: Entity with primary source
        entity = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Test Entity",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536,
            mention_chunk_ids=[]
        )

        # Primary chunk (500 tokens)
        primary_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Primary source",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=500,
            usage_count=10,
            indexed_at=datetime.utcnow()
        )

        entity.primary_source_chunk_id = primary_chunk.id

        # Mention chunks (400 tokens each)
        mention_chunks = []
        for i in range(3):
            chunk = Chunk(
                id=uuid4(),
                vault_id=db_vault.id,
                content=f"Mention chunk {i}",
                content_hash=f"hash{i+2}",
                file_path=f"/test{i}.md",
                file_hash=f"fhash{i+2}",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=400,
                usage_count=10 - i,  # Descending usage
                indexed_at=datetime.utcnow()
            )
            mention_chunks.append(chunk)
            entity.mention_chunk_ids.append(str(chunk.id))

        db_session.add(entity)
        db_session.add(primary_chunk)
        for chunk in mention_chunks:
            db_session.add(chunk)
        db_session.commit()

        # WHEN: Building context with 1000 token budget
        # Expected: Primary (500) + 1 mention (400) = 900 tokens
        builder = EntityContextBuilder(max_tokens=1000, session=db_session)
        result = await builder.build_context(entity.id, db_vault.id)

        # THEN: Budget is respected
        assert result.total_tokens <= 1000
        assert result.total_tokens == 900  # Primary + 1 mention
        assert len(result.chunks) == 2


# ============================================================================
# CONTEXT BUILD RESULT TESTS
# ============================================================================

class TestContextBuildResult:
    """Test suite for ContextBuildResult data class."""

    def test_result_initialization_with_defaults(self):
        """
        Test that ContextBuildResult initializes with default values.

        GIVEN: Minimal initialization parameters
        WHEN: Creating ContextBuildResult
        THEN: Default values are populated
        """
        # GIVEN / WHEN
        chunks = []
        result = ContextBuildResult(chunks=chunks, total_tokens=0)

        # THEN
        assert result.chunks == []
        assert result.total_tokens == 0
        assert result.chunks_by_source == {
            "primary_source": 0,
            "relationship_sources": 0,
            "mention_chunks": 0
        }
        assert result.budget_utilized == 0.0

    def test_result_initialization_with_custom_values(self):
        """
        Test that ContextBuildResult accepts custom values.

        GIVEN: Custom initialization parameters
        WHEN: Creating ContextBuildResult
        THEN: Custom values are stored
        """
        # GIVEN
        chunks = [Chunk(
            id=uuid4(),
            vault_id=uuid4(),
            content="Test",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=0,
            indexed_at=datetime.utcnow()
        )]

        chunks_by_source = {
            "primary_source": 1,
            "relationship_sources": 0,
            "mention_chunks": 0
        }

        # WHEN
        result = ContextBuildResult(
            chunks=chunks,
            total_tokens=100,
            chunks_by_source=chunks_by_source,
            budget_utilized=0.5
        )

        # THEN
        assert len(result.chunks) == 1
        assert result.total_tokens == 100
        assert result.chunks_by_source["primary_source"] == 1
        assert result.budget_utilized == 0.5
