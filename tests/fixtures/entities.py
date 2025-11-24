"""
Entity fixtures for WriterOS tests.
Provides sample characters, locations, and factions.
"""
from uuid import uuid4
from src.writeros.schema import Entity, EntityType, CanonInfo


def create_character(name: str, description: str, vault_id=None):
    """Create a test character entity."""
    return Entity(
        id=uuid4(),
        vault_id=vault_id or uuid4(),
        name=name,
        type=EntityType.CHARACTER,
        description=description,
        canon=CanonInfo(layer="primary", status="active"),
        properties={"role": "protagonist"}
    )


def create_location(name: str, description: str, vault_id=None):
    """Create a test location entity."""
    return Entity(
        id=uuid4(),
        vault_id=vault_id or uuid4(),
        name=name,
        type=EntityType.LOCATION,
        description=description,
        canon=CanonInfo(layer="primary", status="active"),
        properties={"terrain": "urban"}
    )


# Sample entities
SAMPLE_ENTITIES = {
    "character": create_character(
        "Aria Winters",
        "A skilled hacker navigating the neon-lit streets of Neo Tokyo"
    ),
    "location": create_location(
        "Neo Tokyo",
        "A sprawling megacity dominated by corporate skyscrapers and holographic billboards"
    ),
}
