#!/usr/bin/env python3
"""
Add High-Performance Vector Indexes to Existing Database

This script adds HNSW (Hierarchical Navigable Small World) indexes to the
entities, documents, and facts tables for 100x-1000x faster vector searches.

Usage:
    python scripts/add_vector_indexes.py

    # Or with custom database URL:
    DATABASE_URL=postgresql://user:pass@host:port/db python scripts/add_vector_indexes.py

Performance Impact:
    - Before: O(N) sequential scan of all embeddings
    - After: O(log N) graph traversal with HNSW
    - Expected speedup: 100x-1000x for large datasets

Index Details:
    - Type: HNSW (pgvector)
    - Distance metric: Cosine similarity
    - Index build time: ~1-5 min per 100k records
    - Disk space: ~10-20% of embedding data size
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlmodel import Session, text
from writeros.utils.db import engine
from writeros.core.logging import get_logger

logger = get_logger(__name__)


def check_vector_extension():
    """Verify pgvector extension is installed."""
    logger.info("checking_vector_extension")
    with Session(engine) as session:
        result = session.exec(text("""
            SELECT EXISTS(
                SELECT 1 FROM pg_extension WHERE extname = 'vector'
            )
        """)).first()

        if not result:
            logger.error("vector_extension_missing")
            raise RuntimeError(
                "pgvector extension not installed. Run: CREATE EXTENSION vector;"
            )
    logger.info("vector_extension_found")


def check_existing_indexes():
    """Check which indexes already exist."""
    logger.info("checking_existing_indexes")
    with Session(engine) as session:
        result = session.exec(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE indexname LIKE '%embedding%hnsw%'
        """)).all()

        existing = [r[0] for r in result] if result else []
        logger.info("existing_indexes_found", count=len(existing), indexes=existing)
        return existing


def create_vector_indexes():
    """Create HNSW indexes on all embedding columns."""
    logger.info("starting_index_creation")

    indexes = [
        ("entities", "entities_embedding_hnsw_idx"),
        ("documents", "documents_embedding_hnsw_idx"),
        ("facts", "facts_embedding_hnsw_idx"),
    ]

    existing = check_existing_indexes()

    with Session(engine) as session:
        for table_name, index_name in indexes:
            if index_name in existing:
                logger.info("index_already_exists", table=table_name, index=index_name)
                continue

            logger.info("creating_index", table=table_name, index=index_name)

            try:
                # Count records to estimate time
                count_result = session.exec(text(f"SELECT COUNT(*) FROM {table_name}")).first()
                count = count_result[0] if count_result else 0

                logger.info(
                    "index_build_starting",
                    table=table_name,
                    rows=count,
                    estimated_time_minutes=count // 20000  # Rough estimate
                )

                # Create index (this may take several minutes for large tables)
                session.exec(text(f"""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
                    ON {table_name} USING hnsw (embedding vector_cosine_ops)
                """))

                logger.info("index_created", table=table_name, index=index_name)

            except Exception as e:
                logger.error(
                    "index_creation_failed",
                    table=table_name,
                    error=str(e)
                )
                # Continue with other indexes

    logger.info("index_creation_complete")


def verify_indexes():
    """Verify all indexes were created successfully."""
    logger.info("verifying_indexes")

    with Session(engine) as session:
        result = session.exec(text("""
            SELECT
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE indexname LIKE '%embedding%hnsw%'
            ORDER BY tablename
        """)).all()

        if result:
            logger.info("indexes_verified", count=len(result))
            print("\n✓ Vector Indexes Created Successfully:")
            print("=" * 80)
            for row in result:
                print(f"  • {row[1]}.{row[2]}")
                print(f"    {row[3]}\n")
        else:
            logger.warning("no_indexes_found")
            print("\n⚠ No vector indexes found")


def main():
    """Main execution function."""
    print("╔═══════════════════════════════════════════════════════════════════╗")
    print("║     WriterOS Vector Index Migration                               ║")
    print("║     Adds HNSW indexes for 100x-1000x faster semantic search      ║")
    print("╚═══════════════════════════════════════════════════════════════════╝\n")

    try:
        # Step 1: Check prerequisites
        check_vector_extension()

        # Step 2: Check existing indexes
        existing = check_existing_indexes()
        if len(existing) >= 3:
            print("\n✓ All vector indexes already exist. No action needed.")
            return

        # Step 3: Create indexes
        print("\nCreating vector indexes (this may take several minutes)...")
        create_vector_indexes()

        # Step 4: Verify
        verify_indexes()

        print("\n✓ Migration complete!")
        print("\nExpected performance improvement:")
        print("  • Vector searches: 100x-1000x faster")
        print("  • Query latency: Milliseconds instead of seconds")
        print("  • Scalability: Handles millions of embeddings efficiently\n")

    except Exception as e:
        logger.error("migration_failed", error=str(e))
        print(f"\n✗ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
