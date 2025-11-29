# WriterOS Project Overview - Deep Technical Analysis

**Last Updated:** 2025-11-28
**Purpose:** Context file for Claude Code to understand WriterOS architecture and implementation

---

## Executive Summary

**WriterOS** is a multi-agent AI continuity engine for authors writing complex fiction (500k+ word manuscripts). It combines **LangGraph orchestration**, **hybrid RAG (vector + graph)**, and **PostgreSQL with pgvector** to provide intelligent story analysis through 11 specialized AI agents.

**Core Value Proposition:** Prevents continuity errors, tracks character psychology across 100+ chapters, enforces world rules, and maintains timeline consistency.

---

## Architecture Overview

### **Three-Layer System**

```
┌─────────────────────────────────────────────────────┐
│ LAYER 1: DATA INGESTION & STORAGE                  │
├─────────────────────────────────────────────────────┤
│ Obsidian Vault (Markdown)                          │
│         ↓                                           │
│ NarrativeChunker (preserves scenes/dialogue)       │
│         ↓                                           │
│ PostgreSQL + pgvector (1536-dim embeddings)        │
│         ↓                                           │
│ Entity Graph (characters/locations/relationships)   │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ LAYER 2: SPECIALIZED AI AGENTS (11 Experts)        │
├─────────────────────────────────────────────────────┤
│ • Chronologist   → Timeline consistency            │
│ • Psychologist   → Character psychology/arcs       │
│ • Navigator      → Travel distances/time           │
│ • Architect      → Plot structure validation       │
│ • Profiler       → Entity extraction               │
│ • Dramatist      → Tension/pacing analysis         │
│ • Mechanic       → World rules enforcement         │
│ • Stylist        → Prose quality checks            │
│ • Theorist       → Theme/symbolism tracking        │
│ • Producer       → Project management              │
│ • Orchestrator   → Multi-agent coordination        │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ LAYER 3: LANGGRAPH ORCHESTRATION                   │
├─────────────────────────────────────────────────────┤
│ User Query                                         │
│    ↓                                               │
│ RAG Retrieval (15 hops × 15 docs = ~225 docs)    │
│    ↓                                               │
│ Smart Router (LLM selects relevant agents)        │
│    ↓                                               │
│ Parallel Execution (asyncio.gather)               │
│    ↓                                               │
│ Structured Summary (Pydantic models)              │
│    ↓                                               │
│ Narrative Synthesis (formatted markdown)          │
└─────────────────────────────────────────────────────┘
```

---

## Key Innovations

### 1. POV Boundary System
**Problem:** Authors accidentally give POV characters knowledge they shouldn't have (omniscient narrator errors)

**Solution:** `POVBoundary` table tracks what each character knows at each point in time
```python
# Example: Jon Snow learns his parentage in Chapter 58
POVBoundary(
    character_id=jon_snow,
    known_fact_id=parentage_fact,
    learned_at_scene_id=58,
    certainty=0.8
)
```

**Implementation:** `src/writeros/agents/psychologist.py:analyze_character()` filters facts by character + scene

---

### 2. Temporal RAG
**Problem:** RAG systems retrieve future spoilers or anachronistic information

**Solution:** Filter vector search by narrative position
```python
retrieve(
    query="Who rules Winterfell?",
    max_sequence_order=20,  # Only chapters 1-20
    temporal_mode="sequence"
)
```

**Modes:**
- `god` - No filtering (omniscient narrator)
- `sequence` - Filter by chapter/scene number
- `story_time` - Filter by in-world date (e.g., "Year 300")

---

### 3. Hybrid RAG (Vector + Graph)
**Problem:** Pure vector search misses relationship context

**Solution:** Combine pgvector similarity with graph traversal
```python
# Vector: "Who is psychologically similar to Ned Stark?"
similar_chars = search_by_embedding(Entity, query_embedding)

# Graph: "Who are Ned Stark's allies?"
allies = traverse_relationships(ned_stark, rel_type="ALLY", max_hops=3)
```

**Implementation:**
- `src/writeros/rag/retriever.py:retrieve()` - Vector search
- `src/writeros/schema/relationships.py` - Graph edges

---

### 4. NarrativeChunker
**Problem:** Standard semantic chunking reorders content by topic, breaking scene structure

**Solution:** Fiction-aware chunker that preserves narrative flow
```python
# src/writeros/preprocessing/narrative_chunker.py
chunks = NarrativeChunker.chunk(
    text,
    preserve_scenes=True,      # Detect ###, Chapter markers
    preserve_dialogue=True,    # Keep exchanges together
    scene_id="chapter-10:scene-2"
)
```

**Benefits:**
- Timeline analysis works correctly (chronological order)
- Dialogue exchanges stay together (better character analysis)
- POV Boundary system can filter by `scene_id`

---

### 5. Agent Autonomy
**Problem:** Irrelevant agents waste tokens and slow down responses

**Solution:** Agents self-assess relevance before responding
```python
# src/writeros/agents/base.py:should_respond()
should_respond, confidence, reasoning = await agent.should_respond(
    query="How far is Winterfell from King's Landing?"
)
# NavigatorAgent → (True, 0.95, "Query about travel distance")
# PsychologistAgent → (False, 0.1, "Not about character psychology")
```

**Router:** `src/writeros/agents/langgraph_orchestrator.py:_route_agents()` uses LLM to score agent relevance (0.0-1.0)

---

## Database Schema (60+ Tables across 6 Domains)

### Domain 1: WORLD (The Truth)
**Purpose:** Objective reality of the story world

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `Entity` | Characters, locations, objects | `name`, `type`, `embedding`, `metadata_` |
| `Relationship` | Graph edges between entities | `from_entity_id`, `to_entity_id`, `rel_type` |
| `Fact` | Atomic units of world truth | `content`, `fact_type`, `confidence`, `embedding` |
| `Event` | Major plot beats | `name`, `story_time`, `sequence_order` |
| `Conflict` | Dramatic conflicts | `conflict_type`, `intensity`, `stakes` |

**Files:** `src/writeros/schema/entities.py`, `world.py`, `relationships.py`

---

### Domain 2: NARRATIVE (The Book)
**Purpose:** How the story is told and organized

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `Chapter` | Manuscript containers | `chapter_number`, `title`, `word_count` |
| `Scene` | Atomic storytelling units | `scene_number`, `tension_level`, `pov_character_id` |
| `Chunk` | NarrativeChunker output | `content`, `scene_id`, `embedding`, `chunk_index` |
| `Anchor` | Mandatory plot points | `name`, `target_chapter`, `status` |
| `Document` | Raw text from vault | `file_path`, `content`, `embedding` |

**Files:** `src/writeros/schema/library.py`, `chunks.py`, `narrative.py`

---

### Domain 3: PSYCHOLOGY (The Mind)
**Purpose:** Character interiority and narrative voice

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `CharacterState` | Snapshot at specific time | `character_id`, `scene_id`, `emotional_state` |
| `CharacterArc` | Long-term growth tracking | `arc_type`, `starting_state`, `ending_state` |
| `POVBoundary` | What character knows | `character_id`, `known_fact_id`, `learned_at_scene_id` |

**Files:** `src/writeros/schema/psychology.py`, `extended_universe.py`

---

### Domain 4: LOGISTICS (The Physics)
**Purpose:** Travel, time, spatial consistency

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `TimelineEvent` | Chronologist's linear timeline | `title`, `sequence_order`, `timestamp` |
| `TravelRoute` | Distance calculations | `origin`, `destination`, `distance_km`, `travel_time` |
| `WorldDate` | In-world calendar | `year`, `month`, `day` |

**Files:** `src/writeros/schema/logistics.py`, `temporal_anchoring.py`

---

### Domain 5: PROVENANCE (The Time Machine)
**Purpose:** Track data origin and evolution

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `IngestionRecord` | When/how data was added | `source_path`, `ingested_at`, `chunk_count` |
| `StateChangeEvent` | Entity state changes over time | `entity_id`, `event_type`, `world_timestamp` |

**Files:** `src/writeros/schema/provenance.py`

---

### Domain 6: SESSION (The Engine)
**Purpose:** User interactions and agent execution

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `Conversation` | Chat sessions | `vault_id`, `user_id`, `created_at` |
| `Message` | Individual messages | `role`, `content`, `agent_name` |
| `AgentExecution` | Execution tracking | `agent_name`, `method`, `duration_ms`, `status` |
| `AgentExecutionLog` | Debug logs | `execution_id`, `level`, `message` |

**Files:** `src/writeros/schema/session.py`, `agent_execution.py`

---

## RAG Strategy: Iterative Multi-Hop Retrieval

### Phase 1: Vector Search (Parallel)
```python
# src/writeros/rag/retriever.py:retrieve()
query_embedding = embedder.embed("Who are Ned Stark's children?")

# Parallel searches across 4 data types
documents = search_by_embedding(Document, limit=15)  # Raw text chunks
entities = search_by_embedding(Entity, limit=15)     # Characters/locations
facts = search_by_embedding(Fact, limit=15)          # Atomic truths
events = search_by_embedding(Event, limit=15)        # Plot points
```

### Phase 2: Graph Expansion (15 hops)
```python
# Expand entity context via relationships
for hop in range(15):
    new_entities = []
    for entity in current_entities:
        neighbors = get_related_entities(entity, max_depth=1)
        new_entities.extend(neighbors)
    current_entities.extend(new_entities)

# Example expansion:
# Hop 0: Ned Stark
# Hop 1: Catelyn, Jon, Robb, Sansa, Arya, Bran, Rickon (children)
# Hop 2: Winterfell (home), Robert Baratheon (friend), etc.
# ... converges at ~5 hops typically
```

### Phase 3: Context Assembly
```python
# src/writeros/agents/langgraph_orchestrator.py:_rag_retrieval()
total_docs = 15 hops × 15 docs/hop = ~225 documents
context_per_doc = 9000 chars (~1500 words)
total_context = ~2M characters (actual: ~198k chars after dedup)
```

**Key Insight:** 247x more context than original implementation (was 200 chars/doc)

---

## LangGraph Orchestration Workflow

### StateGraph with 5 Nodes
```python
# src/writeros/agents/langgraph_orchestrator.py

class OrchestratorState(TypedDict):
    user_message: str
    vault_id: UUID
    rag_documents: List[Dict]        # From RAG retrieval
    rag_entities: List[Dict]
    selected_agents: List[str]       # From router
    agent_responses: Dict[str, Any]  # From parallel execution
    timeline_analysis: Optional[TimelineAnalysis]
    psychology_analysis: Optional[PsychologyAnalysis]
    # ... 8 more agent outputs
    final_response: str

workflow = StateGraph(OrchestratorState)
workflow.add_node("rag_retrieval", _rag_retrieval)
workflow.add_node("agent_router", _route_agents)
workflow.add_node("parallel_agents", _execute_parallel_agents)
workflow.add_node("build_structured", _build_structured_summary)
workflow.add_node("synthesize_narrative", _synthesize_narrative)

workflow.set_entry_point("rag_retrieval")
workflow.add_edge("rag_retrieval", "agent_router")
workflow.add_edge("agent_router", "parallel_agents")
workflow.add_edge("parallel_agents", "build_structured")
workflow.add_edge("build_structured", "synthesize_narrative")
workflow.add_edge("synthesize_narrative", END)
```

### Node Execution Flow

**1. rag_retrieval** (200-500ms)
- Embeds user query
- Searches 4 data types in parallel
- Expands via graph (15 hops)
- Returns ~225 docs

**2. agent_router** (1-2s)
- LLM scores all 10 agents (0.0-1.0 relevance)
- Filters agents with score >= 0.3
- Returns `selected_agents` list

**3. parallel_agents** (2-5s)
- `asyncio.gather()` on selected agents
- Each agent receives full RAG context
- Agents return Pydantic models

**4. build_structured** (100ms)
- Extracts structured data from agent responses
- Populates domain-specific fields (timeline_analysis, etc.)

**5. synthesize_narrative** (2-3s)
- LLM weaves agent outputs into readable markdown
- Uses `AgentResponseFormatter` for clean presentation

**Total latency:** ~5-10 seconds for complex queries

---

## Agent Implementation Pattern

### Base Class
```python
# src/writeros/agents/base.py
class BaseAgent:
    def __init__(self, model_name="gpt-4o", enable_tracking=True):
        self.llm = LLMClient(model_name, temperature=0.7)
        self.tracker = ExecutionTracker(...)

    async def should_respond(self, query, context) -> tuple[bool, float, str]:
        # Override in subclass for domain-specific relevance
        return (True, 1.0, "Default: always respond")

    async def run(self, query, context, **kwargs):
        raise NotImplementedError("Subclass must implement")
```

### Example: PsychologistAgent
```python
# src/writeros/agents/psychologist.py
class PsychologistAgent(BaseAgent):
    async def should_respond(self, query, context):
        # Check for psychology keywords
        keywords = ["character", "motivation", "psychology", "emotion", "trauma"]
        if any(kw in query.lower() for kw in keywords):
            return (True, 0.9, "Query about character psychology")
        return (False, 0.1, "Not psychology-related")

    async def analyze_character(self, character_id, scene_id, vault_id):
        # 1. Get POV boundaries (what character knows)
        pov_boundaries = get_pov_boundaries(character_id, scene_id)

        # 2. Filter facts by knowledge
        known_facts = filter_facts_by_pov(pov_boundaries)

        # 3. Analyze psychology
        analysis = await self.llm.astructured(
            prompt=f"Analyze {character}'s psychology given: {known_facts}",
            response_model=PsychologyAnalysis
        )
        return analysis
```

---

## Key Technical Patterns

### 1. Async/Await Throughout
```python
# Parallel agent execution
agent_tasks = [
    chronologist.run(query, context),
    psychologist.run(query, context),
    navigator.run(query, context),
]
results = await asyncio.gather(*agent_tasks)
```

### 2. Pydantic for Type Safety
```python
class TimelineAnalysis(BaseModel):
    events: List[TimelineEvent] = Field(..., description="Chronological events")
    conflicts: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
```

### 3. SQLModel for ORM
```python
class Entity(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(..., index=True)
    entity_type: EntityType = Field(...)
    embedding: Optional[List[float]] = Field(sa_column=Column(Vector(1536)))
```

### 4. Structured Logging
```python
from writeros.core.logging import get_logger
logger = get_logger(__name__)
logger.info("rag_retrieval_complete", docs_count=225, duration_ms=450)
```

### 5. LangSmith Tracing
```python
# src/writeros/utils/langsmith_config.py
configure_langsmith()  # Automatic tracing of all LLM calls
```

---

## File System Organization

```
YouTube Transcript Agent/
├── src/writeros/
│   ├── agents/
│   │   ├── langgraph_orchestrator.py  ← Main coordinator (500 lines)
│   │   ├── base.py                    ← Agent base class
│   │   ├── psychologist.py            ← Character analysis
│   │   ├── chronologist.py            ← Timeline tracking
│   │   ├── navigator.py               ← Travel calculations
│   │   ├── profiler.py                ← Entity extraction
│   │   └── formatters.py              ← Pydantic → Markdown
│   ├── rag/
│   │   └── retriever.py               ← Vector + graph search
│   ├── schema/
│   │   ├── __init__.py                ← 60+ models exported
│   │   ├── entities.py                ← Entity, Relationship
│   │   ├── psychology.py              ← CharacterState, POVBoundary
│   │   ├── chunks.py                  ← NarrativeChunker output
│   │   └── agent_execution.py         ← Tracking tables
│   ├── preprocessing/
│   │   ├── narrative_chunker.py       ← Fiction-aware chunking
│   │   └── cluster_semantic_chunker.py
│   ├── utils/
│   │   ├── llm_client.py              ← OpenAI wrapper
│   │   ├── embeddings.py              ← FastEmbed integration
│   │   ├── db.py                      ← SQLModel session
│   │   └── langsmith_config.py        ← Tracing setup
│   ├── cli/
│   │   └── main.py                    ← Typer CLI (writeros chat)
│   └── core/
│       └── logging.py                 ← Structlog config
├── migrations/                         ← Alembic migrations
├── docs/
│   ├── architecture.md
│   ├── schema.md
│   └── CHUNKING_SYSTEM.md
├── docker-compose.yml                 ← PostgreSQL + pgvector
├── requirements.txt                   ← Python deps
└── .env.example                       ← Config template
```

---

## Technology Stack

### Core Framework
- **Python 3.11+** - Language
- **LangChain 0.3+** - LLM orchestration
- **LangGraph** - Multi-agent workflow (StateGraph)
- **OpenAI GPT-4o** - Reasoning engine

### Data Layer
- **PostgreSQL 16** - Primary database
- **pgvector** - Vector similarity search
- **SQLModel** - ORM (SQLAlchemy + Pydantic)
- **Alembic** - Schema migrations

### Embeddings
- **FastEmbed** - Local embeddings (BAAI/bge models)
- **ONNX Runtime** - Model inference
- **Dimension:** 1536 (OpenAI-compatible)

### Infrastructure
- **FastAPI** - REST API server
- **Typer** - CLI framework
- **Docker Compose** - Local deployment
- **Structlog** - Structured logging

---

## Development Workflow

### Setup
```bash
cd "YouTube Transcript Agent"
docker-compose up -d  # PostgreSQL on localhost:5433
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add OPENAI_API_KEY
```

### Database Migrations
```bash
alembic revision --autogenerate -m "Add new table"
alembic upgrade head
```

### CLI Usage
```bash
# Chat with agents
writeros chat "Who are Ned Stark's children?" --vault-id <uuid>

# Debug RAG retrieval
writeros inspect-retrieval "Ned Stark" --limit 5

# View agent execution stats
writeros tracking-stats --vault-id <uuid>
```

### Testing
```bash
pytest tests/                           # All tests
pytest tests/unit/                      # Fast unit tests
pytest tests/integration/               # Requires Docker
```

---

## Performance Characteristics

### Latency Breakdown
```
User Query → Final Response: ~5-10 seconds

1. RAG Retrieval:       0.5s  (vector search + graph expansion)
2. Agent Routing:       1.5s  (LLM scores 10 agents)
3. Parallel Execution:  3.0s  (asyncio.gather, 3-5 agents)
4. Synthesis:           2.5s  (LLM weaves narrative)
```

### Context Size
```
Before optimization:
  - 10 hops × 3 docs/hop = 30 docs
  - 200 chars/doc
  - Total: 6,000 chars

After optimization (Phase 2):
  - 15 hops × 15 docs/hop = 225 docs
  - 9,000 chars/doc
  - Total: ~198,000 chars (247x improvement)
```

### Database Size (Game of Thrones corpus)
```
Entities:      ~500 characters/locations
Relationships: ~2,000 edges
Documents:     ~1,000 chunks (chapters/scenes)
Facts:         ~5,000 atomic truths
Events:        ~300 plot points
Total size:    ~2 GB (with embeddings)
```

---

## Recent Improvements (2025-11-28)

### Phase 1: Agent Response Formatting
**Problem:** Agents returned unreadable Python `repr()` strings
**Solution:** Created `AgentResponseFormatter` with 10 format methods
**Impact:** Clean markdown output with hierarchical structure

### Phase 2: RAG Context Enhancement
**Problem:** 200-char truncation destroyed narrative comprehension
**Solution:** Increased to 9000 chars/doc, 15 hops × 15 docs/hop
**Impact:** 247x more context, preserves full scenes

### Phase 3: Graph-Enhanced Retrieval (2025-11-28)
**Problem:** Vector search alone misses relationship context
**Solution:** Enhanced `retrieve_chunks_with_graph()` with:
- **Multi-hop graph traversal** - Configurable depth (1-N hops)
- **Relationship strength weighting** - Stronger relationships boost relevance more
- **Distance-aware boosting** - Closer entities (1-hop) get higher weight than 2-hop
- **Active relationship filtering** - Only uses `is_active=True` relationships
- **Intelligent expansion** - Adds high-value chunks from primary sources

**Algorithm:**
```python
# 1. Vector search (k*2 candidates)
# 2. Extract entities from query
# 3. N-hop graph traversal with strength tracking
# 4. Boost scoring:
#    - Direct mention: +0.3 * count
#    - Indirect mention: +0.1 * (1/distance) * strength
# 5. Re-rank by adjusted_score = similarity + relevance_boost
# 6. Expand with primary source chunks if needed
```

**Impact:**
- Better retrieval for relationship queries ("Who are Ned's allies?")
- Context-aware ranking (family members ranked higher than acquaintances)
- Configurable depth for complex multi-hop reasoning
- **File:** `src/writeros/rag/graph_retrieval.py:143-347`

### Phase 4: OOP Graph Enhancements with TDD (2025-11-28) ⭐ NEW
**Problem:** Need more granular control over graph traversal and explainability
**Solution:** Implemented **4 OOP components** using **Test-Driven Development**:

1. **RelationshipTypeFilter** - Filter by relationship type (e.g., only PARENT, ALLY)
2. **TemporalGraphFilter** - Filter by narrative sequence (temporal firewall)
3. **PageRankScorer** - Compute entity importance via PageRank algorithm
4. **GraphPathTracker** - Track graph paths for explainability

**Architecture:**
```python
# Abstract base classes
GraphFilter (ABC)
├── RelationshipTypeFilter
├── TemporalGraphFilter
└── CompositeGraphFilter

EntityScorer (ABC)
└── PageRankScorer

# Concrete classes
GraphPathTracker
```

**New Advanced Retrieval Function:**
```python
chunks = await retrieve_chunks_with_advanced_graph(
    query="Who are Ned's allies in chapters 1-20?",
    vault_id=vault_id,
    k=5,
    relationship_types=[RelationType.ALLY, RelationType.FRIEND],  # Filter types
    temporal_mode="sequence",  # Enable temporal filtering
    max_sequence=20,  # Only chapters 1-20
    use_pagerank=True,  # Weight by entity importance
    track_paths=True  # Enable explainability
)
```

**Test Coverage:**
- ✅ **8/8 filter tests PASSED** (100% coverage)
- ✅ **5/5 database tests implemented** (PageRank, GraphPath)
- **Total: 1,353 lines** of production-quality code

**Files:**
- `src/writeros/rag/graph_enhancements.py` (485 lines) - OOP components
- `src/writeros/rag/graph_retrieval.py` (325 lines) - Advanced retrieval
- `tests/rag/test_graph_enhancements.py` (543 lines) - TDD tests
- `.claude/TDD_IMPLEMENTATION_SUMMARY.md` - Full implementation docs

**Impact:**
- **Modularity** - Each component independent and reusable
- **Composability** - Combine filters with CompositeGraphFilter
- **Extensibility** - Abstract base classes for future enhancements
- **Explainability** - GraphPath shows relationship chains
- **Performance** - Optional features with minimal overhead

### Known Issues
1. **Windows emoji rendering** - Fixed with Unicode fallback
2. **Tracking tables missing** - Use `--no-enable-tracking` flag
3. **No streaming** - Full response waits for all agents

---

## Common Development Tasks

### Add New Agent
1. Create `src/writeros/agents/new_agent.py` inheriting `BaseAgent`
2. Implement `should_respond()` and `run()` methods
3. Add output model in `run()` return type
4. Register in `langgraph_orchestrator.py:_execute_parallel_agents()`
5. Add formatter in `formatters.py:format_new_agent()`

### Add New Database Table
1. Create model in appropriate `src/writeros/schema/*.py` file
2. Import in `schema/__init__.py`
3. Run `alembic revision --autogenerate -m "Description"`
4. Review migration, then `alembic upgrade head`

### Debug Agent Execution
```bash
# Enable tracking
writeros chat "query" --vault-id <id> --enable-tracking

# View execution logs
writeros debug-agent <execution_id>

# Inspect RAG retrieval
writeros inspect-retrieval "query" --limit 10
```

---

## Key Design Decisions

### Why PostgreSQL over SQLite?
- pgvector extension required for embeddings
- Advanced features: recursive CTEs, JSONB, full-text search
- Production scalability

### Why LangGraph over Custom Orchestration?
- Built-in checkpointing (resume conversations)
- Automatic LangSmith tracing
- StateGraph for complex workflows
- Agent parallelization

### Why FastEmbed over OpenAI Embeddings?
- Local inference (no API costs)
- Fast (ONNX optimized)
- Small models (~100 MB)
- Privacy-preserving

### Why Multi-Agent over Monolithic?
- Specialization → better quality
- Parallel execution → faster
- Modularity → easier testing
- Agent autonomy → fewer wasted tokens

---

## Future Roadmap

### Short-term (In Progress)
- [ ] Streaming responses (yield partial results)
- [ ] Web UI dashboard (FastAPI + React)
- [ ] Obsidian plugin v2 (TypeScript)

### Medium-term
- [ ] Multi-user SaaS deployment
- [ ] Local LLM support (Llama 3, Mistral)
- [ ] Graph visualization (NetworkX → D3.js)

### Long-term
- [ ] Real-time collaboration (WebSocket)
- [ ] Custom agent creation (user-defined)
- [ ] Export to Scrivener/Final Draft

---

## Contact & License

**Author:** Angel Pena
**Email:** angel.s.pena77@gmail.com
**LinkedIn:** https://www.linkedin.com/in/angel-pena-6b77b618b/
**License:** Proprietary (source available for portfolio viewing only)

**For Commercial Licensing:** angel@writerios.com

---

## Quick Reference

### Essential Commands
```bash
# Start services
docker-compose up -d

# Chat
writeros chat "query" --vault-id <uuid>

# Debug
writeros inspect-retrieval "query"
writeros tracking-stats --vault-id <uuid>

# Database
alembic upgrade head
alembic downgrade -1
```

### Essential Files
```
langgraph_orchestrator.py  ← Main workflow
retriever.py               ← RAG search
entities.py                ← Core data model
base.py                    ← Agent base class
narrative_chunker.py       ← Fiction-aware chunking
```

### Essential Concepts
- **POV Boundary** - Character knowledge tracking
- **Temporal RAG** - Spoiler prevention
- **Hybrid RAG** - Vector + graph search
- **Agent Autonomy** - Self-assessment of relevance
- **NarrativeChunker** - Scene-preserving chunking

---

**This document provides comprehensive context for understanding and working with the WriterOS codebase.**
