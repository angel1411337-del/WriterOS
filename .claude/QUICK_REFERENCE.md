# WriterOS Quick Reference Card

**Last Updated:** 2025-11-28

---

## Essential Commands

### Development
```bash
# Start services
docker-compose up -d

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "Description"
alembic downgrade -1

# Environment setup
cp .env.example .env
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### CLI Usage
```bash
# Chat with agents
writeros chat "Who are Ned Stark's children?" --vault-id <uuid>

# Debug RAG retrieval
writeros inspect-retrieval "Ned Stark" --limit 5

# Agent execution stats
writeros tracking-stats --vault-id <uuid>

# Debug specific execution
writeros debug-agent <execution_id>

# Disable tracking (if tables missing)
writeros chat "query" --vault-id <uuid> --no-enable-tracking
```

---

## Key File Locations

### Core Implementation
```
src/writeros/
├── agents/
│   ├── langgraph_orchestrator.py  ← Main coordinator (500 lines)
│   ├── base.py                    ← Agent base class
│   ├── psychologist.py            ← Character analysis
│   ├── chronologist.py            ← Timeline tracking
│   └── formatters.py              ← Pydantic → Markdown
├── rag/
│   ├── retriever.py               ← Vector + graph search
│   └── graph_retrieval.py         ← Graph-enhanced retrieval ⭐
├── schema/
│   ├── entities.py                ← Entity, primary_source_chunk_id
│   ├── chunks.py                  ← Chunk, mentioned_entity_ids
│   ├── relationships.py           ← Relationship, strength, is_active
│   └── psychology.py              ← CharacterState, POVBoundary
└── utils/
    ├── llm_client.py              ← OpenAI wrapper
    ├── embeddings.py              ← FastEmbed integration
    └── db.py                      ← SQLModel session
```

---

## Architecture Patterns

### Multi-Agent Pattern
```python
# src/writeros/agents/base.py
class MyAgent(BaseAgent):
    async def should_respond(self, query, context):
        # Domain-specific relevance check
        if "keyword" in query.lower():
            return (True, 0.9, "Query matches domain")
        return (False, 0.1, "Not relevant")

    async def run(self, query, context, vault_id, **kwargs):
        # Main agent logic
        tracker = self.create_tracker(vault_id)
        async with tracker.track_execution(method="run", input_data={...}):
            result = await self.llm.astructured(
                prompt=prompt,
                response_model=OutputModel
            )
            return result
```

### RAG Retrieval Pattern
```python
# Standard retrieval
from writeros.rag.retriever import RAGRetriever

retriever = RAGRetriever()
results = await retriever.retrieve(
    query="Who are Ned's children?",
    vault_id=vault_id,
    limit=10,
    include_documents=True,
    include_entities=True
)

# Graph-enhanced retrieval
from writeros.rag.graph_retrieval import retrieve_chunks_with_graph

chunks = await retrieve_chunks_with_graph(
    query="Who are Ned Stark's allies?",
    vault_id=vault_id,
    k=5,
    expand_graph=True,
    max_hops=1,
    entity_boost_direct=0.3,
    entity_boost_indirect=0.1,
    use_relationship_strength=True
)
```

### Database Pattern
```python
# Reading entities
from sqlmodel import Session, select
from writeros.schema import Entity, Relationship
from writeros.utils.db import engine

with Session(engine) as session:
    stmt = select(Entity).where(
        Entity.vault_id == vault_id,
        Entity.entity_type == EntityType.CHARACTER
    )
    characters = session.exec(stmt).all()

# Creating entities
entity = Entity(
    vault_id=vault_id,
    name="Jon Snow",
    entity_type=EntityType.CHARACTER,
    description="Ned Stark's bastard son",
    embedding=embedding_vector,
    primary_source_chunk_id=chunk_id  # For graph retrieval
)
session.add(entity)
session.commit()
```

---

## Common Queries & Solutions

### "How do I add a new agent?"
1. Create `src/writeros/agents/my_agent.py` inheriting `BaseAgent`
2. Implement `should_respond()` and `run()` methods
3. Add output model (Pydantic)
4. Register in `langgraph_orchestrator.py:_execute_parallel_agents()`
5. Add formatter in `formatters.py:format_my_agent()`

### "How do I add a new database table?"
1. Create model in `src/writeros/schema/my_table.py`
2. Inherit `UUIDMixin` and `TimestampMixin`
3. Import in `schema/__init__.py`
4. Run `alembic revision --autogenerate -m "Add my_table"`
5. Review migration, then `alembic upgrade head`

### "How do I debug slow RAG retrieval?"
```bash
# 1. Inspect what's being retrieved
writeros inspect-retrieval "your query" --limit 10

# 2. Check vector index
psql -h localhost -p 5433 -U writer -d writeros
\d chunks  # Check if embedding column has index

# 3. Enable detailed logging
export LOG_LEVEL=DEBUG
writeros chat "query" --vault-id <uuid>
```

### "How do I test graph-enhanced retrieval?"
```python
# test_graph_retrieval.py
import asyncio
from writeros.rag.graph_retrieval import retrieve_chunks_with_graph

async def test():
    chunks = await retrieve_chunks_with_graph(
        query="Who are Ned Stark's allies?",
        vault_id=vault_id,
        k=5,
        expand_graph=True,
        max_hops=1
    )

    for chunk in chunks:
        print(f"Score: {chunk.adjusted_score:.3f} "
              f"(sim={chunk.similarity:.3f} + boost={chunk.relevance_boost:.3f})")
        print(f"Content: {chunk.chunk.content[:200]}\n")

asyncio.run(test())
```

---

## Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://writer:password@localhost:5433/writeros

# OpenAI
OPENAI_API_KEY=sk-...

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=writeros-dev

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Mode
WRITEROS_MODE=local  # or "saas"
```

### Docker Compose
```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5433:5432"
    environment:
      POSTGRES_USER: writer
      POSTGRES_PASSWORD: password
      POSTGRES_DB: writeros
```

---

## Performance Tuning

### RAG Retrieval
```python
# Current settings (optimized for narrative comprehension)
max_hops = 15
docs_per_hop = 15
max_content_length = 9000  # ~1500 words per doc

# For faster queries (less context)
max_hops = 5
docs_per_hop = 5
max_content_length = 2000
```

### Graph-Enhanced Retrieval
```python
# Balanced (default)
max_hops = 1
entity_boost_direct = 0.3
entity_boost_indirect = 0.1

# Aggressive (prioritize graph heavily)
max_hops = 2
entity_boost_direct = 0.5
entity_boost_indirect = 0.2

# Conservative (mostly vector)
max_hops = 1
entity_boost_direct = 0.1
entity_boost_indirect = 0.05
```

---

## Troubleshooting

### "UndefinedTable: relation 'agent_executions' does not exist"
```bash
# Quick fix: Disable tracking
writeros chat "query" --vault-id <id> --no-enable-tracking

# Permanent fix: Create tables
python -c "from writeros.utils.db import engine; from sqlmodel import SQLModel; from writeros.schema.agent_execution import *; SQLModel.metadata.create_all(engine)"
```

### "UnicodeEncodeError on Windows"
Already fixed in `cli/main.py:248-255` with Unicode fallback

### "pgvector extension not installed"
```sql
-- Connect to database
psql -h localhost -p 5433 -U writer -d writeros

-- Install extension
CREATE EXTENSION IF NOT EXISTS vector;
```

### "Relationship strength not being used"
```python
# Check if relationships have strength values
with Session(engine) as session:
    rel = session.get(Relationship, relationship_id)
    print(rel.strength)  # Should be 0.0-1.0, not None

# If None, update:
rel.strength = 0.8
session.add(rel)
session.commit()
```

---

## Key Concepts

### POV Boundary
Prevents omniscient narrator errors by tracking what each character knows
```python
POVBoundary(
    character_id=jon_snow,
    known_fact_id=fact_id,
    learned_at_scene_id=scene_58,
    certainty=0.8
)
```

### Temporal RAG
Filters retrieval by narrative position to avoid spoilers
```python
results = await retriever.retrieve(
    query="Who rules Winterfell?",
    max_sequence_order=20,  # Only chapters 1-20
    temporal_mode="sequence"
)
```

### Graph-Enhanced Retrieval
Boosts chunks based on entity relationships
```python
# Direct mention: +0.3
# 1-hop neighbor: +0.1 * strength
# 2-hop neighbor: +0.1 * 0.5 * strength
adjusted_score = similarity + relevance_boost
```

### NarrativeChunker
Preserves scene structure instead of reordering by topic
```python
chunks = NarrativeChunker.chunk(
    text,
    preserve_scenes=True,    # Detect ###, Chapter markers
    preserve_dialogue=True,  # Keep exchanges together
    scene_id="chapter-10:2"
)
```

---

## Metrics & Logging

### Structured Logging
```python
from writeros.core.logging import get_logger

logger = get_logger(__name__)
logger.info("event_name", key1="value1", key2=42)
```

### Key Metrics to Monitor
- **RAG retrieval latency:** Should be <500ms
- **Graph traversal fanout:** How many entities per hop?
- **Average relevance boost:** Should be >0.1 if graph is helping
- **Agent execution time:** Total pipeline should be <10s

---

## Links

- **Architecture:** `.claude/PROJECT_OVERVIEW.md`
- **Graph Retrieval:** `.claude/GRAPH_ENHANCED_RETRIEVAL.md`
- **Smart Context Formatter:** `.claude/SMART_CONTEXT_FORMATTER.md` (Solves RAG text blob problem)
- **Output Cleanup:** `.claude/OUTPUT_CLEANUP.md` (NEW - Solves synthesis text blob problem)
- **Context Builder:** `.claude/CONTEXT_BUILDER_DESIGN.md` (Entity-focused context)
- **Coding Standards:** `.claude/CODING_STANDARDS.md` (REQUIRED READING)
- **TDD Implementation:** `.claude/TDD_IMPLEMENTATION_SUMMARY.md`
- **Usage Examples:** `.claude/USAGE_EXAMPLES.md`
- **Troubleshooting:** `TROUBLESHOOTING.md`
- **Testing:** `TESTING_GUIDE.md`

---

**IMPORTANT:** All new code must follow the standards in `.claude/CODING_STANDARDS.md`:
- Object-Oriented Programming (OOP)
- Test-Driven Development (TDD)
- No emojis in code or documentation
- Comprehensive documentation with design decisions
- Well-separated and organized code

**This reference card covers 80% of common development tasks. For deep dives, see the full documentation.**
