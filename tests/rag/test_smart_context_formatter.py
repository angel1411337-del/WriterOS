"""
Tests for SmartContextFormatter

Design Decision:
Test the smart context formatter to ensure it produces structured,
hierarchical output instead of text blobs.
"""
import pytest
from uuid import uuid4
from datetime import datetime

from writeros.schema import Entity, Chunk, EntityType, Vault, ConnectionType
from writeros.rag.smart_context_formatter import SmartContextFormatter


class TestSmartContextFormatter:
    """Test suite for SmartContextFormatter"""

    @pytest.mark.asyncio
    async def test_format_context_with_entities(
        self,
        db_session,
        db_vault
    ):
        """
        Test smart formatting with entities.

        GIVEN: Entities with context chunks
        WHEN: Formatting context
        THEN: Output is hierarchical with entity sections
        """
        # GIVEN: Create entities with chunks
        ned = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Ned Stark",
            entity_type=EntityType.CHARACTER,
            description="Lord of Winterfell",
            embedding=[0.1] * 1536
        )

        ned_chunk = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Ned Stark is an honorable man who serves as Warden of the North",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=150,
            usage_count=10,
            indexed_at=datetime.utcnow()
        )

        ned.primary_source_chunk_id = ned_chunk.id

        db_session.add(ned)
        db_session.add(ned_chunk)
        db_session.commit()

        # WHEN: Format context
        formatter = SmartContextFormatter()
        context = await formatter.format_context(
            query="Tell me about Ned Stark",
            vault_id=db_vault.id,
            entities=[ned],
            max_total_tokens=1000,
            session=db_session
        )

        # THEN: Output is structured
        assert "## Key Entities" in context
        assert "### Ned Stark" in context
        assert "CHARACTER" in context
        assert "**Definition:**" in context
        assert "honorable man" in context
        assert "# Context for Query: Tell me about Ned Stark" in context

    @pytest.mark.asyncio
    async def test_format_context_without_entities(
        self,
        db_session,
        db_vault
    ):
        """
        Test formatting with no entities (edge case).

        GIVEN: No entities provided
        WHEN: Formatting context
        THEN: Returns query context without entity sections
        """
        # GIVEN: No entities
        formatter = SmartContextFormatter()

        # WHEN: Format context
        context = await formatter.format_context(
            query="What happened in chapter 5?",
            vault_id=db_vault.id,
            entities=[],
            max_total_tokens=1000,
            session=db_session
        )

        # THEN: Basic structure without entities
        assert "# Context for Query: What happened in chapter 5?" in context
        assert "## Key Entities" not in context  # No entity section

    @pytest.mark.asyncio
    async def test_format_context_respects_token_budget(
        self,
        db_session,
        db_vault
    ):
        """
        Test that formatter respects token budget.

        GIVEN: Multiple entities and documents
        WHEN: Formatting with limited budget
        THEN: Output fits within budget
        """
        # GIVEN: Create multiple entities
        entities = []
        for i in range(10):  # More entities than can fit
            entity = Entity(
                id=uuid4(),
                vault_id=db_vault.id,
                name=f"Character {i}",
                entity_type=EntityType.CHARACTER,
                description=f"Description for character {i}",
                embedding=[0.1] * 1536
            )
            entities.append(entity)
            db_session.add(entity)

        db_session.commit()

        # WHEN: Format with small budget
        formatter = SmartContextFormatter()
        context = await formatter.format_context(
            query="Tell me about the characters",
            vault_id=db_vault.id,
            entities=entities,
            max_total_tokens=500,  # Small budget
            max_entities=3,  # Limit entities
            session=db_session
        )

        # THEN: Only top entities included
        # Rough token estimate: 4 chars per token
        estimated_tokens = len(context) // 4
        assert estimated_tokens <= 600  # Allow some margin

        # Should only have max 3 entities
        entity_count = context.count("###")
        assert entity_count <= 3

    @pytest.mark.asyncio
    async def test_hierarchical_structure(
        self,
        db_session,
        db_vault
    ):
        """
        Test that output has hierarchical structure (not a blob).

        GIVEN: Entity with multiple chunk types
        WHEN: Formatting context
        THEN: Output has clear sections (Definition, Relationships, Context)
        """
        # GIVEN: Entity with primary and mention chunks
        entity = Entity(
            id=uuid4(),
            vault_id=db_vault.id,
            name="Jon Snow",
            entity_type=EntityType.CHARACTER,
            embedding=[0.1] * 1536,
            mention_chunk_ids=[]
        )

        primary = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Jon Snow is the bastard son of Ned Stark",
            content_hash="hash1",
            file_path="/test.md",
            file_hash="fhash1",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=10,
            indexed_at=datetime.utcnow()
        )

        mention = Chunk(
            id=uuid4(),
            vault_id=db_vault.id,
            content="Jon joined the Night's Watch at Castle Black",
            content_hash="hash2",
            file_path="/test2.md",
            file_hash="fhash2",
            line_start=1,
            line_end=10,
            char_start=0,
            char_end=100,
            chunk_index=0,
            token_count=100,
            usage_count=8,
            indexed_at=datetime.utcnow()
        )

        entity.primary_source_chunk_id = primary.id
        entity.mention_chunk_ids.append(str(mention.id))

        db_session.add(entity)
        db_session.add(primary)
        db_session.add(mention)
        db_session.commit()

        # WHEN: Format context
        formatter = SmartContextFormatter()
        context = await formatter.format_context(
            query="Who is Jon Snow?",
            vault_id=db_vault.id,
            entities=[entity],
            max_total_tokens=2000,
            session=db_session
        )

        # THEN: Has hierarchical sections
        assert "### Jon Snow" in context
        assert "**Definition:**" in context
        assert "**Context:**" in context
        # Primary source content
        assert "bastard son" in context
        # Mention content
        assert "Night's Watch" in context

        # Structure check: sections appear in order
        def_pos = context.index("**Definition:**")
        context_pos = context.index("**Context:**")
        assert def_pos < context_pos  # Definition comes before Context
