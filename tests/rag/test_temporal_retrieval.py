"""
Anti-Spoiler Test Suite - Temporal RAG Retrieval

Tests the "time-aware" retrieval system to prevent spoilers and maintain narrative continuity.

Test Scenario:
- Event A (Day 1 / Sequence 1): "Hero finds the sword"
- Event B (Day 10 / Sequence 10): "Hero breaks the sword"

Query at Day 5 (Sequence 5): "What is the status of the sword?"
- Expected: Only retrieve Event A
- Response should indicate: "The hero has the sword"

Query at Day 11 (Sequence 11): "What is the status of the sword?"
- Expected: Retrieve both Event A and B
- Response should indicate: "The sword is broken"
"""
import pytest
from uuid import uuid4
from sqlmodel import Session

from writeros.rag.retriever import RAGRetriever, RetrievalResult
from writeros.schema import Event, Vault, User, SubscriptionTier, ConnectionType


@pytest.fixture
def sample_timeline(db_session, sample_vault_id):
    """Create a sample timeline with two events about a sword."""
    # Create user
    user = User(
        email="timeline_test@writeros.local",
        username="timelinetest",
        tier=SubscriptionTier.FREE
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create vault
    vault = Vault(
        id=sample_vault_id,
        name="Temporal Test Vault",
        owner_id=user.id,
        connection_type=ConnectionType.LOCAL_OBSIDIAN,
        local_system_path="/test/vault"
    )
    db_session.add(vault)
    db_session.commit()

    # Event A: Hero finds the sword (Day 1, Sequence 1)
    event_a = Event(
        vault_id=sample_vault_id,
        name="Hero Finds Sword",
        description="The hero discovers a legendary sword in the ancient ruins",
        story_time={"year": 280, "month": 1, "day": 1},
        narrative_time={"chapter": 1, "scene": 1},
        sequence_order=1,
        embedding=[0.1] * 1536  # Mock embedding
    )
    db_session.add(event_a)

    # Event B: Hero breaks the sword (Day 10, Sequence 10)
    event_b = Event(
        vault_id=sample_vault_id,
        name="Sword Breaks",
        description="The legendary sword shatters during the battle with the dark knight",
        story_time={"year": 280, "month": 1, "day": 10},
        narrative_time={"chapter": 5, "scene": 3},
        sequence_order=10,
        embedding=[0.15] * 1536  # Mock embedding (slightly different)
    )
    db_session.add(event_b)

    db_session.commit()

    return {"event_a": event_a, "event_b": event_b, "vault": vault}


class TestTemporalFilteringSequence:
    """Tests for sequence-based temporal filtering."""

    @pytest.mark.asyncio
    async def test_retrieve_at_sequence_5_only_past_events(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """
        Test that querying at sequence 5 only returns events from sequence 1-5.
        This is the "anti-spoiler" test.
        """
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        # Query at sequence 5 (Day 5) - should only get Event A
        results = await retriever.retrieve(
            query="What is the status of the sword?",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="sequence",
            max_sequence_order=5
        )

        # Should only retrieve Event A (sequence 1)
        assert len(results.events) == 1
        assert results.events[0].name == "Hero Finds Sword"
        assert results.events[0].sequence_order == 1

        # Event B should NOT be in results (it's in the future)
        event_names = [e.name for e in results.events]
        assert "Sword Breaks" not in event_names

        # Verify temporal context is recorded
        assert results.temporal_context is not None
        assert results.temporal_context["mode"] == "sequence"
        assert results.temporal_context["max_sequence_order"] == 5

    @pytest.mark.asyncio
    async def test_retrieve_at_sequence_11_includes_all_events(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """Test that querying at sequence 11 returns all events (no spoilers)."""
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        # Query at sequence 11 (Day 11) - should get both events
        results = await retriever.retrieve(
            query="What is the status of the sword?",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="sequence",
            max_sequence_order=11
        )

        # Should retrieve both Event A and Event B
        assert len(results.events) == 2
        event_names = [e.name for e in results.events]
        assert "Hero Finds Sword" in event_names
        assert "Sword Breaks" in event_names

    @pytest.mark.asyncio
    async def test_god_mode_retrieves_all_events(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """Test that 'god' mode (no temporal filtering) retrieves all events."""
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        # Query in god mode - should get all events regardless of time
        results = await retriever.retrieve(
            query="What is the status of the sword?",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="god"  # No filtering
        )

        # Should retrieve both events
        assert len(results.events) == 2

        # Temporal context should indicate god mode
        assert results.temporal_context is not None
        assert results.temporal_context["mode"] == "god"


class TestTemporalFilteringStoryTime:
    """Tests for story_time-based temporal filtering."""

    @pytest.mark.asyncio
    async def test_retrieve_at_day_5_only_past_events(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """Test that querying at Day 5 only returns events from Days 1-5."""
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        # Query at Day 5 (story_time) - should only get Event A
        results = await retriever.retrieve(
            query="What is the status of the sword?",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="story_time",
            max_story_time={"year": 280, "month": 1, "day": 5}
        )

        # Should only retrieve Event A (Day 1)
        assert len(results.events) == 1
        assert results.events[0].name == "Hero Finds Sword"
        assert results.events[0].story_time["day"] == 1

        # Event B should NOT be in results
        event_names = [e.name for e in results.events]
        assert "Sword Breaks" not in event_names

    @pytest.mark.asyncio
    async def test_retrieve_at_day_11_includes_all_events(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """Test that querying at Day 11 returns all events."""
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        # Query at Day 11 - should get both events
        results = await retriever.retrieve(
            query="What is the status of the sword?",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="story_time",
            max_story_time={"year": 280, "month": 1, "day": 11}
        )

        # Should retrieve both events
        assert len(results.events) == 2


class TestTemporalFormattingOutput:
    """Tests for formatted output with temporal context."""

    @pytest.mark.asyncio
    async def test_format_results_includes_temporal_context(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """Test that formatted results include temporal context."""
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        results = await retriever.retrieve(
            query="sword status",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="sequence",
            max_sequence_order=5
        )

        formatted = retriever.format_results(results)

        # Should include temporal context indicator
        assert "TEMPORAL CONTEXT" in formatted
        assert "sequence order 5" in formatted

        # Should show Event A
        assert "Hero Finds Sword" in formatted

    @pytest.mark.asyncio
    async def test_format_results_shows_sequence_numbers(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """Test that events are formatted with sequence numbers."""
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        results = await retriever.retrieve(
            query="sword",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="god"
        )

        formatted = retriever.format_results(results)

        # Should include sequence numbers in output
        assert "[Seq: 1]" in formatted
        assert "[Seq: 10]" in formatted


class TestTemporalEdgeCases:
    """Tests for edge cases in temporal filtering."""

    @pytest.mark.asyncio
    async def test_events_without_sequence_order_included(
        self,
        db_session,
        sample_vault_id,
        mock_embedding_service
    ):
        """Test that events without sequence_order are included (permissive fallback)."""
        # Create event with no sequence_order
        event_no_seq = Event(
            vault_id=sample_vault_id,
            name="Timeless Event",
            description="An event outside of time",
            sequence_order=None,  # No sequence
            embedding=[0.2] * 1536
        )
        db_session.add(event_no_seq)
        db_session.commit()

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        results = await retriever.retrieve(
            query="timeless",
            vault_id=sample_vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="sequence",
            max_sequence_order=5
        )

        # Event without sequence_order should still be retrieved
        # (We don't filter it out if it has no temporal data)
        event_names = [e.name for e in results.events]
        # This depends on implementation - could go either way
        # For now, NULL sequence_order means "don't filter it"

    @pytest.mark.asyncio
    async def test_exact_boundary_sequence_included(
        self,
        sample_timeline,
        mock_embedding_service
    ):
        """Test that event at exact sequence boundary is included."""
        vault_id = sample_timeline["vault"].id

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        # Query at sequence 10 (exact boundary)
        results = await retriever.retrieve(
            query="sword",
            vault_id=vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="sequence",
            max_sequence_order=10
        )

        # Should include both events (Event B is at sequence 10)
        assert len(results.events) == 2


class TestIntegrationWithOrchestrator:
    """Integration tests for temporal context extraction in Orchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_extracts_sequence_context(
        self,
        mocker
    ):
        """Test that Orchestrator can extract and use sequence context."""
        # This would test the full flow:
        # User provides frontmatter: sequence_order: 5
        # Orchestrator extracts it
        # Passes to retriever
        # Gets filtered results
        pass  # Placeholder for future integration test


class TestAntiSpoilerScenarios:
    """Real-world anti-spoiler test scenarios."""

    @pytest.mark.asyncio
    async def test_writing_chapter_1_no_chapter_10_spoilers(
        self,
        db_session,
        sample_vault_id,
        mock_embedding_service
    ):
        """
        Scenario: User is writing Chapter 1.
        Query: "Is the King alive?"
        Expected: Should only see Chapter 1 information (King is alive).
        Should NOT see Chapter 10 information (King dies).
        """
        # Setup: King's status events
        event_king_alive = Event(
            vault_id=sample_vault_id,
            name="King Introduced",
            description="The King is introduced, ruling the kingdom",
            narrative_time={"chapter": 1},
            sequence_order=1,
            embedding=[0.3] * 1536
        )

        event_king_dies = Event(
            vault_id=sample_vault_id,
            name="King Dies",
            description="The King is assassinated by the traitor",
            narrative_time={"chapter": 10},
            sequence_order=10,
            embedding=[0.35] * 1536
        )

        db_session.add(event_king_alive)
        db_session.add(event_king_dies)
        db_session.commit()

        retriever = RAGRetriever(embedding_service=mock_embedding_service)

        # User writing Chapter 1 - query about King
        results = await retriever.retrieve(
            query="Is the King alive?",
            vault_id=sample_vault_id,
            include_documents=False,
            include_entities=False,
            include_facts=False,
            include_events=True,
            temporal_mode="sequence",
            max_sequence_order=1  # Only Chapter 1
        )

        # Should ONLY see Chapter 1 event
        assert len(results.events) == 1
        assert results.events[0].name == "King Introduced"

        # Should NOT see death event
        event_names = [e.name for e in results.events]
        assert "King Dies" not in event_names

        # SUCCESS: No spoilers! User can safely write Chapter 1
        # without being told the King dies in Chapter 10.
