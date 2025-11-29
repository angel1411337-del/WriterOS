# Graph-Enhanced Retrieval - Implementation Guide

**Last Updated:** 2025-11-28
**Status:** ✅ Implemented
**File:** `src/writeros/rag/graph_retrieval.py`

---

## Overview

Graph-Enhanced Retrieval combines **vector similarity search** with **knowledge graph traversal** to improve retrieval quality for relationship-focused queries. This addresses a fundamental limitation of pure vector RAG: it misses implicit relationship context.

---

## Problem Statement

### Before: Pure Vector RAG
```
Query: "Who are Ned Stark's allies?"

Vector Search Results:
1. "Ned Stark is Lord of Winterfell" (0.85 similarity)
2. "Ned Stark has five children" (0.78 similarity)
3. "Robert Baratheon is king" (0.62 similarity)
```

**Issue:** Robert Baratheon (Ned's closest ally) ranks low because the chunk doesn't explicitly mention "ally" or "Ned Stark" together.

### After: Graph-Enhanced RAG
```
Query: "Who are Ned Stark's allies?"

1. Extract query entities: [Ned Stark]
2. Find 1-hop neighbors: [Robert Baratheon (ALLY, strength=0.9),
                          Catelyn Stark (SPOUSE, strength=1.0),
                          Jon Arryn (MENTOR, strength=0.8)]
3. Boost chunks mentioning these entities

Enhanced Results:
1. "Robert and Ned grew up together in the Vale" (0.62 sim + 0.27 boost = 0.89)
2. "Ned Stark is Lord of Winterfell" (0.85 similarity)
3. "Jon Arryn raised Ned and Robert as wards" (0.58 sim + 0.24 boost = 0.82)
```

**Result:** Relationship-relevant chunks rank higher even with lower vector similarity.

---

## Algorithm Deep Dive

### Step 1: Vector Search (Baseline)
```python
initial_chunks = await vector_search_chunks(query, vault_id, k=k * 2)
```

- Retrieve **k×2** candidates (e.g., 10 for top-5 results)
- Uses cosine similarity on chunk embeddings
- Returns `RetrievedChunk` objects with similarity scores

### Step 2: Entity Extraction from Query
```python
query_entities = await extract_entities_from_query(query, vault_id)
# Uses vector search on Entity table to find top 3 entities
```

**Example:**
- Query: "What is the relationship between Ned Stark and Robert Baratheon?"
- Extracted: `[Ned Stark, Robert Baratheon]`

### Step 3: Multi-Hop Graph Traversal
```python
for hop in range(max_hops):
    for entity in current_entities:
        relationships = get_relationships(entity)
        for rel in relationships:
            neighbor = rel.target or rel.source
            related_entity_info[neighbor] = {
                "distance": hop + 1,
                "strength": rel.strength
            }
```

**Data Tracked:**
- **Distance:** How many hops away (1 = direct connection, 2 = friend-of-friend)
- **Strength:** Relationship strength from `Relationship.strength` field (0.0-1.0)

**Example (2-hop traversal):**
```
Query Entity: Ned Stark

Hop 1 (direct connections):
  - Robert Baratheon (ALLY, strength=0.9, distance=1)
  - Catelyn Stark (SPOUSE, strength=1.0, distance=1)
  - Jon Arryn (MENTOR, strength=0.8, distance=1)

Hop 2 (connections of connections):
  - Cersei Lannister (via Robert, SPOUSE, strength=0.7, distance=2)
  - Tywin Lannister (via Cersei, PARENT, strength=0.9, distance=2)
  - Lysa Arryn (via Jon, SPOUSE, strength=0.8, distance=2)
```

### Step 4: Relevance Boosting
```python
for chunk in initial_chunks:
    mentioned = set(chunk.mentioned_entity_ids)

    # Direct mentions of query entities
    direct_overlap = mentioned & query_entity_ids
    direct_boost = len(direct_overlap) * entity_boost_direct  # 0.3 per mention

    # Indirect mentions of related entities
    indirect_boost = 0.0
    for entity_id in mentioned & related_entity_ids:
        info = related_entity_info[entity_id]
        distance_penalty = 1.0 / info["distance"]  # 1-hop = 1.0, 2-hop = 0.5
        strength_weight = info["strength"]         # 0.0-1.0
        indirect_boost += entity_boost_indirect * distance_penalty * strength_weight

    chunk.adjusted_score = chunk.similarity + direct_boost + indirect_boost
```

**Boost Calculation Example:**
```
Chunk: "Robert and Ned fought together in the rebellion"
Mentioned entities: [Ned Stark, Robert Baratheon]

Direct boost:
  - Ned Stark (query entity) = +0.3
  - Robert Baratheon (query entity) = +0.3
  Total direct = +0.6

Indirect boost: (none, both are query entities)

Final score = 0.72 (similarity) + 0.6 (boost) = 1.32
```

**Complex Example (2-hop):**
```
Chunk: "Tywin Lannister sent a raven to the capital"
Mentioned entities: [Tywin Lannister]

Direct boost: 0 (Tywin not in query)

Indirect boost:
  - Tywin Lannister (distance=2, strength=0.9)
  - boost = 0.1 * (1/2) * 0.9 = 0.045

Final score = 0.55 (similarity) + 0.045 (boost) = 0.595
```

### Step 5: Re-ranking
```python
initial_chunks.sort(key=lambda c: c.adjusted_score, reverse=True)
```

Chunks are sorted by `adjusted_score`, which combines:
- **Vector similarity** (semantic relevance to query)
- **Graph relevance** (mentions entities related to query entities)

### Step 6: Intelligent Expansion
```python
if len(initial_chunks) < k:
    for entity_id, info in sorted_related:  # Sorted by strength
        entity = get_entity(entity_id)
        if entity.primary_source_chunk_id:
            source_chunk = get_chunk(entity.primary_source_chunk_id)
            if source_chunk not in results:
                initial_chunks.append(source_chunk)
```

**Purpose:** If we have fewer than `k` results (e.g., asking for 10 but only found 7), add high-value chunks that define the related entities.

**Example:**
- Query: "Who are Ned's allies?"
- Found 7 chunks
- Related entities: Robert Baratheon, Jon Arryn, Howland Reed
- Add primary source chunks for Robert, Jon, Howland (their character introductions)

---

## Configuration Parameters

### `max_hops` (default: 1)
**Description:** How many relationship hops to traverse

**Trade-offs:**
- **1 hop:** Fast, highly relevant (direct connections only)
- **2 hops:** Broader context, includes friend-of-friend relationships
- **3+ hops:** Very broad, may include irrelevant entities

**Use Cases:**
- 1-hop: "Who are Ned's children?" (direct PARENT relationships)
- 2-hop: "Who might support Ned in a conflict?" (allies + their allies)
- 3-hop: "What factions are connected to the Starks?" (political network)

### `entity_boost_direct` (default: 0.3)
**Description:** Boost added per direct query entity mention

**Tuning:**
- Too low (0.1): Graph context underweighted, results similar to pure vector
- Too high (0.5): Graph dominates, chunks with entity mentions rank too high
- Sweet spot: 0.2-0.4 (depends on embedding quality)

### `entity_boost_indirect` (default: 0.1)
**Description:** Boost added per related entity mention (before distance/strength weighting)

**Relationship to direct:**
- Should be **lower** than direct boost (indirect connections are weaker signals)
- Typically 1/3 to 1/2 of direct boost
- Gets multiplied by `(1/distance) * strength`

### `use_relationship_strength` (default: True)
**Description:** Whether to weight boosts by `Relationship.strength` field

**When to disable:**
- Relationship strengths are not populated
- All relationships should be weighted equally
- Testing/debugging

---

## Performance Characteristics

### Latency Breakdown
```
Total: ~300-800ms (depending on graph size)

1. Vector search:           50-100ms  (pgvector query)
2. Entity extraction:       50-100ms  (pgvector on Entity table)
3. Graph traversal:        100-400ms  (depends on hop count & fanout)
   - 1-hop:  ~100ms (10-50 relationships per entity)
   - 2-hop:  ~200ms (100-500 total relationships)
   - 3-hop:  ~400ms (500-2000 total relationships)
4. Boost calculation:       10-50ms   (Python loop over chunks)
5. Re-ranking:              <10ms     (Python sort)
6. Expansion (if needed):   50-100ms  (additional DB queries)
```

### Database Queries
```
Standard retrieval (no graph):
  - 1 query (vector search on chunks)

Graph-enhanced (1-hop):
  - 1 query (vector search on chunks)
  - 1 query (entity extraction)
  - N queries (relationships for N query entities)
  - M queries (expansion chunks, only if len(results) < k)

Graph-enhanced (2-hop):
  - 1 query (vector search)
  - 1 query (entity extraction)
  - N + (N*fanout) queries (relationships for all entities in 2 hops)
```

**Optimization:** Consider batching relationship queries or using a single query with `IN` clause.

### Memory Usage
```
Chunks: k*2 * ~10KB = 20-50KB (minimal)
Entities: O(fanout^hops) * 1KB
  - 1-hop, fanout=10: ~10KB
  - 2-hop, fanout=10: ~100KB
  - 3-hop, fanout=10: ~1MB (careful!)
```

---

## Usage Examples

### Example 1: Simple Relationship Query
```python
from writeros.rag.graph_retrieval import retrieve_chunks_with_graph

chunks = await retrieve_chunks_with_graph(
    query="Who are Ned Stark's children?",
    vault_id=vault_id,
    k=5,
    expand_graph=True,
    max_hops=1  # Direct PARENT relationships only
)

# Results will include chunks mentioning:
# - Robb, Sansa, Arya, Bran, Rickon (direct children)
# - Potentially Jon Snow if connected via PARENT relationship
```

### Example 2: Political Network (2-hop)
```python
chunks = await retrieve_chunks_with_graph(
    query="What political alliances involve House Stark?",
    vault_id=vault_id,
    k=10,
    expand_graph=True,
    max_hops=2,  # Include allies-of-allies
    entity_boost_direct=0.4,     # Strong boost for Stark mentions
    entity_boost_indirect=0.15,  # Moderate boost for allied houses
    use_relationship_strength=True
)

# Graph traversal:
# Hop 1: House Stark → House Tully (ALLY), House Arryn (ALLY)
# Hop 2: House Tully → House Frey (VASSAL), House Arryn → House Royce (VASSAL)

# Results ranked by:
# 1. Chunks mentioning Stark directly (high boost)
# 2. Chunks mentioning Tully/Arryn (medium boost, 1-hop)
# 3. Chunks mentioning Frey/Royce (lower boost, 2-hop)
```

### Example 3: Disable Graph (Baseline Comparison)
```python
chunks = await retrieve_chunks_with_graph(
    query="Who are Ned Stark's children?",
    vault_id=vault_id,
    k=5,
    expand_graph=False  # Pure vector search
)

# No graph traversal, only vector similarity
# Useful for A/B testing graph enhancement impact
```

---

## Integration with LangGraph Orchestrator

The graph-enhanced retrieval is already integrated into the main RAG workflow via `RAGRetriever.retrieve_with_graph_enhancement()`:

```python
# src/writeros/rag/retriever.py:467-623

results = await retriever.retrieve_with_graph_enhancement(
    query=user_query,
    vault_id=vault_id,
    k=15,
    expand_graph=True,
    return_chunks=True  # Use chunk-level graph retrieval
)
```

**Orchestrator Integration:**
```python
# src/writeros/agents/langgraph_orchestrator.py

async def _rag_retrieval(state: OrchestratorState) -> OrchestratorState:
    retriever = RAGRetriever()

    # Option 1: Graph-enhanced retrieval
    results = await retriever.retrieve_with_graph_enhancement(
        query=state["user_message"],
        vault_id=state["vault_id"],
        k=15,
        expand_graph=True,
        return_chunks=True
    )

    # Results automatically include graph-boosted chunks
    state["rag_documents"] = results.documents
    return state
```

---

## Debugging & Observability

### Logging
The implementation includes structured logging at each step:

```python
logger.info("graph_enhanced_retrieval_started", query=query[:100], k=k, max_hops=max_hops)
logger.info("query_entities_extracted", count=len(query_entities), entities=[...])
logger.info("related_entities_found", count=len(related_entity_ids), max_distance=2)
logger.info("graph_enhanced_retrieval_complete",
    returned_count=5,
    avg_boost=0.18,
    max_boost=0.6
)
```

### Metrics to Monitor
1. **Query entity extraction accuracy** - Are the right entities being identified?
2. **Graph traversal fanout** - How many entities at each hop?
3. **Average relevance boost** - Is graph adding value? (should be >0.1)
4. **Max relevance boost** - Are some chunks getting huge boosts? (check for bugs)
5. **Expansion trigger rate** - How often do we need to add chunks?

### Debug Example
```python
chunks = await retrieve_chunks_with_graph(query="...", vault_id=..., k=5)

for chunk in chunks:
    print(f"Chunk: {chunk.chunk.content[:100]}")
    print(f"  Similarity: {chunk.similarity:.3f}")
    print(f"  Relevance Boost: {chunk.relevance_boost:.3f}")
    print(f"  Adjusted Score: {chunk.adjusted_score:.3f}")
    print(f"  Mentioned Entities: {len(chunk.mentioned_entity_ids)}")
    print()
```

---

## Testing Recommendations

### Unit Tests
```python
# Test entity extraction
entities = await extract_entities_from_query("Ned Stark and Robert", vault_id)
assert "Ned Stark" in [e.name for e in entities]

# Test graph traversal
neighbors = await get_entity_neighbors(ned_stark_id, vault_id)
assert robert_baratheon_id in neighbors

# Test boost calculation
chunks = await retrieve_chunks_with_graph(
    query="Who are Ned's allies?",
    vault_id=vault_id,
    k=5,
    max_hops=1
)
assert chunks[0].relevance_boost > 0  # At least one chunk got boosted
```

### A/B Testing
```python
# Compare graph-enhanced vs. pure vector

# Baseline
baseline = await retrieve_chunks_with_graph(
    query=query, vault_id=vault_id, k=5, expand_graph=False
)

# Enhanced
enhanced = await retrieve_chunks_with_graph(
    query=query, vault_id=vault_id, k=5, expand_graph=True
)

# Evaluate:
# - Do relationship queries improve? (manual annotation or user feedback)
# - Does latency increase significantly?
# - Are there queries that get worse? (over-boosting)
```

---

## Future Enhancements

### 1. Relationship Type Filtering
```python
# Only traverse ALLY and SPOUSE relationships
retrieve_chunks_with_graph(
    query="Who supports House Stark?",
    relationship_types=[RelationType.ALLY, RelationType.VASSAL]
)
```

### 2. Temporal Graph Filtering
```python
# Only use relationships active at a specific point in the story
retrieve_chunks_with_graph(
    query="Who are Ned's allies in Chapter 10?",
    max_sequence_order=10  # Filter by Relationship.established_at_sequence
)
```

### 3. PageRank-Style Entity Importance
```python
# Weight boost by entity centrality (pre-computed)
for entity_id in indirect_overlap:
    centrality = entity_importance_scores[entity_id]  # 0.0-1.0
    boost *= centrality
```

### 4. Relationship Path Explanation
```python
@dataclass
class RetrievedChunk:
    chunk: Chunk
    similarity: float
    relevance_boost: float
    graph_path: List[Tuple[str, str]]  # [(entity, relationship_type), ...]

# Example: [("Ned Stark", "ALLY"), ("Robert Baratheon", "KING_OF")]
# Explains WHY this chunk was boosted
```

### 5. Batch Optimization
```python
# Single query for all relationship lookups
stmt = select(Relationship).where(
    or_(
        Relationship.source_entity_id.in_(all_entity_ids),
        Relationship.target_entity_id.in_(all_entity_ids)
    )
)
# Reduces N queries to 1 query per hop
```

---

## Comparison with Other Approaches

### vs. Pure Vector RAG
| Aspect | Pure Vector | Graph-Enhanced |
|--------|-------------|----------------|
| **Relationship Queries** | ❌ Poor | ✅ Excellent |
| **Latency** | ✅ 50-100ms | ⚠️ 300-800ms |
| **Implementation Complexity** | ✅ Simple | ⚠️ Moderate |
| **Entity Extraction Required** | ❌ No | ✅ Yes |

### vs. Pure Graph Traversal
| Aspect | Pure Graph | Graph-Enhanced Hybrid |
|--------|------------|----------------------|
| **Semantic Search** | ❌ No | ✅ Yes |
| **Scalability** | ⚠️ Poor (large graphs) | ✅ Good (vector prunes first) |
| **Exact Match Required** | ✅ Yes | ❌ No (fuzzy via embeddings) |

### vs. Reranking Models (Cross-Encoder)
| Aspect | Cross-Encoder Rerank | Graph-Enhanced |
|--------|---------------------|----------------|
| **Relationship Context** | ❌ Limited | ✅ Explicit |
| **Latency** | ⚠️ High (LLM rerank) | ✅ Lower (rule-based boost) |
| **Explainability** | ❌ Black box | ✅ Clear (entity mentions) |

---

## References

- **Implementation:** `src/writeros/rag/graph_retrieval.py`
- **Schema:** `src/writeros/schema/chunks.py`, `relationships.py`
- **Integration:** `src/writeros/rag/retriever.py:467-623`
- **Original Inspiration:** Adapted from external graph_enhanced_retrieval pattern

---

**This implementation provides a production-ready graph-enhanced retrieval system optimized for fiction analysis and relationship-heavy queries.**
