#!/usr/bin/env python3
"""
Database seeding script for WriterOS.
Populates the database with sample data from data/fixtures/.

Usage:
    python -m scripts.seed_data
"""
import asyncio
from pathlib import Path
import json
from uuid import UUID

# Import from installed package (requires: pip install -e .)
from writeros.utils.db import get_session, engine
from writeros.schema import Entity, Relationship, EntityType, RelationType
from writeros.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def load_fixtures():
    """Load sample data from data/fixtures/."""
    fixtures_dir = Path(__file__).parent.parent / "data" / "fixtures"
    
    if not fixtures_dir.exists():
        logger.warning("fixtures_dir_not_found", path=str(fixtures_dir))
        return []
    
    fixtures = []
    for json_file in fixtures_dir.glob("*.json"):
        with open(json_file, "r") as f:
            data = json.load(f)
            fixtures.append(data)
    
    return fixtures


async def seed_database():
    """Seed the database with sample entities and relationships."""
    logger.info("seeding_database")
    
    fixtures = load_fixtures()
    
    if not fixtures:
        logger.info("creating_default_fixtures")
        # Create default sample data if no fixtures exist
        from tests.fixtures.entities import SAMPLE_ENTITIES
        fixtures = [
            {
                "name": entity.name,
                "type": str(entity.type),
                "description": entity.description
            }
            for entity in SAMPLE_ENTITIES.values()
        ]
    
    logger.info("fixtures_loaded", count=len(fixtures))
    
    # TODO: Insert fixtures into database
    # This will be implemented once we have proper database initialization
    
    logger.info("seeding_complete")


if __name__ == "__main__":
    asyncio.run(seed_database())
