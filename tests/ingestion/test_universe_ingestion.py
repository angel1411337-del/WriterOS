"""
Test suite for Phase 2.5: Citadel Pipeline (Structured Universe Ingestion)

Tests:
1. Universe manifest loading
2. Era tag creation
3. Narrator creation
4. Entity disambiguation by era
5. Metadata injection
6. Narrator claim extraction
"""
import pytest
import json
from pathlib import Path
from uuid import uuid4, UUID
from sqlmodel import Session, select

from writeros.schema import Vault, EraTag, Narrator, Entity, Document
from writeros.schema.universe_manifest import UniverseManifest, CanonWork, NarratorReliability
from writeros.scripts.ingest_universe import UniverseIngester
from writeros.agents.profiler import ProfilerAgent
from writeros.utils.indexer import VaultIndexer
from writeros.utils.db import engine


@pytest.fixture
def sample_vault(db_session):
    """Create a sample vault for testing."""
    vault = Vault(
        name="Test ASOIAF Vault",
        user_id=uuid4()
    )
    db_session.add(vault)
    db_session.commit()
    db_session.refresh(vault)
    return vault


@pytest.fixture
def sample_manifest(tmp_path):
    """Create a sample universe manifest."""
    manifest_data = {
        "universe_name": "Test Universe",
        "version": "1.0",
        "eras": [
            {
                "name": "Ancient Era",
                "description": "The old times",
                "time_range": {"start_year": 1, "end_year": 100},
                "color": "#FF0000",
                "icon": "🏛️"
            },
            {
                "name": "Modern Era",
                "description": "Present day",
                "time_range": {"start_year": 100, "end_year": 200},
                "color": "#00FF00",
                "icon": "🏙️"
            }
        ],
        "works": [
            {
                "title": "Ancient Chronicles",
                "source_path": "Story_Bible/Ancient",
                "ingestion_order": 1,
                "story_time_range": {"start_year": 1, "end_year": 100},
                "era_name": "Ancient Era",
                "era_sequence": 1,
                "has_unreliable_narrators": True,
                "default_narrator": "Old Scribe",
                "narrator_reliability": "conflicting",
                "expected_entities": [
                    {
                        "name": "King Arthur",
                        "type": "character",
                        "era_start_year": 50,
                        "era_end_year": 80,
                        "aliases": ["The King", "Arthur"]
                    }
                ],
                "canon_layer": "primary",
                "metadata": {
                    "author": "Test Author",
                    "publication_year": 2020
                }
            },
            {
                "title": "Modern Tales",
                "source_path": "Story_Bible/Modern",
                "ingestion_order": 2,
                "story_time_range": {"start_year": 100, "end_year": 200},
                "era_name": "Modern Era",
                "era_sequence": 2,
                "has_unreliable_narrators": False,
                "default_narrator": "Omniscient",
                "narrator_reliability": "omniscient",
                "expected_entities": [
                    {
                        "name": "King Arthur",
                        "type": "character",
                        "era_start_year": 120,
                        "era_end_year": 150,
                        "aliases": ["Arthur II", "The Returned King"]
                    }
                ],
                "canon_layer": "primary",
                "metadata": {
                    "author": "Test Author",
                    "publication_year": 2021
                }
            }
        ],
        "disambiguation_rules": {
            "name_patterns": {
                "King Arthur": "Use era_start_year to distinguish between Arthur I (50-80) and Arthur II (120-150)"
            }
        },
        "metadata": {
            "total_eras": 2,
            "ingestion_strategy": "chronological"
        }
    }

    manifest_path = tmp_path / "test_universe.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_data, f)

    return manifest_path


class TestUniverseManifestSchema:
    """Tests for UniverseManifest schema validation."""

    def test_manifest_loads_correctly(self, sample_manifest):
        """Test that manifest JSON loads into schema correctly."""
        with open(sample_manifest, 'r', encoding='utf-8') as f:
            data = json.load(f)

        manifest = UniverseManifest(**data)

        assert manifest.universe_name == "Test Universe"
        assert len(manifest.eras) == 2
        assert len(manifest.works) == 2

    def test_works_sorted_by_ingestion_order(self, sample_manifest):
        """Test that get_sorted_works() returns works in correct order."""
        with open(sample_manifest, 'r', encoding='utf-8') as f:
            data = json.load(f)

        manifest = UniverseManifest(**data)
        sorted_works = manifest.get_sorted_works()

        assert sorted_works[0].title == "Ancient Chronicles"
        assert sorted_works[1].title == "Modern Tales"
        assert sorted_works[0].ingestion_order == 1
        assert sorted_works[1].ingestion_order == 2

    def test_get_works_by_era(self, sample_manifest):
        """Test filtering works by era."""
        with open(sample_manifest, 'r', encoding='utf-8') as f:
            data = json.load(f)

        manifest = UniverseManifest(**data)
        ancient_works = manifest.get_works_by_era("Ancient Era")

        assert len(ancient_works) == 1
        assert ancient_works[0].title == "Ancient Chronicles"


class TestEraTagCreation:
    """Tests for EraTag database creation."""

    @pytest.mark.asyncio
    async def test_create_era_tags(self, sample_vault, sample_manifest, db_session):
        """Test that era tags are created in database."""
        with open(sample_manifest, 'r', encoding='utf-8') as f:
            data = json.load(f)

        manifest = UniverseManifest(**data)

        # Create ingester (without actual file ingestion)
        ingester = UniverseIngester(
            manifest_path=sample_manifest,
            vault_id=sample_vault.id,
            vault_path=Path("/fake/path")  # Won't be used for this test
        )

        # Create era tags
        count = await ingester._create_era_tags()

        assert count == 2

        # Verify in database
        eras = db_session.exec(
            select(EraTag).where(EraTag.vault_id == sample_vault.id)
        ).all()

        assert len(eras) == 2

        # Check first era
        ancient_era = [e for e in eras if e.name == "Ancient Era"][0]
        assert ancient_era.description == "The old times"
        assert ancient_era.color == "#FF0000"
        assert ancient_era.icon == "🏛️"


class TestNarratorCreation:
    """Tests for Narrator database creation."""

    @pytest.mark.asyncio
    async def test_create_narrators(self, sample_vault, sample_manifest, db_session):
        """Test that narrator entries are created."""
        with open(sample_manifest, 'r', encoding='utf-8') as f:
            data = json.load(f)

        manifest = UniverseManifest(**data)

        ingester = UniverseIngester(
            manifest_path=sample_manifest,
            vault_id=sample_vault.id,
            vault_path=Path("/fake/path")
        )

        # Create narrators
        count = await ingester._create_narrators()

        assert count >= 2  # At least "Old Scribe" and "Omniscient"

        # Verify in database
        narrators = db_session.exec(
            select(Narrator).where(Narrator.vault_id == sample_vault.id)
        ).all()

        assert len(narrators) >= 2

        # Check "Old Scribe" narrator
        old_scribe = [n for n in narrators if n.name == "Old Scribe"][0]
        assert old_scribe.reliability_score == 0.3  # conflicting = 0.3


class TestEntityDisambiguation:
    """Tests for entity resolution by era."""

    @pytest.mark.asyncio
    async def test_resolve_entity_by_era_single_match(self, sample_vault, db_session):
        """Test resolving entity when only one match exists."""
        profiler = ProfilerAgent()

        # Create a single entity
        entity = Entity(
            vault_id=sample_vault.id,
            name="Unique Character",
            type="character",
            description="A unique character",
            embedding=[0.1] * 1536
        )
        db_session.add(entity)
        db_session.commit()

        # Resolve
        resolved = await profiler.resolve_entity_by_era(
            name="Unique Character",
            vault_id=sample_vault.id
        )

        assert resolved is not None
        assert resolved.id == entity.id

    @pytest.mark.asyncio
    async def test_resolve_entity_by_era_multiple_matches(self, sample_vault, db_session):
        """Test disambiguating between entities with same name in different eras."""
        profiler = ProfilerAgent()

        # Create Arthur I (Ancient Era)
        arthur_1 = Entity(
            vault_id=sample_vault.id,
            name="King Arthur",
            type="character",
            description="Ancient king",
            embedding=[0.1] * 1536,
            metadata_={
                "era_start_year": 50,
                "era_end_year": 80
            }
        )
        db_session.add(arthur_1)

        # Create Arthur II (Modern Era)
        arthur_2 = Entity(
            vault_id=sample_vault.id,
            name="King Arthur",
            type="character",
            description="Modern king",
            embedding=[0.1] * 1536,
            metadata_={
                "era_start_year": 120,
                "era_end_year": 150
            }
        )
        db_session.add(arthur_2)
        db_session.commit()

        # Resolve at year 60 - should get Arthur I
        resolved_ancient = await profiler.resolve_entity_by_era(
            name="King Arthur",
            vault_id=sample_vault.id,
            current_story_time={"year": 60}
        )

        assert resolved_ancient.id == arthur_1.id

        # Resolve at year 130 - should get Arthur II
        resolved_modern = await profiler.resolve_entity_by_era(
            name="King Arthur",
            vault_id=sample_vault.id,
            current_story_time={"year": 130}
        )

        assert resolved_modern.id == arthur_2.id

    @pytest.mark.asyncio
    async def test_find_or_create_entity_reuses_existing(self, sample_vault, db_session):
        """Test that find_or_create reuses existing entity instead of creating duplicate."""
        profiler = ProfilerAgent()

        # Create existing entity
        existing = Entity(
            vault_id=sample_vault.id,
            name="Test Character",
            type="character",
            description="Original",
            embedding=[0.1] * 1536,
            metadata_={"era_start_year": 50, "era_end_year": 100}
        )
        db_session.add(existing)
        db_session.commit()
        db_session.refresh(existing)

        # Try to create same entity
        result = await profiler.find_or_create_entity(
            name="Test Character",
            entity_type="character",
            vault_id=sample_vault.id,
            current_story_time={"year": 75}
        )

        # Should return existing entity, not create new one
        assert result.id == existing.id

        # Verify only one entity exists
        all_entities = db_session.exec(
            select(Entity).where(
                Entity.vault_id == sample_vault.id,
                Entity.name == "Test Character"
            )
        ).all()

        assert len(all_entities) == 1


class TestNarratorExtraction:
    """Tests for narrator claim extraction from text."""

    def test_extract_mushroom_claim(self):
        """Test extracting claim from Mushroom."""
        indexer = VaultIndexer(
            vault_path="/fake",
            vault_id=uuid4(),
            override_metadata={"has_unreliable_narrators": True}
        )

        text = "Mushroom claims that the queen wore a red dress to the feast."

        claims = indexer.extract_narrator_claims(text)

        assert len(claims) >= 1
        assert any(c["narrator"] == "Mushroom" for c in claims)
        assert any("red dress" in c["claim"] for c in claims)

    def test_extract_according_to_pattern(self):
        """Test 'According to X' pattern."""
        indexer = VaultIndexer(
            vault_path="/fake",
            vault_id=uuid4(),
            override_metadata={"has_unreliable_narrators": True}
        )

        text = "According to Septon Eustace, the battle lasted three days."

        claims = indexer.extract_narrator_claims(text)

        assert len(claims) >= 1
        assert any(c["narrator"] == "Septon Eustace" for c in claims)
        assert any("battle" in c["claim"] for c in claims)

    def test_extract_account_states_pattern(self):
        """Test 'X's account states' pattern."""
        indexer = VaultIndexer(
            vault_path="/fake",
            vault_id=uuid4(),
            override_metadata={"has_unreliable_narrators": True}
        )

        text = "Grand Maester Munkun's account states that the king was poisoned."

        claims = indexer.extract_narrator_claims(text)

        assert len(claims) >= 1
        assert any(c["narrator"] == "Grand Maester Munkun" for c in claims)
        assert any("poisoned" in c["claim"] for c in claims)


class TestMetadataInjection:
    """Tests for metadata injection during ingestion."""

    @pytest.mark.asyncio
    async def test_override_metadata_injected(self, sample_vault, tmp_path, db_session):
        """Test that override metadata is injected into document chunks."""
        # Create a test file
        test_file = tmp_path / "test.md"
        test_file.write_text("This is a test document for metadata injection.")

        # Create indexer with override metadata
        indexer = VaultIndexer(
            vault_path=str(tmp_path),
            vault_id=sample_vault.id,
            override_metadata={
                "era_name": "Test Era",
                "canon_layer": "primary",
                "ingestion_order": 1
            }
        )

        # Index the file
        chunks = await indexer.index_file(test_file)

        assert chunks > 0

        # Verify metadata in database
        docs = db_session.exec(
            select(Document).where(Document.vault_id == sample_vault.id)
        ).all()

        assert len(docs) > 0

        # Check first document
        doc = docs[0]
        assert doc.metadata_.get("era_name") == "Test Era"
        assert doc.metadata_.get("canon_layer") == "primary"
        assert doc.metadata_.get("ingestion_order") == 1


class TestRealWorldScenarios:
    """Integration tests for real-world usage scenarios."""

    @pytest.mark.asyncio
    async def test_asoiaf_aegon_disambiguation(self, sample_vault, db_session):
        """
        Real-world scenario: Distinguish between multiple Aegons.

        Aegon I (1-37)
        Aegon II (120-131)
        Aegon V (208-259)
        """
        profiler = ProfilerAgent()

        # Create the three Aegons
        aegon_1 = await profiler.find_or_create_entity(
            name="Aegon",
            entity_type="character",
            vault_id=sample_vault.id,
            description="Aegon I, The Conqueror",
            override_metadata={"era_start_year": 1, "era_end_year": 37}
        )

        aegon_2 = await profiler.find_or_create_entity(
            name="Aegon",
            entity_type="character",
            vault_id=sample_vault.id,
            description="Aegon II, The Usurper",
            override_metadata={"era_start_year": 120, "era_end_year": 131}
        )

        aegon_5 = await profiler.find_or_create_entity(
            name="Aegon",
            entity_type="character",
            vault_id=sample_vault.id,
            description="Aegon V, The Unlikely (Egg)",
            override_metadata={"era_start_year": 208, "era_end_year": 259}
        )

        # Resolve at different time periods
        resolved_at_20 = await profiler.resolve_entity_by_era(
            name="Aegon",
            vault_id=sample_vault.id,
            current_story_time={"year": 20}
        )
        assert resolved_at_20.id == aegon_1.id

        resolved_at_125 = await profiler.resolve_entity_by_era(
            name="Aegon",
            vault_id=sample_vault.id,
            current_story_time={"year": 125}
        )
        assert resolved_at_125.id == aegon_2.id

        resolved_at_220 = await profiler.resolve_entity_by_era(
            name="Aegon",
            vault_id=sample_vault.id,
            current_story_time={"year": 220}
        )
        assert resolved_at_220.id == aegon_5.id
