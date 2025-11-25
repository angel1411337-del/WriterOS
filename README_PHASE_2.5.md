# Phase 2.5: Citadel Pipeline - Quick Reference

**Status**: ✅ COMPLETE (2025-11-25)

## What Is This?

Phase 2.5 adds **structured universe ingestion** to WriterOS, solving the entity disambiguation problem for complex multi-era stories like A Song of Ice and Fire.

**Before**: Ingesting "Aegon" created 5+ duplicate entities with no way to distinguish them.

**After**: System creates distinct entities for Aegon I, Aegon II, Aegon V, etc., with temporal metadata for disambiguation.

## Quick Start

### 1. Create Manifest

Create `my_universe.json`:

```json
{
  "universe_name": "My Story",
  "works": [
    {
      "title": "Prequel",
      "source_path": "Story_Bible/Prequel",
      "ingestion_order": 1,
      "era_name": "Ancient Era",
      "has_unreliable_narrators": false
    }
  ]
}
```

### 2. Run Ingestion

```bash
python -m writeros.scripts.ingest_universe \
    --manifest my_universe.json \
    --vault-id <vault-uuid> \
    --vault-path ~/vaults/my_vault
```

### 3. Query with Temporal Context

```python
from writeros.agents.profiler import ProfilerAgent

profiler = ProfilerAgent()

# Disambiguate "Aegon" at year 125
entity = await profiler.resolve_entity_by_era(
    name="Aegon",
    vault_id=vault_id,
    current_story_time={"year": 125}
)
```

## Key Features

✅ **Entity Disambiguation**: Distinguishes entities with same name across different eras
✅ **Chronological Ingestion**: Books ingested in story-time order
✅ **Unreliable Narrators**: Extracts conflicting claims (Mushroom vs. Septon Eustace)
✅ **Era Tagging**: Groups events into narrative phases
✅ **Metadata Injection**: Enriches documents with temporal context

## Files Created

- `src/writeros/schema/universe_manifest.py` - Manifest schema
- `src/writeros/scripts/ingest_universe.py` - Ingestion orchestrator
- `examples/asoiaf_universe.json` - ASOIAF example
- `tests/ingestion/test_universe_ingestion.py` - Test suite (22 tests)
- `docs/CITADEL_PIPELINE_GUIDE.md` - Developer guide
- `PHASE_2.5_COMPLETE.md` - Full documentation

## Files Modified

- `src/writeros/utils/indexer.py` - Added `override_metadata`, narrator extraction
- `src/writeros/agents/profiler.py` - Added entity disambiguation methods
- `src/writeros/schema/__init__.py` - Exports new schemas

## Documentation

- **Developer Guide**: `docs/CITADEL_PIPELINE_GUIDE.md`
- **Complete Summary**: `PHASE_2.5_COMPLETE.md`
- **Example Manifest**: `examples/asoiaf_universe.json`

## Testing

```bash
# Run all tests
pytest tests/ingestion/test_universe_ingestion.py -v

# Run specific test
pytest tests/ingestion/test_universe_ingestion.py::TestEntityDisambiguation -v
```

## Next Steps

**Phase 3**: Retrieval filtering with narrator reliability, POV boundaries, and conflict resolution.

## Problems Solved

1. ✅ **Entity Duplication**: No more duplicate "Aegon" entities
2. ✅ **Temporal Ambiguity**: System knows which "King" at which time
3. ✅ **Lost Context**: Maintains chronological ingestion order
4. ✅ **Unreliable Narrators**: Tracks conflicting accounts

## Example Use Cases

- **ASOIAF**: Distinguish Aegon I, II, III, V, VI
- **Wheel of Time**: Track Dragon Reborn reincarnations
- **Dune**: Distinguish Paul, Leto II, etc.
- **Any multi-era fantasy**: Historical vs. current timeline

## Success Criteria - ALL MET ✅

- ✅ Manifest schema defined
- ✅ Ingestion script works
- ✅ Entity disambiguation by era
- ✅ Narrator claim extraction
- ✅ Metadata injection
- ✅ 22 tests passing
- ✅ Documentation complete

---

**Questions?** See `PHASE_2.5_COMPLETE.md` for full details.
