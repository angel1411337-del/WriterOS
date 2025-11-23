# WriterOS Architecture

## System Overview

WriterOS is an AI-powered creative writing assistant that helps authors build, analyze, and maintain complex story worlds.

## Core Components

### 1. **Agents** (`src/writeros/agents/`)
Specialized AI agents for different aspects of story analysis:

- **ProducerAgent** - Ingests and processes manuscripts from Obsidian vaults
- **ProfilerAgent** - Extracts entities (characters, locations, factions) and relationships
- **PsychologistAgent** - Analyzes character psychology, arcs, and transformations  
- **DramatistAgent** - Tracks tension, pacing, and emotional beats
- **ArchitectAgent** - Manages narrative structure and story anchors
- **OrchestratorAgent** - Coordinates multi-agent workflows

### 2. **Schema** (`src/writeros/schema/`)
Database models using SQLModel/Pydantic:

- **Entities & Relationships** - Story world graph
- **Canon & Drift** - Version control for story elements
- **Psychology** - Character states and arcs
- **Narrative** - Story structure (anchors, scenes)
- **Sessions** - User interactions and conversations

### 3. **Services** (`src/writeros/services/`)
Business logic layer for data operations.

### 4. **RAG Pipeline** (`src/writeros/rag/`)
Retrieval-Augmented Generation for context-aware responses.

### 5. **API** (`src/writeros/api/`)
FastAPI REST endpoints for external integrations.

## Database Architecture

### Technology Stack
- **PostgreSQL 15+** with **pgvector** extension
- **SQLModel** for ORM
- **Alembic** for migrations

### Key Tables
- `entities` - Characters, locations, factions, items
- `relationships` - Graph edges between entities
- `sources` - Manuscript chapters/scenes
- `conversations` - User interaction history

### Embedding Strategy
- OpenAI `text-embedding-3-small`
- Vectors stored in `embedding` columns
- Cosine similarity search for semantic queries

## Deployment

### Development
```bash
docker-compose up
```

### Production
- Multi-stage Docker build
- Gunicorn + Uvicorn workers
- PostgreSQL on managed DB service
- Redis for caching (optional)

## Integration Points

### Obsidian Plugin
TypeScript plugin that:
- Syncs vault to WriterOS database
- Generates graph visualizations
- Provides inline AI assistance

### API Consumers
- Web dashboard (future)
- CLI tools (`writeros` command)
- Third-party integrations
