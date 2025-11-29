"""
Universe Ingestion Script

Reads a universe.json manifest and ingests works in chronological order.
Handles:
- Era tagging
- Narrator extraction
- Entity disambiguation
- Metadata injection

Usage:
    python -m writeros.scripts.ingest_universe \
        --manifest examples/asoiaf_universe.json \
        --vault-id 550e8400-e29b-41d4-a716-446655440000 \
        --vault-path /path/to/vault
"""
import asyncio
import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select

from writeros.schema.universe_manifest import UniverseManifest, CanonWork
from writeros.schema import Vault, EraTag, Narrator
from writeros.utils.indexer import VaultIndexer
from writeros.utils.db import engine
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class UniverseIngester:
    """
    Orchestrates the ingestion of a complete universe.

    Workflow:
    1. Load manifest
    2. Create Era tags in database
    3. Create Narrator entries
    4. Ingest works in order (with metadata injection)
    5. Log summary
    """

    def __init__(
        self,
        manifest_path: Path,
        vault_id: UUID,
        vault_path: Path,
        force_reindex: bool = False
    ):
        self.manifest_path = manifest_path
        self.vault_id = vault_id
        self.vault_path = vault_path
        self.force_reindex = force_reindex

        # Load manifest
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest_data = json.load(f)

        self.manifest = UniverseManifest(**manifest_data)

        logger.info(
            "universe_ingester_initialized",
            universe=self.manifest.universe_name,
            total_works=len(self.manifest.works),
            total_eras=len(self.manifest.eras),
            vault_id=str(vault_id)
        )

    async def ingest_universe(self) -> Dict[str, Any]:
        """
        Main entry point - ingest the entire universe.

        Returns:
            Dict with ingestion summary
        """
        logger.info(
            "universe_ingestion_started",
            universe=self.manifest.universe_name
        )

        results = {
            "universe_name": self.manifest.universe_name,
            "eras_created": 0,
            "narrators_created": 0,
            "works_ingested": 0,
            "total_chunks": 0,
            "errors": []
        }

        try:
            # Step 1: Create Era Tags
            results["eras_created"] = await self._create_era_tags()

            # Step 2: Create Narrator Entries
            results["narrators_created"] = await self._create_narrators()

            # Step 3: Ingest Works in Order
            sorted_works = self.manifest.get_sorted_works()

            for work in sorted_works:
                try:
                    chunks = await self._ingest_work(work)
                    results["works_ingested"] += 1
                    results["total_chunks"] += chunks

                    logger.info(
                        "work_ingested",
                        title=work.title,
                        chunks=chunks,
                        era=work.era_name,
                        ingestion_order=work.ingestion_order
                    )

                except Exception as e:
                    logger.error(
                        "work_ingestion_failed",
                        title=work.title,
                        error=str(e)
                    )
                    results["errors"].append({
                        "work": work.title,
                        "error": str(e)
                    })

            logger.info(
                "universe_ingestion_complete",
                universe=self.manifest.universe_name,
                works=results["works_ingested"],
                chunks=results["total_chunks"],
                errors=len(results["errors"])
            )

        except Exception as e:
            logger.error(
                "universe_ingestion_failed",
                universe=self.manifest.universe_name,
                error=str(e)
            )
            results["errors"].append({
                "stage": "universe_level",
                "error": str(e)
            })

        return results

    async def _create_era_tags(self) -> int:
        """
        Create EraTag entries for all eras in manifest.

        Returns:
            Number of eras created
        """
        created_count = 0

        with Session(engine) as session:
            for era_data in self.manifest.eras:
                # Check if era already exists
                existing = session.exec(
                    select(EraTag).where(
                        EraTag.vault_id == self.vault_id,
                        EraTag.name == era_data["name"]
                    )
                ).first()

                if existing:
                    logger.info(
                        "era_tag_exists",
                        era_name=era_data["name"]
                    )
                    continue

                # Create new era tag
                era_tag = EraTag(
                    vault_id=self.vault_id,
                    name=era_data["name"],
                    description=era_data.get("description"),
                    color=era_data.get("color"),
                    icon=era_data.get("icon"),
                    sequence_order=era_data.get("time_range", {}).get("start_year", 0)
                )

                session.add(era_tag)
                created_count += 1

                logger.info(
                    "era_tag_created",
                    era_name=era_data["name"],
                    sequence=era_tag.sequence_order
                )

            session.commit()

        return created_count

    async def _create_narrators(self) -> int:
        """
        Create Narrator entries for all narrators referenced in works.

        Returns:
            Number of narrators created
        """
        created_count = 0
        narrators_to_create = set()

        # Collect all unique narrators from works
        for work in self.manifest.works:
            if work.default_narrator:
                narrators_to_create.add((
                    work.default_narrator,
                    work.narrator_reliability.value
                ))

            # Also create narrators from metadata if present
            if work.metadata.get("primary_narrators"):
                for narrator_name in work.metadata["primary_narrators"]:
                    narrators_to_create.add((
                        narrator_name,
                        "unreliable"  # Assume unreliable for sub-narrators
                    ))

        with Session(engine) as session:
            for narrator_name, reliability in narrators_to_create:
                # Check if narrator already exists
                existing = session.exec(
                    select(Narrator).where(
                        Narrator.vault_id == self.vault_id,
                        Narrator.name == narrator_name
                    )
                ).first()

                if existing:
                    logger.info(
                        "narrator_exists",
                        narrator_name=narrator_name
                    )
                    continue

                # Map reliability to score
                reliability_map = {
                    "omniscient": 1.0,
                    "reliable": 0.9,
                    "unreliable": 0.5,
                    "conflicting": 0.3
                }

                # Create narrator
                narrator = Narrator(
                    vault_id=self.vault_id,
                    name=narrator_name,
                    narrator_type="third_person_omniscient" if "omniscient" in reliability.lower() else "first_person",
                    reliability_score=reliability_map.get(reliability, 0.7),
                    description=f"Narrator from {self.manifest.universe_name}"
                )

                session.add(narrator)
                created_count += 1

                logger.info(
                    "narrator_created",
                    narrator_name=narrator_name,
                    reliability=reliability
                )

            session.commit()

        return created_count

    async def _ingest_work(self, work: CanonWork) -> int:
        """
        Ingest a single work with metadata injection.

        Args:
            work: CanonWork definition from manifest

        Returns:
            Number of chunks created
        """
        # Construct full path
        work_path = self.vault_path / work.source_path

        if not work_path.exists():
            raise FileNotFoundError(f"Work path does not exist: {work_path}")

        # Prepare override metadata
        override_metadata = {
            "era_name": work.era_name,
            "era_sequence": work.era_sequence,
            "canon_layer": work.canon_layer,
            "has_unreliable_narrators": work.has_unreliable_narrators,
            "default_narrator": work.default_narrator,
            "narrator_reliability": work.narrator_reliability.value,
            "story_time_range": work.story_time_range,
            "ingestion_order": work.ingestion_order,
            **work.metadata
        }

        # Create VaultIndexer with override
        indexer = VaultIndexer(
            vault_path=str(self.vault_path),
            vault_id=self.vault_id,
            override_metadata=override_metadata
        )

        # Index the work
        if work_path.is_file():
            # Single file
            chunks = await indexer.index_file(work_path)
        else:
            # Directory - index all markdown files
            chunks = 0
            for md_file in work_path.rglob("*.md"):
                chunks += await indexer.index_file(md_file)

        logger.info(
            "work_indexed",
            title=work.title,
            path=str(work_path),
            chunks=chunks,
            era=work.era_name
        )

        return chunks


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest a multi-era universe using a manifest file"
    )
    parser.add_argument(
        "--manifest",
        type=str,
        required=True,
        help="Path to universe.json manifest"
    )
    parser.add_argument(
        "--vault-id",
        type=str,
        required=True,
        help="UUID of the vault"
    )
    parser.add_argument(
        "--vault-path",
        type=str,
        required=True,
        help="Path to vault root directory"
    )
    parser.add_argument(
        "--force-reindex",
        action="store_true",
        help="Force re-indexing of all works"
    )

    args = parser.parse_args()

    # Validate paths
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}")
        return

    vault_path = Path(args.vault_path)
    if not vault_path.exists():
        print(f"❌ Vault path not found: {vault_path}")
        return

    # Parse vault UUID
    try:
        vault_id = UUID(args.vault_id)
    except ValueError:
        print(f"❌ Invalid vault UUID: {args.vault_id}")
        return

    # Verify vault exists in database
    with Session(engine) as session:
        vault = session.get(Vault, vault_id)
        if not vault:
            print(f"❌ Vault not found in database: {vault_id}")
            return

    print(f"🚀 Starting universe ingestion...")
    print(f"   Manifest: {manifest_path}")
    print(f"   Vault: {vault.name} ({vault_id})")
    print(f"   Path: {vault_path}")
    print()

    # Run ingestion
    ingester = UniverseIngester(
        manifest_path=manifest_path,
        vault_id=vault_id,
        vault_path=vault_path,
        force_reindex=args.force_reindex
    )

    results = await ingester.ingest_universe()

    # Print summary
    print("\n" + "="*60)
    print(f"✅ INGESTION COMPLETE: {results['universe_name']}")
    print("="*60)
    print(f"   Eras Created: {results['eras_created']}")
    print(f"   Narrators Created: {results['narrators_created']}")
    print(f"   Works Ingested: {results['works_ingested']}")
    print(f"   Total Chunks: {results['total_chunks']}")

    if results["errors"]:
        print(f"\n⚠️  Errors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"   - {error}")
    else:
        print(f"\n✅ No errors")


if __name__ == "__main__":
    asyncio.run(main())
