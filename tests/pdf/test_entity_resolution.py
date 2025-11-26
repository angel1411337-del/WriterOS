"""
Tests for temporal entity resolution and disambiguation.

Tests:
- Single entity resolution
- Temporal disambiguation (multiple Aegon entities)
- Fallback to most recent entity
- find_or_create_entity (existing)
- find_or_create_entity (new)
- Duplicate prevention across eras
"""
import pytest
from uuid import uuid4
import time

from writeros.schema import Entity, EntityType
from writeros.agents.profiler import ProfilerAgent


class TestEntityResolution:
    """Test suite for temporal entity resolution."""
    
    @pytest.mark.asyncio
    async def test_resolve_entity_by_era_single_match(self, db_session, sample_vault_id, mock_profiler):
        """Test resolving entity when only one match exists."""
        profiler = mock_profiler
        
        # Create single entity
        entity = Entity(
            vault_id=sample_vault_id,
            name="Rhaenyra",
            type=EntityType.CHARACTER,
            description="Princess Rhaenyra Targaryen",
            embedding=[0.1] * 1536
        )
        db_session.add(entity)
        db_session.commit()
        
        # Resolve entity
        result = await profiler.resolve_entity_by_era(
            name="Rhaenyra",
            vault_id=sample_vault_id
        )
        
        # Verify correct entity returned
        assert result is not None
        assert result.id == entity.id
        assert result.name == "Rhaenyra"
    
    @pytest.mark.asyncio
    async def test_resolve_entity_by_era_temporal_disambiguation(self, db_session, sample_vault_id, mock_profiler):
        """Test temporal disambiguation with multiple entities of same name."""
        profiler = mock_profiler
        
        # Create Aegon I (1-37 AC)
        aegon_i = Entity(
            vault_id=sample_vault_id,
            name="Aegon",
            type=EntityType.CHARACTER,
            description="Aegon I Targaryen, the Conqueror",
            embedding=[0.1] * 1536,
            properties={
                "era_start_year": 1,
                "era_end_year": 37
            }
        )
        
        # Create Aegon II (129-131 AC)
        aegon_ii = Entity(
            vault_id=sample_vault_id,
            name="Aegon",
            type=EntityType.CHARACTER,
            description="Aegon II Targaryen",
            embedding=[0.2] * 1536,
            properties={
                "era_start_year": 129,
                "era_end_year": 131
            }
        )
        
        db_session.add(aegon_i)
        db_session.add(aegon_ii)
        db_session.commit()
        
        # Resolve for year 130 (Dance of Dragons)
        result = await profiler.resolve_entity_by_era(
            name="Aegon",
            vault_id=sample_vault_id,
            current_story_time={"year": 130}
        )
        
        # Verify Aegon II returned (not Aegon I)
        assert result is not None
        assert result.id == aegon_ii.id
        assert result.properties["era_start_year"] == 129
    
    @pytest.mark.asyncio
    async def test_resolve_entity_by_era_fallback(self, db_session, sample_vault_id, mock_profiler):
        """Test fallback to most recent entity when no temporal context."""
        profiler = mock_profiler
        
        # Create two entities (different created_at times)
        aegon_old = Entity(
            vault_id=sample_vault_id,
            name="Aegon",
            type=EntityType.CHARACTER,
            description="Older Aegon",
            embedding=[0.1] * 1536
        )
        db_session.add(aegon_old)
        db_session.commit()
        
        time.sleep(0.1)  # Ensure different timestamps
        
        aegon_new = Entity(
            vault_id=sample_vault_id,
            name="Aegon",
            type=EntityType.CHARACTER,
            description="Newer Aegon",
            embedding=[0.2] * 1536
        )
        db_session.add(aegon_new)
        db_session.commit()
        
        # Resolve without temporal context
        result = await profiler.resolve_entity_by_era(
            name="Aegon",
            vault_id=sample_vault_id
        )
        
        # Verify most recent entity returned
        assert result is not None
        assert result.id == aegon_new.id
    
    @pytest.mark.asyncio
    async def test_find_or_create_entity_existing(self, db_session, sample_vault_id, mock_profiler):
        """Test find_or_create_entity returns existing entity."""
        profiler = mock_profiler
        
        # Create existing entity
        existing = Entity(
            vault_id=sample_vault_id,
            name="Daemon",
            type=EntityType.CHARACTER,
            description="Prince Daemon Targaryen",
            embedding=[0.1] * 1536
        )
        db_session.add(existing)
        db_session.commit()
        
        # Try to find or create
        result = await profiler.find_or_create_entity(
            name="Daemon",
            entity_type=EntityType.CHARACTER,
            vault_id=sample_vault_id,
            description="Prince Daemon"
        )
        
        # Verify existing entity returned (not new one created)
        assert result.id == existing.id
        
        # Verify only one Daemon exists
        from sqlmodel import select
        daemons = db_session.exec(
            select(Entity).where(
                Entity.vault_id == sample_vault_id,
                Entity.name == "Daemon"
            )
        ).all()
        assert len(daemons) == 1
    
    @pytest.mark.asyncio
    async def test_find_or_create_entity_new(self, db_session, sample_vault_id, mock_profiler):
        """Test find_or_create_entity creates new entity when none exists."""
        profiler = mock_profiler
        
        # Create new entity
        result = await profiler.find_or_create_entity(
            name="Viserys",
            entity_type=EntityType.CHARACTER,
            vault_id=sample_vault_id,
            description="King Viserys I Targaryen",
            override_metadata={"era_start_year": 103, "era_end_year": 129}
        )
        
        # Verify entity created
        assert result is not None
        assert result.name == "Viserys"
        assert result.type == EntityType.CHARACTER
        assert result.properties["era_start_year"] == 103
        
        # Verify entity in database
        db_session.refresh(result)
        assert result.id is not None
    
    @pytest.mark.asyncio
    async def test_prevent_duplicate_entities_across_eras(self, db_session, sample_vault_id, mock_profiler):
        """Test that entities with same name but different eras don't create duplicates."""
        profiler = mock_profiler
        
        # Create Aegon I
        aegon_i = await profiler.find_or_create_entity(
            name="Aegon",
            entity_type=EntityType.CHARACTER,
            vault_id=sample_vault_id,
            description="Aegon I",
            override_metadata={"era_start_year": 1, "era_end_year": 37}
        )
        
        # Try to create Aegon II (different era)
        aegon_ii = await profiler.find_or_create_entity(
            name="Aegon",
            entity_type=EntityType.CHARACTER,
            vault_id=sample_vault_id,
            description="Aegon II",
            override_metadata={"era_start_year": 129, "era_end_year": 131},
            current_story_time={"year": 130}
        )
        
        # Verify two different entities created (different eras)
        assert aegon_i.id != aegon_ii.id
        
        # Verify both exist in database
        from sqlmodel import select
        aegons = db_session.exec(
            select(Entity).where(
                Entity.vault_id == sample_vault_id,
                Entity.name == "Aegon"
            )
        ).all()
        assert len(aegons) == 2
