# Citadel Pipeline Developer Guide

**Phase 2.5** - Structured Universe Ingestion

## Quick Start

### 1. Create a Universe Manifest

```json
{
  "universe_name": "My Universe",
  "version": "1.0",
  "eras": [
    {
      "name": "Ancient Times",
      "description": "The beginning",
      "time_range": {"start_year": 0, "end_year": 100},
      "color": "#FF0000",
      "icon": "🏛️"
    }
  ],
  "works": [
    {
      "title": "Book One",
      "source_path": "Story_Bible/Book_01",
      "ingestion_order": 1,
      "story_time_range": {"start_year": 0, "end_year": 50},
      "era_name": "Ancient Times",
      "era_sequence": 1,
      "has_unreliable_narrators": false,
      "default_narrator": "Omniscient",
      "narrator_reliability": "omniscient",
      "canon_layer": "primary",
      "metadata": {}
    }
  ]
}
```

### 2. Run Ingestion

```bash
python -m writeros.scripts.ingest_universe \
    --manifest my_universe.json \
    --vault-id <uuid> \
    --vault-path ~/vaults/my_vault
```

### 3. Query with Temporal Context

```python
from writeros.agents.profiler import ProfilerAgent

profiler = ProfilerAgent()

# Resolve entity by era
entity = await profiler.resolve_entity_by_era(
    name="Character Name",
    vault_id=vault_id,
    current_story_time={"year": 25}
)
```

## Core Concepts

### Ingestion Order

**Critical**: Books MUST be ingested in story-chronological order, not publication order.

**Why?** Entity disambiguation depends on temporal metadata. If you ingest Book 5 before Book 1, the system won't know which "King Arthur" came first.

**Example** (ASOIAF):

✅ **CORRECT ORDER** (story time):
1. Fire & Blood (1-300 AC)
2. Dunk & Egg (208-212 AC)
3. A Game of Thrones (298-299 AC)

❌ **WRONG ORDER** (publication):
1. A Game of Thrones (1996)
2. The Hedge Knight (1998)
3. Fire & Blood (2018)

### Entity Disambiguation

The system distinguishes entities with the same name using `era_start_year` and `era_end_year`.

**Example**:

```json
{
  "expected_entities": [
    {
      "name": "Aegon",
      "type": "character",
      "era_start_year": 1,
      "era_end_year": 37,
      "aliases": ["Aegon I", "The Conqueror"]
    }
  ]
}
```

When the system encounters "Aegon" at `story_time={"year": 20}`, it resolves to this entity because 1 ≤ 20 ≤ 37.

### Unreliable Narrators

Set `has_unreliable_narrators: true` to extract narrator claims.

**Patterns Detected**:

1. **"X claims that Y"**
   ```
   Mushroom claims that the queen wore red.
   → {narrator: "Mushroom", claim: "the queen wore red"}
   ```

2. **"According to X, Y"**
   ```
   According to Septon Eustace, the battle lasted three days.
   → {narrator: "Septon Eustace", claim: "the battle lasted three days"}
   ```

3. **"X's account states Y"**
   ```
   Grand Maester Munkun's account states the king was poisoned.
   → {narrator: "Grand Maester Munkun", claim: "the king was poisoned"}
   ```

## API Reference

### `UniverseIngester`

Orchestrates universe ingestion.

```python
from writeros.scripts.ingest_universe import UniverseIngester

ingester = UniverseIngester(
    manifest_path=Path("universe.json"),
    vault_id=vault_id,
    vault_path=Path("/vault"),
    force_reindex=False
)

results = await ingester.ingest_universe()
# Returns: {
#   "universe_name": "...",
#   "eras_created": 3,
#   "narrators_created": 5,
#   "works_ingested": 10,
#   "total_chunks": 1247,
#   "errors": []
# }
```

### `ProfilerAgent.resolve_entity_by_era()`

Disambiguates entities by temporal context.

```python
entity = await profiler.resolve_entity_by_era(
    name="Aegon",
    vault_id=vault_id,
    current_story_time={"year": 125},
    current_scene_id=None  # Optional
)
# Returns: Entity object or None
```

**Logic**:

1. Find all entities with `name="Aegon"` in vault
2. If `current_story_time` provided:
   - Check each entity's `metadata_.era_start_year` and `era_end_year`
   - Return entity where `era_start_year ≤ current_year ≤ era_end_year`
3. Fallback: Return most recently created entity

### `ProfilerAgent.find_or_create_entity()`

Prevents duplicate entities during ingestion.

```python
entity = await profiler.find_or_create_entity(
    name="Aegon",
    entity_type=EntityType.CHARACTER,
    vault_id=vault_id,
    description="The Conqueror",
    override_metadata={
        "era_start_year": 1,
        "era_end_year": 37
    },
    current_story_time={"year": 20}
)
# Returns: Existing entity if found, new entity otherwise
```

**Workflow**:

1. Call `resolve_entity_by_era()` to check for existing entity
2. If found, return existing entity ✅ NO DUPLICATE
3. If not found, create new entity with metadata

### `VaultIndexer` with Override Metadata

Injects metadata into document chunks.

```python
from writeros.utils.indexer import VaultIndexer

indexer = VaultIndexer(
    vault_path="/path",
    vault_id=vault_id,
    override_metadata={
        "era_name": "Targaryen Dynasty",
        "canon_layer": "primary",
        "has_unreliable_narrators": True,
        "ingestion_order": 1
    }
)

chunks = await indexer.index_file(Path("file.md"))
```

**Result**: All chunks will have this metadata in `metadata_` field.

### `VaultIndexer.extract_narrator_claims()`

Extracts narrator attributions from text.

```python
claims = indexer.extract_narrator_claims(text)
# Returns: [
#   {
#     "narrator": "Mushroom",
#     "claim": "the queen wore red",
#     "pattern": "claims_that"
#   }
# ]
```

## Manifest Schema Reference

### Top Level

```typescript
{
  universe_name: string,
  version: string,
  eras: Era[],
  works: CanonWork[],
  disambiguation_rules?: object,
  metadata?: object
}
```

### Era

```typescript
{
  name: string,
  description?: string,
  time_range: {start_year: number, end_year: number},
  color?: string,  // Hex color for UI
  icon?: string    // Emoji icon
}
```

### CanonWork

```typescript
{
  title: string,
  source_path: string,  // Relative to vault root
  ingestion_order: number,  // 1-indexed, chronological
  story_time_range?: {start_year: number, end_year: number},
  era_name: string,
  era_sequence: number,
  has_unreliable_narrators: boolean,
  default_narrator?: string,
  narrator_reliability: "omniscient" | "reliable" | "unreliable" | "conflicting",
  expected_entities?: ExpectedEntity[],
  canon_layer: "primary" | "alternate" | "supplemental" | "non_canon",
  metadata?: object
}
```

### ExpectedEntity

```typescript
{
  name: string,
  type: "character" | "location" | "organization" | "item",
  era_start_year: number,
  era_end_year: number,
  aliases?: string[]
}
```

## Best Practices

### 1. Define All Major Entities

**Do This**:

```json
{
  "expected_entities": [
    {
      "name": "Aegon I",
      "era_start_year": 1,
      "era_end_year": 37,
      "aliases": ["The Conqueror", "Aegon the Dragon"]
    },
    {
      "name": "Aegon II",
      "era_start_year": 120,
      "era_end_year": 131,
      "aliases": ["The Usurper"]
    }
  ]
}
```

**Why?** Helps the system create entities with correct metadata from the start.

### 2. Use Chronological Ingestion Order

**Do This**:

```json
{
  "works": [
    {"title": "Fire & Blood", "ingestion_order": 1},
    {"title": "Dunk & Egg", "ingestion_order": 2},
    {"title": "AGOT", "ingestion_order": 3}
  ]
}
```

**Don't Do This**:

```json
{
  "works": [
    {"title": "AGOT", "ingestion_order": 1},  ❌ Wrong!
    {"title": "Fire & Blood", "ingestion_order": 2}
  ]
}
```

### 3. Mark Unreliable Narrators

**Do This**:

```json
{
  "title": "Fire & Blood",
  "has_unreliable_narrators": true,
  "default_narrator": "Archmaester Gyldayn",
  "metadata": {
    "primary_narrators": ["Mushroom", "Septon Eustace", "Grand Maester Munkun"]
  }
}
```

**Why?** Enables narrator claim extraction for conflict resolution.

### 4. Use Consistent Era Names

**Do This**:

```json
{
  "eras": [
    {"name": "Targaryen Dynasty", ...}
  ],
  "works": [
    {"era_name": "Targaryen Dynasty", ...}
  ]
}
```

**Don't Do This**:

```json
{
  "eras": [
    {"name": "Targaryen Dynasty", ...}
  ],
  "works": [
    {"era_name": "Targaryen Era", ...}  ❌ Mismatch!
  ]
}
```

## Common Patterns

### Pattern 1: Multi-Book Series

```json
{
  "works": [
    {
      "title": "Book 1",
      "ingestion_order": 1,
      "story_time_range": {"start_year": 0, "end_year": 5}
    },
    {
      "title": "Book 2",
      "ingestion_order": 2,
      "story_time_range": {"start_year": 5, "end_year": 10}
    },
    {
      "title": "Book 3",
      "ingestion_order": 3,
      "story_time_range": {"start_year": 10, "end_year": 15}
    }
  ]
}
```

### Pattern 2: Prequels

```json
{
  "works": [
    {
      "title": "Prequel (happens first)",
      "ingestion_order": 1,  // Ingest FIRST
      "story_time_range": {"start_year": 0, "end_year": 50}
    },
    {
      "title": "Main Series (happens later)",
      "ingestion_order": 2,  // Ingest SECOND
      "story_time_range": {"start_year": 100, "end_year": 200}
    }
  ]
}
```

### Pattern 3: Flashback-Heavy Narratives

```json
{
  "works": [
    {
      "title": "Present Day Chapters",
      "ingestion_order": 2,  // Ingest AFTER flashbacks
      "story_time_range": {"start_year": 100, "end_year": 100}
    },
    {
      "title": "Flashback Arc",
      "ingestion_order": 1,  // Ingest FIRST (chronological)
      "story_time_range": {"start_year": 50, "end_year": 60}
    }
  ]
}
```

## Troubleshooting

### Issue: Duplicate Entities Created

**Symptom**: Multiple entities with same name, no temporal disambiguation.

**Cause**: Missing `era_start_year` and `era_end_year` in entity metadata.

**Fix**: Add to manifest:

```json
{
  "expected_entities": [
    {
      "name": "Character",
      "era_start_year": 10,  // ✅ Add this
      "era_end_year": 50      // ✅ And this
    }
  ]
}
```

### Issue: Narrator Claims Not Extracted

**Symptom**: `narrator_claims` field empty in document metadata.

**Cause**: `has_unreliable_narrators: false` or patterns don't match.

**Fix**:

1. Set `has_unreliable_narrators: true` in manifest
2. Check text matches one of these patterns:
   - "X claims that Y"
   - "According to X, Y"
   - "X's account states Y"

### Issue: Works Ingested in Wrong Order

**Symptom**: Entity disambiguation fails, wrong entities returned.

**Cause**: Manifest `ingestion_order` not chronological.

**Fix**: Re-order works by story timeline, not publication date:

```json
{
  "works": [
    {"title": "Prequel", "ingestion_order": 1},  // First in story
    {"title": "Main Series", "ingestion_order": 2}  // Later in story
  ]
}
```

## Testing

### Unit Tests

```bash
# Run all ingestion tests
pytest tests/ingestion/test_universe_ingestion.py -v

# Run specific test
pytest tests/ingestion/test_universe_ingestion.py::TestEntityDisambiguation::test_resolve_entity_by_era_multiple_matches -v
```

### Manual Testing

```python
# 1. Create test vault
vault = Vault(name="Test Vault", user_id=uuid4())
session.add(vault)
session.commit()

# 2. Run ingestion
ingester = UniverseIngester(
    manifest_path=Path("test_manifest.json"),
    vault_id=vault.id,
    vault_path=Path("/tmp/test_vault")
)
results = await ingester.ingest_universe()

# 3. Verify entities
entities = session.exec(
    select(Entity).where(Entity.vault_id == vault.id)
).all()

print(f"Created {len(entities)} entities")

# 4. Test disambiguation
aegon = await profiler.resolve_entity_by_era(
    name="Aegon",
    vault_id=vault.id,
    current_story_time={"year": 125}
)

print(f"Resolved to: {aegon.name} ({aegon.metadata_.get('era_start_year')}-{aegon.metadata_.get('era_end_year')})")
```

## Next Steps

After successful ingestion:

1. **Verify Data**: Check database for era tags, narrators, entities
2. **Test Queries**: Use temporal context in retrieval
3. **Implement Phase 3**: Retrieval filtering (dream filtering, POV boundaries)

## References

- **Full Documentation**: `PHASE_2.5_COMPLETE.md`
- **Example Manifest**: `examples/asoiaf_universe.json`
- **Test Suite**: `tests/ingestion/test_universe_ingestion.py`
- **Schema**: `src/writeros/schema/universe_manifest.py`
