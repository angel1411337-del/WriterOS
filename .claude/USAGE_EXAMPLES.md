# Graph Retrieval Enhancement Usage Examples

**Last Updated:** 2025-11-28
**Related Docs:** `TDD_IMPLEMENTATION_SUMMARY.md`, `GRAPH_ENHANCED_RETRIEVAL.md`

---

## Quick Start

```python
from writeros.rag.graph_retrieval import retrieve_chunks_with_advanced_graph
from writeros.schema.enums import RelationType

# Basic usage (same as original function)
chunks = await retrieve_chunks_with_advanced_graph(
    query="Who are Ned Stark's children?",
    vault_id=vault_id,
    k=5
)
```

---

## Example 1: Family Tree Query

**Use Case:** Find family members without noise from other relationship types

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="Who are Ned Stark's children?",
    vault_id=vault_id,
    k=5,
    relationship_types=[RelationType.PARENT],  # Only parent-child relationships
    max_hops=1  # Direct children only (not grandchildren)
)

# Result: Only chunks mentioning Robb, Sansa, Arya, Bran, Rickon, Jon
```

**Why it works:**
- `RelationshipTypeFilter` excludes FRIEND, ALLY, etc.
- `max_hops=1` prevents traversing to grandchildren
- Higher relevance scores for actual family members

---

## Example 2: Political Network (2-hop with Temporal Filter)

**Use Case:** Find political allies mentioned in early chapters (avoid spoilers)

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="Who are House Stark's political allies?",
    vault_id=vault_id,
    k=10,
    relationship_types=[RelationType.ALLY, RelationType.VASSAL, RelationType.FRIEND],
    max_hops=2,  # Include allies-of-allies
    temporal_mode="sequence",
    max_sequence=20,  # Only chapters 1-20
)

# Result: House Tully, House Arryn, House Manderly, etc.
# Excludes: Spoiler alliances from later chapters
```

**Why it works:**
- `RelationshipTypeFilter` focuses on political relationships
- `TemporalGraphFilter` prevents future spoilers
- `max_hops=2` finds indirect alliances (e.g., via House Tully)

---

## Example 3: Active Relationships at Specific Point

**Use Case:** "Who is allied with Ned at Chapter 15?"

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="Who is allied with Ned Stark?",
    vault_id=vault_id,
    k=5,
    relationship_types=[RelationType.ALLY],
    temporal_mode="sequence",
    current_sequence=15,  # Active at chapter 15
)

# Result: Only relationships that:
# - Were established by chapter 15 (established_at_sequence <= 15)
# - Had not ended before chapter 15 (ended_at_sequence >= 15 OR null)
```

**Why it works:**
- `TemporalGraphFilter(current_sequence=15)` checks both establishment and ending
- Automatically filters out relationships that formed later or ended earlier

---

## Example 4: Entity Importance Weighting (PageRank)

**Use Case:** Prioritize chunks mentioning central characters

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="Tell me about the power struggles in Westeros",
    vault_id=vault_id,
    k=10,
    use_pagerank=True,  # Enable PageRank scoring
    max_hops=2
)

# PageRank computation:
# 1. Builds graph of all entities and relationships
# 2. Computes centrality scores (e.g., Ned Stark = 0.8, minor character = 0.2)
# 3. Multiplies boost by (1 + pagerank_score)
#    - Ned Stark mention: boost * 1.8
#    - Minor character mention: boost * 1.2

# Result: Chunks about major characters ranked higher
```

**Why it works:**
- PageRank identifies "hubs" in the relationship graph
- More connected entities (protagonists) get higher importance scores
- Boost formula: `boost * (1 + pagerank_score)` gives 1.0-2.0x multiplier

**Performance:**
- Small graphs (50 entities): ~100ms
- Medium graphs (200 entities): ~250ms
- Large graphs (1000 entities): ~500ms

---

## Example 5: Explainable Retrieval (Path Tracking)

**Use Case:** Understand WHY a chunk was retrieved

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="How is Robert Baratheon connected to Ned Stark?",
    vault_id=vault_id,
    k=5,
    track_paths=True,  # Enable path tracking
    max_hops=2
)

# Paths tracked:
# Robert Baratheon → Ned Stark
#   Path 1: [FRIEND, strength=0.9] (direct)
#   Path 2: [ALLY, strength=0.85] (direct)
#
# Robert Baratheon → Ned Stark → Jon Arryn
#   Path 1: [FRIEND, 0.9] → [MENTOR, 0.8] (2-hop via Ned)

# Access paths from returned metadata
for chunk in chunks:
    if hasattr(chunk, 'graph_path'):
        print(f"Retrieved via: {chunk.graph_path}")
```

**Why it's useful:**
- **Debugging** - Understand why unexpected chunks appear
- **User trust** - Show users how results were found
- **Transparency** - Explain AI reasoning

**Visualization:**
```
Query: "Robert Baratheon"
↓
Entity: Robert Baratheon
↓ [FRIEND, 0.9]
Entity: Ned Stark
↓ [PARENT, 1.0]
Entity: Robb Stark
↓
Chunk: "Robb Stark fought in the War of Five Kings..."
```

---

## Example 6: Composite Filtering (Multiple Constraints)

**Use Case:** Find family members in early chapters only

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="Tell me about Ned Stark's family",
    vault_id=vault_id,
    k=5,
    relationship_types=[RelationType.PARENT, RelationType.SPOUSE],  # Family only
    temporal_mode="sequence",
    min_sequence=1,
    max_sequence=10,  # Chapters 1-10 only
)

# Composite filter applies BOTH constraints:
# 1. RelationshipTypeFilter: Only PARENT/SPOUSE
# 2. TemporalGraphFilter: Only sequence 1-10

# Result: Catelyn, Robb, Sansa, Arya, Bran, Rickon (no spoilers)
```

**Implementation:**
```python
# Internal: CompositeGraphFilter is created automatically
filters = [
    RelationshipTypeFilter([RelationType.PARENT, RelationType.SPOUSE]),
    TemporalGraphFilter(mode="sequence", min_sequence=1, max_sequence=10)
]
composite = CompositeGraphFilter(filters)

# Relationships filtered sequentially:
# all_rels → type_filtered → temporal_filtered → final_rels
```

---

## Example 7: Pure Family Tree (Parents Only, No Friends)

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="Show me Ned Stark's descendants",
    vault_id=vault_id,
    k=10,
    relationship_types=[RelationType.PARENT],  # Parents only
    max_hops=3,  # Grandchildren, great-grandchildren
    use_pagerank=False  # Don't weight by importance (all family equal)
)

# Traversal:
# Hop 1: Ned → Robb, Sansa, Arya, Bran, Rickon, Jon
# Hop 2: Robb → [children if any], Sansa → [children if any], etc.
# Hop 3: Grandchildren → Great-grandchildren

# Result: Complete family tree up to 3 generations
```

---

## Example 8: Minimal Overhead (Baseline Performance)

**Use Case:** Fast retrieval without advanced features

```python
# Disable all advanced features for minimal latency
chunks = await retrieve_chunks_with_advanced_graph(
    query="Who are Ned Stark's children?",
    vault_id=vault_id,
    k=5,
    expand_graph=True,  # Still use graph expansion
    use_pagerank=False,  # Disable PageRank (~500ms saved)
    track_paths=False,  # Disable path tracking (~100ms saved)
    max_hops=1  # Minimize traversal depth
)

# Total latency: ~300-500ms (similar to original function)
```

---

## Example 9: Maximum Explainability (All Features)

**Use Case:** Research mode with full transparency

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="What is the political situation in Westeros?",
    vault_id=vault_id,
    k=20,
    relationship_types=[RelationType.ALLY, RelationType.ENEMY, RelationType.VASSAL],
    temporal_mode="sequence",
    current_sequence=50,  # Active at chapter 50
    max_hops=3,  # Deep political network
    use_pagerank=True,  # Weight by importance
    track_paths=True,  # Track all paths
    entity_boost_direct=0.4,  # Higher boost for direct mentions
    entity_boost_indirect=0.15  # Higher boost for indirect
)

# Features enabled:
# ✓ Relationship filtering (ALLY, ENEMY, VASSAL only)
# ✓ Temporal filtering (active at chapter 50)
# ✓ PageRank scoring (prioritize major houses)
# ✓ Path tracking (explain connections)
# ✓ 3-hop traversal (find complex alliances)

# Latency: ~1-2 seconds (comprehensive analysis)
```

---

## Example 10: Temporal Range Query

**Use Case:** "What happened between chapters 10-20?"

```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="What major events occurred?",
    vault_id=vault_id,
    k=15,
    temporal_mode="sequence",
    min_sequence=10,
    max_sequence=20,  # Chapters 10-20 only
)

# Filters:
# - Relationships established in [10, 20]
# - Events occurring in [10, 20]
# - Excludes: Earlier backstory, later spoilers

# Result: Only information from the target range
```

---

## Performance Tuning Examples

### Low Latency (< 500ms)
```python
chunks = await retrieve_chunks_with_advanced_graph(
    query=query,
    vault_id=vault_id,
    k=5,
    max_hops=1,  # Minimal traversal
    use_pagerank=False,  # Skip expensive computation
    track_paths=False  # Skip path finding
)
```

### Balanced (500ms - 1s)
```python
chunks = await retrieve_chunks_with_advanced_graph(
    query=query,
    vault_id=vault_id,
    k=10,
    max_hops=2,
    relationship_types=[...],  # Add filters (minimal overhead)
    temporal_mode="sequence",
    max_sequence=20,
    use_pagerank=False  # Still skip PageRank
)
```

### Comprehensive (1-2s)
```python
chunks = await retrieve_chunks_with_advanced_graph(
    query=query,
    vault_id=vault_id,
    k=20,
    max_hops=3,
    relationship_types=[...],
    temporal_mode="sequence",
    current_sequence=50,
    use_pagerank=True,  # Enable PageRank
    track_paths=True  # Enable explainability
)
```

---

## Integration with Agents

### In LangGraph Orchestrator

```python
# src/writeros/agents/langgraph_orchestrator.py

async def _rag_retrieval(state: OrchestratorState):
    # Check if user wants advanced graph features
    advanced_config = state.get("advanced_graph_config", {})

    if advanced_config:
        chunks = await retrieve_chunks_with_advanced_graph(
            query=state["user_message"],
            vault_id=state["vault_id"],
            k=15,
            **advanced_config  # Pass user configuration
        )
    else:
        # Default: basic graph retrieval
        chunks = await retrieve_chunks_with_graph(
            query=state["user_message"],
            vault_id=state["vault_id"],
            k=15
        )

    state["rag_documents"] = [c.chunk for c in chunks]
    return state
```

### User Configuration
```python
# User can specify:
config = {
    "relationship_types": [RelationType.PARENT, RelationType.ALLY],
    "temporal_mode": "sequence",
    "max_sequence": 20,
    "use_pagerank": True
}

# Pass to orchestrator
result = await orchestrator.run(
    user_message="Who are Ned's allies?",
    vault_id=vault_id,
    advanced_graph_config=config
)
```

---

## Common Patterns

### Pattern 1: Family-Only Queries
```python
FAMILY_FILTER = [RelationType.PARENT, RelationType.SPOUSE, RelationType.SIBLING]

async def get_family_members(person_name: str, vault_id: UUID):
    return await retrieve_chunks_with_advanced_graph(
        query=f"Tell me about {person_name}'s family",
        vault_id=vault_id,
        k=10,
        relationship_types=FAMILY_FILTER,
        max_hops=2  # Parents, children, grandchildren, siblings
    )
```

### Pattern 2: Political Network
```python
POLITICAL_FILTER = [RelationType.ALLY, RelationType.VASSAL, RelationType.ENEMY]

async def get_political_network(house_name: str, vault_id: UUID, max_sequence: int):
    return await retrieve_chunks_with_advanced_graph(
        query=f"Who is allied with {house_name}?",
        vault_id=vault_id,
        k=15,
        relationship_types=POLITICAL_FILTER,
        temporal_mode="sequence",
        max_sequence=max_sequence,
        max_hops=2,
        use_pagerank=True  # Prioritize major houses
    )
```

### Pattern 3: Temporal Snapshot
```python
async def get_relationship_snapshot(entity_name: str, chapter: int, vault_id: UUID):
    return await retrieve_chunks_with_advanced_graph(
        query=f"Who is connected to {entity_name}?",
        vault_id=vault_id,
        k=10,
        temporal_mode="sequence",
        current_sequence=chapter,  # Active at this chapter
        max_hops=1,
        track_paths=True  # Show how they're connected
    )
```

---

## Debugging Tips

### Enable Detailed Logging
```python
import logging
logging.getLogger("writeros.rag.graph_retrieval").setLevel(logging.DEBUG)

# Logs will show:
# - query_entities_extracted: count=2, entities=["Ned Stark", "Robert Baratheon"]
# - related_entities_found: count=15, max_distance=2
# - pagerank_computed: avg_score=0.45
# - graph_paths_tracked: targets_with_paths=8, total_paths=12
```

### Inspect Retrieved Chunks
```python
chunks = await retrieve_chunks_with_advanced_graph(...)

for i, chunk in enumerate(chunks):
    print(f"\n=== Chunk {i+1} ===")
    print(f"Content: {chunk.chunk.content[:200]}...")
    print(f"Similarity: {chunk.similarity:.3f}")
    print(f"Relevance Boost: {chunk.relevance_boost:.3f}")
    print(f"Adjusted Score: {chunk.adjusted_score:.3f}")
    print(f"Mentioned Entities: {chunk.mentioned_entity_ids}")
```

---

## When to Use Each Feature

| Feature | Use When | Latency Impact |
|---------|----------|----------------|
| `relationship_types` | Need specific relationship types | Minimal (~5ms) |
| `temporal_mode` + `max_sequence` | Avoid spoilers | Minimal (~10ms) |
| `current_sequence` | Snapshot at specific time | Minimal (~10ms) |
| `use_pagerank` | Prioritize major characters | Medium (~100-500ms) |
| `track_paths` | Need explainability | Low-Medium (~50-200ms) |
| `max_hops=1` | Direct connections only | Baseline |
| `max_hops=2` | Indirect connections | +50-100ms |
| `max_hops=3` | Complex networks | +100-200ms |

---

**For more details, see:** `.claude/TDD_IMPLEMENTATION_SUMMARY.md`
