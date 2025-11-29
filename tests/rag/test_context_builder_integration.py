"""
Integration tests for EntityContextBuilder with RAG retrieval pipeline.

Design Decision:
Tests the full integration of context builder with the existing RAG system.

Reasoning:
- Unit tests validate individual components in isolation
- Integration tests validate end-to-end workflows with real database
- Ensures context builder works correctly with actual vault data
"""
import pytest
from uuid import uuid4, UUID
from datetime import datetime
from sqlmodel import Session

from writeros.schema import Entity, Chunk, Relationship, EntityType, RelationType, Vault, ConnectionType
from writeros.rag.retriever import RAGRetriever
from writeros.rag.context_builder import (
    EntityContextBuilder,
    UsageBasedPriority,
    RecencyBasedPriority,
    NarrativeSequencePriority
)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestRAGRetrieverIntegration:
    """
    Test suite for RAGRetriever.retrieve_entity_context() integration.

    Design Decision:
    Test the integration point between RAGRetriever and EntityContextBuilder.

    Reasoning:
    Validates that the retriever correctly delegates to context builder
    and returns properly formatted results.
    """

    @pytest.mark.asyncio
    async def test_retrieve_entity_context_basic(
        self,
        db_session,
        db_vault
    ):
        """
        Test basic entity context retrieval through RAGRetriever.

        GIVEN: Entity with primary source and mention chunks
        WHEN: Calling retrieve_entity_context() on RAGRetriever
        THEN: Returns properly formatted context with all expected fields
        """
        # GIVEN: Create entity with chunks
        entity = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Jon Snow",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536,
            mention_chunk_ids=[]
        )

        primary_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Jon Snow is Ned Stark's bastard son",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=200,
            usage_count=15,
            indexed_at=datetime.utcnow()
        )

        mention_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Jon Snow took the black and joined the Night's Watch",
            content_hash="hash2",
            file_path="/test2.md",
            file_hash="fhash2",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=150,
            usage_count=10,
            indexed_at=datetime.utcnow()
        )

        entity.primary_source_chunk_id = primary_chunk.id
        entity.mention_chunk_ids.append(str(mention_chunk.id))

        db_session.add(entity)
        db_session.add(primary_chunk)
        db_session.add(mention_chunk)
        db_session.commit()

        # WHEN: Retrieve entity context
        retriever = RAGRetriever()
        context = await retriever.retrieve_entity_context(
            entity_id=entity.id,
            vault_id=db_vault.id,
            max_tokens=1000,
            session=db_session  # Inject session for test
        )

        # THEN: Validate response structure
        assert "chunks" in context
        assert "total_tokens" in context
        assert "chunks_by_source" in context
        assert "budget_utilized" in context
        assert "entity" in context

        # Validate content
        assert len(context["chunks"]) == 2
        assert context["total_tokens"] == 350  # 200 + 150
        assert context["chunks_by_source"]["primary_source"] == 1
        assert context["chunks_by_source"]["mention_chunks"] == 1  # Fixed key
        assert context["budget_utilized"] == 0.35  # 350 / 1000
        assert context["entity"].id == entity.id

    @pytest.mark.asyncio
    async def test_retrieve_entity_context_with_custom_strategy(
        self,
        db_session,
        db_vault
    ):
        """
        Test entity context retrieval with custom priority strategy.

        GIVEN: Entity with multiple mention chunks
        WHEN: Using RecencyBasedPriority strategy
        THEN: Most recent chunks are prioritized
        """
        # GIVEN: Create entity with multiple mention chunks
        entity = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Arya Stark",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536,
            mention_chunk_ids=[]
        )

        # Older chunk
        old_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Arya was young when she left Winterfell",
            content_hash="hash1",
            file_path="/test1.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=20,
            indexed_at=datetime(2024, 1, 1)  # Old
        )

        # Recent chunk
        recent_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Arya trained with the Faceless Men",
            content_hash="hash2",
            file_path="/test2.md",
            file_hash="fhash2",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=5,  # Lower usage, but more recent
            indexed_at=datetime(2025, 1, 1)  # Recent
        )

        entity.mention_chunk_ids = [str(old_chunk.id), str(recent_chunk.id)]

        db_session.add(entity)
        db_session.add(old_chunk)
        db_session.add(recent_chunk)
        db_session.commit()

        # WHEN: Retrieve with RecencyBasedPriority
        retriever = RAGRetriever()
        context = await retriever.retrieve_entity_context(
            entity_id=entity.id,
            vault_id=db_vault.id,
            max_tokens=150,  # Budget for only one chunk
            priority_strategy=RecencyBasedPriority(),
            session=db_session  # Inject session for test
        )

        # THEN: Recent chunk is selected despite lower usage
        assert len(context["chunks"]) == 1
        assert context["chunks"][0].id == recent_chunk.id

    @pytest.mark.asyncio
    async def test_retrieve_entity_context_respects_token_budget(
        self,
        db_session,
        db_vault
    ):
        """
        Test that entity context retrieval respects token budget.

        GIVEN: Entity with many chunks exceeding budget
        WHEN: Retrieving with limited token budget
        THEN: Only chunks fitting within budget are returned
        """
        # GIVEN: Create entity with primary and multiple mention chunks
        entity = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Tyrion Lannister",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536,
            mention_chunk_ids=[]
        )

        primary_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Tyrion is the youngest Lannister child",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=600,
            usage_count=25,
            indexed_at=datetime.utcnow()
        )

        # Create 5 mention chunks (300 tokens each)
        mention_chunks = []
        for i in range(5):
            chunk = Chunk(
                id=uuid4(),
                vault_id=db_vault.id,
                content=f"Mention {i}: Tyrion's wit and wisdom",
                content_hash=f"hash{i+2}",
                file_path=f"/test{i+2}.md",
                file_hash=f"fhash{i+2}",
                line_start=1,
                line_end=10,
                char_start=0,
                char_end=100,
                chunk_index=0,
                token_count=300,
                usage_count=20 - i,  # Descending usage
                indexed_at=datetime.utcnow()
            )
            mention_chunks.append(chunk)
            entity.mention_chunk_ids.append(str(chunk.id))

        entity.primary_source_chunk_id = primary_chunk.id

        db_session.add(entity)
        db_session.add(primary_chunk)
        for chunk in mention_chunks:
            db_session.add(chunk)
        db_session.commit()

        # WHEN: Retrieve with 1000 token budget
        # Expected: Primary (600) + 1 mention (300) = 900 tokens
        retriever = RAGRetriever()
        context = await retriever.retrieve_entity_context(
            entity_id=entity.id,
            vault_id=db_vault.id,
            max_tokens=1000,
            session=db_session  # Inject session for test
        )

        # THEN: Budget is respected
        assert context["total_tokens"] <= 1000
        assert context["total_tokens"] == 900  # Primary + 1 mention
        assert len(context["chunks"]) == 2  # Primary + 1 mention
        assert context["chunks_by_source"]["primary_source"] == 1
        assert context["chunks_by_source"]["mention_chunks"] == 1  # Fixed key


class TestEntityContextBuilderWithRelationships:
    """
    Test suite for context builder with relationship graph.

    Design Decision:
    Test the 3-tier prioritization with real relationship data.

    Reasoning:
    Validates that relationship source chunks are correctly prioritized
    and integrated into the context.
    """

    @pytest.mark.asyncio
    async def test_context_includes_relationship_chunks(
        self,
        db_session,
        db_vault
    ):
        """
        Test that context builder includes relationship source chunks.

        GIVEN: Entity with relationships that have primary_source_chunk_id
        WHEN: Building context
        THEN: Relationship chunks are included after primary source
        """
        # GIVEN: Create two entities with a relationship
        ned = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Ned Stark",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536
        )

        catelyn = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Catelyn Stark",
            entity_type=EntityType.CHARACTER,
            embedding=[0.2] * 1536
        )

        # Primary source chunk for Ned
        ned_primary = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Ned Stark is Lord of Winterfell",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=15,
            indexed_at=datetime.utcnow()
        )

        # Relationship chunk
        relationship_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Ned married Catelyn Tully after Robert's Rebellion",
            content_hash="hash2",
            file_path="/test2.md",
            file_hash="fhash2",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=150,
            usage_count=10,
            indexed_at=datetime.utcnow()
        )

        # Create relationship
        relationship = Relationship(
            id=uuid4(),
            vault_id=db_vault.id,
            source_entity_id=ned.id,
            target_entity_id=catelyn.id,
            relationship_type=RelationType.SPOUSE,
            primary_source_chunk_id=relationship_chunk.id,
            is_active=True
        )

        ned.primary_source_chunk_id = ned_primary.id

        db_session.add(ned)
        db_session.add(catelyn)
        db_session.add(ned_primary)
        db_session.add(relationship_chunk)
        db_session.add(relationship)
        db_session.commit()

        # WHEN: Build context for Ned
        builder = EntityContextBuilder(max_tokens=1000, session=db_session)
        result = await builder.build_context(ned.id, db_vault.id)

        # THEN: Both chunks are included
        assert len(result.chunks) == 2
        assert result.chunks[0].id == ned_primary.id  # Primary first
        assert result.chunks[1].id == relationship_chunk.id  # Relationship second
        assert result.chunks_by_source["primary_source"] == 1
        assert result.chunks_by_source["relationship_sources"] == 1  # Fixed key
        assert result.total_tokens == 250


class TestNarrativeSequencePriority:
    """
    Test suite for narrative sequence prioritization in real scenarios.

    Design Decision:
    Test chronological ordering with actual narrative sequence data.

    Reasoning:
    Validates that NarrativeSequencePriority correctly orders chunks
    for character arc analysis.
    """

    @pytest.mark.asyncio
    async def test_narrative_sequence_preserves_chronology(
        self,
        db_session,
        db_vault
    ):
        """
        Test that narrative sequence prioritization preserves chronological order.

        GIVEN: Entity with chunks having different narrative sequences
        WHEN: Using NarrativeSequencePriority
        THEN: Chunks are returned in chronological order
        """
        # GIVEN: Create entity with chronologically ordered chunks
        entity = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Bran Stark",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536,
            mention_chunk_ids=[]
        )

        # Early chapter
        early_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Bran climbed the tower",
            content_hash="hash1",
            file_path="/chapter1.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=5,  # Low usage
            narrative_sequence=1,  # Early
            indexed_at=datetime.utcnow()
        )

        # Late chapter
        late_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Bran became the Three-Eyed Raven",
            content_hash="hash2",
            file_path="/chapter50.md",
            file_hash="fhash2",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=20,  # High usage
            narrative_sequence=50,  # Late
            indexed_at=datetime.utcnow()
        )

        entity.mention_chunk_ids = [str(late_chunk.id), str(early_chunk.id)]

        db_session.add(entity)
        db_session.add(early_chunk)
        db_session.add(late_chunk)
        db_session.commit()

        # WHEN: Build context with NarrativeSequencePriority
        builder = EntityContextBuilder(
            max_tokens=1000,
            priority_strategy=NarrativeSequencePriority(),
            session=db_session
        )
        result = await builder.build_context(entity.id, db_vault.id)

        # THEN: Chunks are in chronological order (despite usage counts)
        assert len(result.chunks) == 2
        assert result.chunks[0].narrative_sequence == 1  # Early first
        assert result.chunks[1].narrative_sequence == 50  # Late second
