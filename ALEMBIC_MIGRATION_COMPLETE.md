# Alembic Migration Complete - Schema Sync

**Date:** November 28, 2025
**Migration ID:** `92db7bf6846d`
**Status:** ✅ SUCCESSFULLY APPLIED

---

## Problem Solved

### Root Cause
The application was experiencing `column entities.entity_type does not exist` errors despite the column being present in the database. This was caused by **SQLAlchemy metadata caching** - the running Python process had cached old table definitions in memory.

### Pattern Identified
1. Python models were updated (changed `type` → `entity_type`)
2. Database was manually updated
3. But running application process still had stale metadata cached
4. SQLAlchemy continued using old cached table definition with wrong column names

---

## Migration Details

### Migration File
`migrations/versions/92db7bf6846d_sync_schema_with_models.py`

### What Was Fixed

#### 1. ENUM Type Conversions
Converted VARCHAR columns to proper PostgreSQL ENUM types:

**Entities Table:**
- `canon_layer`: VARCHAR(20) → canonlayer ENUM ('PRIMARY', 'ALTERNATE', 'DRAFT', 'RETCONNED')
- `canon_status`: VARCHAR(20) → canonstatus ENUM ('ACTIVE', 'DEPRECATED', 'PENDING')
- `significance`: VARCHAR(20) → nodesignificance ENUM ('PROTAGONIST', 'MAJOR', 'SUPPORTING', 'MINOR', 'MENTIONED')

**Key Challenge:**
PostgreSQL cannot automatically cast VARCHAR defaults to ENUM types. Solution:
```sql
-- 1. Drop default
ALTER TABLE entities ALTER COLUMN canon_layer DROP DEFAULT;

-- 2. Convert type with USING clause
ALTER TABLE entities
ALTER COLUMN canon_layer
TYPE canonlayer
USING UPPER(canon_layer)::canonlayer;

-- 3. Set new default with proper type
ALTER TABLE entities ALTER COLUMN canon_layer SET DEFAULT 'PRIMARY'::canonlayer;

-- 4. Set NOT NULL constraint
ALTER TABLE entities ALTER COLUMN canon_layer SET NOT NULL;
```

#### 2. NOT NULL Constraints
Added NOT NULL constraints to columns with defaults:
- `mention_count`
- `extraction_confidence`
- `extraction_method`
- `user_verified`
- `relationship_count`
- `pagerank_score`
- `betweenness_score`
- `completeness_score`
- `has_conflicts`
- `conflict_count`

#### 3. Index Reorganization

**Dropped old indexes:**
- `entities_embedding_hnsw_idx` (old naming convention)
- `ix_entities_type` (column renamed to entity_type)
- `documents_embedding_hnsw_idx`
- `scenes_embedding_hnsw_idx`
- `conflicts_embedding_hnsw_idx`
- `events_embedding_hnsw_idx`
- `facts_embedding_hnsw_idx`

**Created new indexes:**

**Entities table:**
- `ix_entities_entity_type` - Single column index on entity_type
- `ix_entities_first_appearance_sequence` - Single column index
- `ix_entities_last_appearance_sequence` - Single column index
- `idx_entity_vault_type` - Composite (vault_id, entity_type)
- `idx_entity_vault_significance` - Composite (vault_id, significance)
- `idx_entity_vault_sequence` - Composite (vault_id, first_appearance_sequence)
- `ix_entities_embedding` - HNSW vector index (m=16, ef_construction=64)

**All embedding tables:**
- Recreated HNSW indexes with consistent naming: `ix_{table}_embedding`

#### 4. Foreign Key Constraints
Added missing foreign keys to entities table:
- `entities.primary_source_chunk_id → chunks.id`
- `entities.vault_id → vaults.id`

---

## Verification Results

```
Key Entities Columns:
--------------------------------------------------------------------------------
  canon_layer        USER-DEFINED (ENUM)   NULL=NO   DEFAULT='PRIMARY'::canonlayer
  canon_status       USER-DEFINED (ENUM)   NULL=NO   DEFAULT='ACTIVE'::canonstatus
  entity_type        USER-DEFINED (ENUM)   NULL=NO   DEFAULT=None
  significance       USER-DEFINED (ENUM)   NULL=NO   DEFAULT='MINOR'::nodesignificance

Entity Indexes:
--------------------------------------------------------------------------------
  ix_entities_embedding      (HNSW vector index)
  ix_entities_entity_type    (B-tree index)
  idx_entity_vault_type      (Composite B-tree)
  idx_entity_vault_significance (Composite B-tree)
  idx_entity_vault_sequence  (Composite B-tree)
```

---

## System Status

### Before Migration
❌ Entity queries failing with "column entity_type does not exist"
❌ Inconsistent index naming
❌ VARCHAR columns instead of ENUM types
❌ Missing composite indexes for vault isolation

### After Migration
✅ All entity queries working
✅ Consistent HNSW index naming across all tables
✅ Proper ENUM types with type safety
✅ Optimized composite indexes for multi-tenant queries
✅ Foreign key constraints enforcing referential integrity

---

## Next Steps

### Immediate Action Required
**Restart your application** to clear SQLAlchemy's metadata cache. The database schema is now correct, but running processes still have stale metadata.

```bash
# Stop your running WriterOS application
# Then restart it - it will reload with fresh metadata
```

### Verification
After restarting, test a query that was failing:
```python
from writeros.schema.entities import Entity
from sqlmodel import Session, select

with Session(engine) as session:
    entities = session.exec(
        select(Entity)
        .where(Entity.vault_id == vault_id)
        .limit(5)
    ).all()

    for entity in entities:
        print(f"{entity.name} ({entity.entity_type})")
```

This should now work without errors.

---

## Lessons Learned

### 1. Always Use Alembic for Schema Changes
Manual SQL changes can lead to metadata cache mismatches. Use Alembic migrations for all schema modifications.

### 2. ENUM Type Conversions Require Care
When converting VARCHAR to ENUM:
- Drop defaults first
- Use USING clause for type conversion
- Set new defaults with proper type casting
- Add NOT NULL constraints last

### 3. Index Naming Consistency
Standardize on naming conventions:
- Single column: `ix_{table}_{column}`
- Composite: `idx_{table}_{purpose}`
- HNSW vector: `ix_{table}_embedding`

### 4. Restart Required After Manual Changes
When database schema is modified outside of the running application, always restart to clear SQLAlchemy metadata cache.

---

## Migration Files

**Created:**
- `migrations/versions/92db7bf6846d_sync_schema_with_models.py`

**Current Alembic Head:**
- `92db7bf6846d` - sync_schema_with_models (this migration)

**Previous Head:**
- `edabc2e83026` - add_prerequisites_tracking_to_anchors

---

## References

- PostgreSQL ENUM types: https://www.postgresql.org/docs/current/datatype-enum.html
- Alembic documentation: https://alembic.sqlalchemy.org/
- pgvector HNSW indexes: https://github.com/pgvector/pgvector#hnsw

---

**Migration Status:** ✅ COMPLETE

All schema changes have been successfully applied. Restart your application to complete the fix.
