"""sync_schema_with_models

Revision ID: 92db7bf6846d
Revises: edabc2e83026
Create Date: 2025-11-28 00:17:35.744841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92db7bf6846d'
down_revision: Union[str, Sequence[str], None] = 'edabc2e83026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Sync database schema with current Python models.

    Key changes:
    1. Entities table: Convert VARCHAR columns to proper ENUM types
    2. Entities table: Add missing indexes
    3. Relationships table: Migrate old schema to new schema
    4. Recreate HNSW indexes with proper naming convention
    """

    # ============================================
    # STEP 1: Create ENUM types if they don't exist
    # ============================================
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE canonlayer AS ENUM ('PRIMARY', 'ALTERNATE', 'DRAFT', 'RETCONNED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE canonstatus AS ENUM ('ACTIVE', 'DEPRECATED', 'PENDING');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE nodesignificance AS ENUM ('PROTAGONIST', 'MAJOR', 'SUPPORTING', 'MINOR', 'MENTIONED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # ============================================
    # STEP 2: Entities table - Convert VARCHAR to ENUM with USING clause
    # ============================================

    # canon_layer: VARCHAR -> canonlayer ENUM
    # Drop default first, convert type, then set default with proper type
    op.execute("ALTER TABLE entities ALTER COLUMN canon_layer DROP DEFAULT")
    op.execute("""
        ALTER TABLE entities
        ALTER COLUMN canon_layer
        TYPE canonlayer
        USING UPPER(canon_layer)::canonlayer
    """)
    op.execute("ALTER TABLE entities ALTER COLUMN canon_layer SET DEFAULT 'PRIMARY'::canonlayer")
    op.execute("ALTER TABLE entities ALTER COLUMN canon_layer SET NOT NULL")

    # canon_status: VARCHAR -> canonstatus ENUM
    op.execute("ALTER TABLE entities ALTER COLUMN canon_status DROP DEFAULT")
    op.execute("""
        ALTER TABLE entities
        ALTER COLUMN canon_status
        TYPE canonstatus
        USING UPPER(canon_status)::canonstatus
    """)
    op.execute("ALTER TABLE entities ALTER COLUMN canon_status SET DEFAULT 'ACTIVE'::canonstatus")
    op.execute("ALTER TABLE entities ALTER COLUMN canon_status SET NOT NULL")

    # significance: VARCHAR -> nodesignificance ENUM
    op.execute("ALTER TABLE entities ALTER COLUMN significance DROP DEFAULT")
    op.execute("""
        ALTER TABLE entities
        ALTER COLUMN significance
        TYPE nodesignificance
        USING UPPER(significance)::nodesignificance
    """)
    op.execute("ALTER TABLE entities ALTER COLUMN significance SET DEFAULT 'MINOR'::nodesignificance")
    op.execute("ALTER TABLE entities ALTER COLUMN significance SET NOT NULL")

    # ============================================
    # STEP 3: Entities table - Set NOT NULL on columns with defaults
    # ============================================

    op.execute("ALTER TABLE entities ALTER COLUMN mention_count SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN extraction_confidence SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN extraction_method SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN user_verified SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN relationship_count SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN pagerank_score SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN betweenness_score SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN completeness_score SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN has_conflicts SET NOT NULL")
    op.execute("ALTER TABLE entities ALTER COLUMN conflict_count SET NOT NULL")

    # ============================================
    # STEP 4: Entities table - Drop old indexes, create new ones
    # ============================================

    # Drop old HNSW index (will recreate with new naming convention)
    op.execute("DROP INDEX IF EXISTS entities_embedding_hnsw_idx")
    op.execute("DROP INDEX IF EXISTS ix_entities_embedding")

    # Drop old type index (column was renamed to entity_type)
    op.execute("DROP INDEX IF EXISTS ix_entities_type")

    # Create new composite indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_vault_type
        ON entities (vault_id, entity_type)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_vault_significance
        ON entities (vault_id, significance)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_entity_vault_sequence
        ON entities (vault_id, first_appearance_sequence)
    """)

    # Create new single-column indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_entities_entity_type
        ON entities (entity_type)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_entities_first_appearance_sequence
        ON entities (first_appearance_sequence)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_entities_last_appearance_sequence
        ON entities (last_appearance_sequence)
    """)

    # Recreate HNSW index with proper naming
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_entities_embedding
        ON entities
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # ============================================
    # STEP 5: Add foreign key constraints if missing
    # ============================================

    # Check and add foreign keys
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'entities_primary_source_chunk_id_fkey'
            ) THEN
                ALTER TABLE entities
                ADD CONSTRAINT entities_primary_source_chunk_id_fkey
                FOREIGN KEY (primary_source_chunk_id)
                REFERENCES chunks(id);
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'entities_vault_id_fkey'
            ) THEN
                ALTER TABLE entities
                ADD CONSTRAINT entities_vault_id_fkey
                FOREIGN KEY (vault_id)
                REFERENCES vaults(id);
            END IF;
        END $$;
    """)

    # ============================================
    # STEP 6: Recreate HNSW indexes for other tables
    # ============================================

    # Documents
    op.execute("DROP INDEX IF EXISTS documents_embedding_hnsw_idx")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_documents_embedding
        ON documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Scenes
    op.execute("DROP INDEX IF EXISTS scenes_embedding_hnsw_idx")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_scenes_embedding
        ON scenes
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Conflicts
    op.execute("DROP INDEX IF EXISTS conflicts_embedding_hnsw_idx")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_conflicts_embedding
        ON conflicts
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Events
    op.execute("DROP INDEX IF EXISTS events_embedding_hnsw_idx")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_events_embedding
        ON events
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Facts
    op.execute("DROP INDEX IF EXISTS facts_embedding_hnsw_idx")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_facts_embedding
        ON facts
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    """
    Downgrade schema (convert ENUMs back to VARCHAR).
    Note: This is a lossy operation and should be used with caution.
    """

    # Revert ENUM types to VARCHAR
    op.execute("""
        ALTER TABLE entities
        ALTER COLUMN canon_layer
        TYPE VARCHAR(20)
        USING canon_layer::text
    """)

    op.execute("""
        ALTER TABLE entities
        ALTER COLUMN canon_status
        TYPE VARCHAR(20)
        USING canon_status::text
    """)

    op.execute("""
        ALTER TABLE entities
        ALTER COLUMN significance
        TYPE VARCHAR(20)
        USING significance::text
    """)

    # Drop new indexes
    op.execute("DROP INDEX IF EXISTS idx_entity_vault_type")
    op.execute("DROP INDEX IF EXISTS idx_entity_vault_significance")
    op.execute("DROP INDEX IF EXISTS idx_entity_vault_sequence")
    op.execute("DROP INDEX IF EXISTS ix_entities_entity_type")
    op.execute("DROP INDEX IF EXISTS ix_entities_first_appearance_sequence")
    op.execute("DROP INDEX IF EXISTS ix_entities_last_appearance_sequence")
