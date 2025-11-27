import pytest
from uuid import uuid4
from writeros.schema.entities import Entity
from writeros.schema.enums import EntityType, EntityStatus, CanonLayer, CanonStatus

def test_entity_instantiation():
    """Test that Entity can be instantiated with default values."""
    entity = Entity(
        vault_id=uuid4(),
        name="Test Entity",
        entity_type=EntityType.CHARACTER
    )
    
    assert entity.name == "Test Entity"
    assert entity.entity_type == EntityType.CHARACTER
    assert entity.status == EntityStatus.ALIVE
    assert entity.canon_layer == CanonLayer.PRIMARY
    assert entity.canon_status == CanonStatus.ACTIVE
    assert entity.extraction_confidence == 1.0
    assert entity.user_verified is False
    assert entity.aliases == []
    assert entity.metadata_ == {}
    assert entity.embedding is None

def test_entity_full_instantiation():
    """Test that Entity can be instantiated with all values."""
    vault_id = uuid4()
    chunk_id = uuid4()
    
    entity = Entity(
        vault_id=vault_id,
        name="Aragorn",
        entity_type=EntityType.CHARACTER,
        aliases=["Strider", "Elessar"],
        description="Heir of Isildur",
        status=EntityStatus.ALIVE,
        canon_layer=CanonLayer.PRIMARY,
        canon_status=CanonStatus.ACTIVE,
        extraction_confidence=0.9,
        extraction_method="ner",
        user_verified=True,
        primary_source_chunk_id=chunk_id,
        metadata_={"race": "Human", "age": 87},
        embedding=[0.1, 0.2, 0.3]
    )
    
    assert entity.name == "Aragorn"
    assert entity.aliases == ["Strider", "Elessar"]
    assert entity.metadata_["race"] == "Human"
    assert entity.embedding == [0.1, 0.2, 0.3]
