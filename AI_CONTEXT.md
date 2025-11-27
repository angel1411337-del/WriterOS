# WriterOS AI Context

## Project Overview
WriterOS is an agentic AI system for assisting authors with long-form creative writing (specifically A Song of Ice and Fire fanfiction/analysis). It uses a multi-agent architecture with a central Orchestrator and specialized agents (Psychologist, Navigator, etc.).

## Architecture
- **Framework:** LangChain, LangGraph, SQLModel (PostgreSQL + pgvector).
- **Database:** PostgreSQL on port 5432.
- **Vector DB:** pgvector for semantic search.
- **Graph:** NetworkX (in-memory) / Adjacency List in DB.

## Agents
1.  **OrchestratorAgent:** Routes queries, synthesizes responses.
    - **Dual-Mode Output:** Returns structured analysis (metrics) + narrative synthesis.
2.  **PsychologistAgent:** Analyzes character psychology.
    - **POV Boundaries:** Enforces character knowledge constraints.
3.  **NavigatorAgent:** Calculates travel times and distances.
4.  **ChronologistAgent:** Manages timelines and events.
5.  **ArchitectAgent:** Analyzes plot structure.
6.  **ProfilerAgent:** Extracts entities and relationships.
7.  **ProducerAgent:** Manages project goals.
8.  **DramatistAgent:** Analyzes scene tension.
9.  **MechanicAgent:** Checks magic/world rules.

## Key Systems
### 1. Agent Execution Tracking
- **Purpose:** Debugging and observability.
- **Tables:** `agent_executions`, `agent_execution_logs`, `agent_call_chains`.
- **CLI:** `writeros tracking-stats`, `writeros debug-agent`.

### 2. POV Boundary System
- **Purpose:** Prevents omniscient narrator errors.
- **Mechanism:** Filters facts based on `character_id` and `scene_id` (temporal knowledge).

### 3. RAG System
- **Retriever:** `RAGRetriever` (Iterative, Multi-hop).
- **Inspector:** `writeros inspect-retrieval` (CLI tool for debugging).
  - **Usage:** `writeros inspect-retrieval "query" --limit 3`
  - **Features:** Displays raw retrieved chunks, scores, and metadata for Documents, Entities, Facts, and Events. Useful for debugging hallucinations or missing context.

## Recent Changes (2025-11-27)
- **Fixed:** Database port mismatch (5433 -> 5432).
- **Fixed:** `UndefinedTable` error by robust reset script.
- **Fixed:** `NavigatorAgent` attribute error.
- **Fixed:** SQLAlchemy reserved name (`metadata` -> `execution_metadata` in agent_execution.py).
- **Fixed:** Windows console encoding (Unicode fallback in cli/main.py:248-255).
- **Added:** Agent Execution Tracking system.
- **Added:** Dual-Mode Output in Orchestrator (structured analysis + narrative).
- **Added:** `inspect-retrieval` CLI command.
- **Fixed:** `UnicodeEncodeError` in `EmbeddingService` logging (Windows).
- **Fixed:** SQLAlchemy Lazy Load error in `inspect-retrieval` CLI.
- **Phase 1 COMPLETE (2025-11-26):** LangChain Foundation
  - Enhanced LLMClient with LCEL chain building (`build_chain()`, `chat_with_parser()`)
  - PostgresChatHistory for LangChain-compatible conversation memory
  - ChronologistAgent enhanced with `run_with_lcel()` method
  - All tests passing (see `PHASE1_COMPLETE.md` and `test_lcel_chain.py`)
- **Phase 2 COMPLETE (2025-11-27):** LangSmith & LangGraph
  - LangSmith tracing integration (`src/writeros/utils/langsmith_config.py`)
  - LangGraph orchestrator with StateGraph workflow (`src/writeros/agents/langgraph_orchestrator.py`)
  - 5-node workflow: RAG retrieval → agent router → parallel agents → structured summary → narrative synthesis
  - Checkpointing with MemorySaver for conversation continuity
  - Automatic parallel agent execution (10 agents)
  - Agent autonomy with selective response
  - All tests passing (see `PHASE2_COMPLETE.md` and `test_langgraph.py`)
- **Phase 3 COMPLETE (2025-11-27):** CLI Integration & Tool Calling
  - CLI updated to use LangGraph orchestrator by default (`--use-langgraph` flag)
  - Streaming support added to LangGraph orchestrator (AsyncGenerator)
  - Conversation management integrated (create/save messages to DB)
  - LangChain @tool decorators created (`src/writeros/agents/langgraph_tools.py`)
  - 6 tools available: search_vault, get_entity_details, create_note, read_note, append_to_note, list_vault_entities
  - Tools ready for ProducerAgent binding (Phase 4)
  - Backward compatibility maintained (original orchestrator still available with `--no-use-langgraph`)
- **Phase 4 COMPLETE (2025-11-27):** Tool Binding & Agent Enhancement
  - ProducerAgent enhanced with tool binding (`enable_tools=True`)
  - Added `run_with_tools()` method for autonomous tool usage
  - LLM can autonomously decide when to call tools
  - LangGraph integration updated to pass vault_id to agents
  - Tool-aware agent execution in `_execute_single_agent()`
  - Tool call detection and logging implemented
  - 6 tools bound to ProducerAgent: search_vault, get_entity_details, create_note, read_note, append_to_note, list_vault_entities
  - Ready for tool execution node implementation (optional enhancement)
- **Modular Indexing Pipeline (2025-11-27):**
  - Created `src/writeros/core/indexing/` package - modular, production-grade indexing architecture
  - Separated concerns: Chunker, Embedder, EntityExtractor, RelationshipExtractor, BidirectionalLinker
  - Protocol-based interfaces for testability and extensibility
  - Adapters for existing WriterOS components (UnifiedChunker, EmbeddingService)
  - Factory function `create_default_pipeline()` for easy initialization
  - Supports Chunk → Graph extraction flow
  - Coexists with existing VaultIndexer (gradual migration path)
  - Async/await throughout, structured logging, type-safe (Pydantic models)
- **Entity Schema Implementation (2025-11-27):**
  - Created `src/writeros/schema/entities.py` with `Entity` class (inherits `UUIDMixin`, `TimestampMixin`).
  - Added `embedding` field with `pgvector` index for semantic search.
  - Created `src/writeros/schema/chunks.py` with `Chunk` class to resolve foreign key dependency.
  - Renamed `metadata` field to `metadata_` in `Entity` to avoid SQLAlchemy reserved keyword conflict (mapped to `metadata` column).
  - Updated `src/writeros/schema/__init__.py` to export `Entity` and `Chunk`.
  - Removed conflicting `Entity` definition from `src/writeros/schema/world.py`.
  - Updated `writer.py` and `profiler.py` to use `metadata_` instead of `properties`.
- **Schema Enhancement (2025-11-27):**
  - **Entity Schema:** Enhanced with chunk integration, extraction provenance, graph metrics, and consolidated `NodeSignificance`.
  - **Relationship Schema:** Enhanced with chunk integration, co-occurrence metrics, temporal bounds, and provenance.
  - **Chunk Schema:** Enhanced as "Source of Truth" with content tracking, source location, embedding, and temporal position.
  - **Graph Schema:** Enhanced `GraphNode` and `GraphLink` with visual properties, status, and centrality metrics. Added `GraphMetrics` and `GraphFilter`.
- **NarrativeChunker Integration (2025-11-27):**
  - **Problem:** ClusterSemanticChunking reorders content by topic similarity, breaking ChronologistAgent's timeline analysis and POV Boundary system.
  - **Solution:** Created fiction-optimized `NarrativeChunker` that preserves narrative structure.
  - **Implementation:**
    - Created `src/writeros/preprocessing/narrative_chunker.py` - preserves scenes, dialogue exchanges, chronological order.
    - Added `ChunkingStrategy.NARRATIVE` to `unified_chunker.py`.
    - Integrated into `UnifiedChunker` with `_chunk_narrative()` method.
    - Updated `create_default_pipeline()` to use `ChunkingStrategy.NARRATIVE` by default.
    - Added `scene_id` field to `Chunk` schema (format: `file_path:scene_index`) for POV Boundary system.
    - Updated `WriterOSChunker` to extract and store scene metadata in `Document.metadata_`.
  - **Benefits:**
    - ✅ ChronologistAgent now receives chunks in narrative order (fixes broken timeline analysis).
    - ✅ POV Boundary system can filter knowledge by `scene_id`.
    - ✅ Dialogue exchanges stay together (improves PsychologistAgent character analysis).
    - ✅ Scene structure preserved (respects author's structural markers: ###, ***, ---, # Chapter).
    - ✅ Section type auto-detection (dialogue, flashback, letter, narrative).
  - **Tradeoff:** Slightly lower semantic retrieval optimization vs. cluster semantic chunking, but narrative accuracy is more important for fiction analysis.


## Known Issues & Workarounds
### Tracking Tables Missing
If you see `UndefinedTable: relation "agent_executions" does not exist`:
```bash
# Quick fix: Disable tracking
python -m writeros.cli.main chat "query" --vault-id <id> --no-enable-tracking

# Permanent fix: Create tables once
python -c "from writeros.utils.db import engine; from sqlmodel import SQLModel; from writeros.schema.agent_execution import AgentExecution, AgentExecutionLog, AgentCallChain, AgentPerformanceMetrics; SQLModel.metadata.create_all(engine, tables=[AgentExecution.__table__, AgentExecutionLog.__table__, AgentCallChain.__table__, AgentPerformanceMetrics.__table__])"
```

### Windows Console Emojis
Emojis in dual-mode output display as `?` on Windows (cp1252 encoding).
- **Harmless:** Content is preserved, only display affected.
- **Fix:** Already implemented in cli/main.py with Unicode fallback.

## Development Guidelines
- **Database:** Always use `DATABASE_URL` from `.env`.
- **Logging:** Use `structlog` via `writeros.core.logging`.
- **Testing:** Use `pytest`.
- **CLI Testing:** Always use `--no-enable-tracking` unless tracking tables exist.
- **Output:** Dual-mode output tested and validated (see TESTING_GUIDE.md).

## Upcoming Priorities
- **Top Priority:** Add `FastEmbed` library integration for efficient local embeddings.

