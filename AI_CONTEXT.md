# WriterOS AI Context

> **Auto-Generated Context File** - Do not edit manually. Update source files in `.context/`.
> *Generated: 2024-05-14*

## 1. Project Overview
**WriterOS** is an AI-powered operating system for epic fantasy authors. It moves beyond simple text generation into high-level structural analysis, world-building management, and narrative consistency checking.
- **Primary Interface:** **Obsidian** (via BYOK Plugin).
- **Backend:** Containerized Python API (FastAPI).
- **Deployment:** Self-hosted (**Docker**) or SaaS (Cloud).

## 2. Architecture Stack
- **Target Model:** **GPT-5.1** (Primary for High-Reasoning Agents).
- **Language:** Python 3.11+
- **Web Framework:** FastAPI
- **Database:** **PostgreSQL 16** + **pgvector** (Vector Store).
- **RAG Strategy:** **GraphRAG** (Hybrid Vector + Knowledge Graph).
- **Chunking Strategy:** **ClusterSemanticChunker** (Dynamic breakpointing based on semantic similarity).
- **ORM:** SQLModel (Pydantic + SQLAlchemy).
- **Logging:** Structlog (JSON in prod, colored in dev).
- **Task Queue:** ARQ (Redis).

## 3. Directory Structure
The project follows a strict `src`-based layout:
- `src/writeros/agents/`: The 11 specialized AI agents.
- `src/writeros/schema/`: **Modular** domain-driven data models.
- `src/writeros/api/`: FastAPI routes and middleware.
- `src/writeros/services/`: Low-level infra (DB, LLM, Embeddings).
- `docker/`: Container definitions.

## 4. Key Conventions
- **Schema Separation:** We distinguish between "Objective Reality" (`schema.world`, `schema.library`) and "Subjective Analysis" (`schema.psychology`, `schema.narrative`).
- **Source-Awareness:** The `Archivist` agent tracks the credibility of sources to weigh conflicting writing advice.
- **Scene-Level Granularity:** The `Dramatist` agent analyzes tension arcs at the `Scene` model level, utilizing semantic clustering.

## 5. Current Development Status
- **Phase:** V1 Architecture Implementation.
- **Completed:** Directory structure, Hybrid Schema design, Docker configuration, Logging setup.
- **Tech Stack Locked:** Docker, Obsidian Plugin, ClusterSemanticChunker, GraphRAG, PostgreSQL.
- **In Progress:** Agent logic implementation, API route wiring.

## 6. The 11 Agents
1. **Orchestrator:** Router.
2. **Profiler:** Entity Extraction.
3. **Psychologist:** Character profiling.
4. **Theorist:** Themes.
5. **Dramatist:** Pacing/Tension.
6. **Architect:** Plot structure.
7. **Mechanic:** Magic systems.
8. **Navigator:** Travel logistics.
9. **Chronologist:** Time tracking.
10. **Stylist:** Prose editing.
11. **Archivist:** Canon/Source management.
12. **Producer:** Project management.
