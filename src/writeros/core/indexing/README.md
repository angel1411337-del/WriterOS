# WriterOS Indexing Pipeline

## Overview

This package implements a **modular, production-grade indexing pipeline** for WriterOS.

It separates the indexing process into discrete, testable components with clear interfaces.

## Architecture

```
IndexingPipeline
├── Chunker           → Break files into semantic chunks
├── Embedder          → Generate vector embeddings
├── EntityExtractor   → Extract entities from chunks (Chunk → Graph)
├── RelationshipExtractor → Extract relationships (Chunk → Graph)
└── BidirectionalLinker  → Update bidirectional links
```

## Flow

```
File → Chunker → Embedder → Save Chunks
                                ↓
                          For each chunk:
                                ↓
                          EntityExtractor
                                ↓
                          RelationshipExtractor
                                ↓
                          BidirectionalLinker
                                ↓
                          (Future: Co-occurrence Analysis)
```

## Components

### 1. Chunker
**Purpose:** Break files into semantic chunks.

**Interface:**
```python
class Chunker:
    async def chunk_file(
        self,
        vault_id: UUID,
        file_path: str,
        content: str,
        narrative_sequence: Optional[int] = None,
    ) -> List[Document]:
        ...
```

**Implementation:** `WriterOSChunker` (adapts existing `UnifiedChunker`)

### 2. Embedder
**Purpose:** Generate vector embeddings for chunks.

**Interface:**
```python
class Embedder:
    async def embed_chunks(self, chunks: List[Document]) -> List[Document]:
        ...
```

**Implementation:** `WriterOSEmbedder` (uses existing embedding service)

### 3. EntityExtractor
**Purpose:** Extract entities from chunks (Chunk → Graph flow).

**Interface:**
```python
class EntityExtractor:
    async def extract(self, chunk: Document) -> List[Entity]:
        ...
```

**Implementation:** `LLMEntityExtractor` (placeholder, needs LLM integration)

### 4. RelationshipExtractor
**Purpose:** Extract relationships from chunks.

**Interface:**
```python
class RelationshipExtractor:
    async def extract(
        self,
        chunk: Document,
        entities: List[Entity]
    ) -> List[Relationship]:
        ...
```

**Implementation:** `LLMRelationshipExtractor` (placeholder, needs LLM integration)

### 5. BidirectionalLinker
**Purpose:** Update all bidirectional links between chunks and graph.

**Interface:**
```python
class BidirectionalLinker:
    async def link_chunk_to_graph(
        self,
        chunk: Document,
        entities: List[Entity],
        relationships: List[Relationship],
    ):
        ...
```

**Implementation:** `DatabaseLinker` (saves to database)

## Usage

### Quick Start (Default Pipeline)

```python
from writeros.core.indexing import create_default_pipeline
from uuid import UUID

# Create pipeline with default implementations
pipeline = create_default_pipeline()

# Process a file
result = await pipeline.process_file(
    vault_id=UUID("your-vault-id"),
    file_path="path/to/file.md",
    content="Your file content here...",
    narrative_sequence=1,  # Optional
)

print(f"Chunks created: {result.chunks_created}")
print(f"Entities extracted: {result.entities_extracted}")
print(f"Relationships extracted: {result.relationships_extracted}")
```

### Custom Pipeline (Dependency Injection)

```python
from writeros.core.indexing import IndexingPipeline
from writeros.core.indexing.pipeline import (
    WriterOSChunker,
    WriterOSEmbedder,
    LLMEntityExtractor,
    LLMRelationshipExtractor,
    DatabaseLinker,
)
from writeros.preprocessing import UnifiedChunker, ChunkingStrategy

# Create custom chunker
unified_chunker = UnifiedChunker(
    strategy=ChunkingStrategy.CLUSTER,  # Custom strategy
    min_chunk_size=100,
    max_chunk_size=500,
)

# Assemble pipeline with custom components
pipeline = IndexingPipeline(
    chunker=WriterOSChunker(unified_chunker),
    embedder=WriterOSEmbedder(),
    entity_extractor=LLMEntityExtractor(),
    relationship_extractor=LLMRelationshipExtractor(),
    linker=DatabaseLinker(),
)

# Use pipeline
result = await pipeline.process_file(...)
```

### Testing with Mocks

```python
from writeros.core.indexing import IndexingPipeline
from unittest.mock import AsyncMock

# Create mock components
mock_chunker = AsyncMock(spec=Chunker)
mock_embedder = AsyncMock(spec=Embedder)
mock_entity_extractor = AsyncMock(spec=EntityExtractor)
mock_relationship_extractor = AsyncMock(spec=RelationshipExtractor)
mock_linker = AsyncMock(spec=BidirectionalLinker)

# Assemble pipeline with mocks
pipeline = IndexingPipeline(
    chunker=mock_chunker,
    embedder=mock_embedder,
    entity_extractor=mock_entity_extractor,
    relationship_extractor=mock_relationship_extractor,
    linker=mock_linker,
)

# Test pipeline behavior
result = await pipeline.process_file(...)

# Assert mock calls
mock_chunker.chunk_file.assert_called_once()
mock_embedder.embed_chunks.assert_called_once()
```

## Relationship to Existing VaultIndexer

### Current System (src/writeros/utils/indexer.py)
- Monolithic VaultIndexer class
- Combines chunking, embedding, and file scanning
- Works well for simple use cases
- Hard to test individual components

### New System (src/writeros/core/indexing/pipeline.py)
- Modular pipeline with discrete components
- Clear separation of concerns
- Easy to test (dependency injection)
- Extensible (swap components)
- Supports Chunk → Graph extraction flow

### Migration Strategy

**Option 1: Gradual Migration (Recommended)**
- Keep existing VaultIndexer for file scanning and vault operations
- Use new IndexingPipeline for per-file processing
- Migrate file-by-file over time

```python
from writeros.utils.indexer import VaultIndexer
from writeros.core.indexing import create_default_pipeline

# Use VaultIndexer for vault-level operations
vault_indexer = VaultIndexer(...)

# Use new pipeline for per-file processing
pipeline = create_default_pipeline()

# In VaultIndexer, replace internal processing with:
for file in files:
    result = await pipeline.process_file(...)
```

**Option 2: Full Replacement**
- Replace VaultIndexer with new pipeline + file scanner
- Requires more upfront work
- Cleaner long-term

## Benefits

### 1. Testability
- Mock individual components
- Test chunking independently from embedding
- Test extraction independently from linking

### 2. Extensibility
- Swap out chunking strategies easily
- Try different embedding models
- A/B test extraction algorithms

### 3. Maintainability
- Clear interfaces (Protocols)
- Single responsibility per component
- Easy to understand data flow

### 4. Production-Ready
- Async/await throughout
- Proper error handling
- Structured logging
- Type-safe (Pydantic models)

## Future Enhancements

### 1. LLM-Based Entity Extraction
```python
class GPT4EntityExtractor(EntityExtractor):
    async def extract(self, chunk: Document) -> List[Entity]:
        prompt = f"Extract entities from: {chunk.content}"
        entities = await llm.extract_entities(prompt)
        return entities
```

### 2. Co-occurrence Analysis
```python
async def queue_co_occurrence_analysis(vault_id: UUID):
    """Queue background job for co-occurrence analysis."""
    await task_queue.enqueue("co_occurrence", vault_id=vault_id)
```

### 3. Incremental Indexing
```python
async def process_file_delta(
    old_content: str,
    new_content: str,
    ...
):
    """Only reindex changed chunks."""
    diff = compute_diff(old_content, new_content)
    changed_chunks = identify_affected_chunks(diff)
    # Only process changed chunks
```

### 4. Batch Processing
```python
async def process_batch(files: List[FileInput]) -> BatchResult:
    """Process multiple files in parallel."""
    tasks = [pipeline.process_file(...) for file in files]
    results = await asyncio.gather(*tasks)
    return BatchResult(results)
```

## API Reference

### IndexingResult
```python
class IndexingResult(BaseModel):
    chunks_created: int
    entities_extracted: int
    relationships_extracted: int
    file_path: str
```

### ChunkExtractionResult
```python
class ChunkExtractionResult(BaseModel):
    chunk_id: UUID
    entity_count: int
    relationship_count: int
```

## Example: CLI Integration

```python
# In src/writeros/cli/main.py

@app.command()
def index_v2(
    vault_path: str = typer.Option(..., help="Path to vault"),
    vault_id: str = typer.Option(..., help="Vault UUID"),
):
    """Index vault using new modular pipeline."""
    import asyncio
    from writeros.core.indexing import create_default_pipeline

    async def _run():
        pipeline = create_default_pipeline()

        # Scan files
        files = scan_vault(vault_path)

        # Process each file
        for file in files:
            result = await pipeline.process_file(
                vault_id=UUID(vault_id),
                file_path=file.path,
                content=file.content,
            )

            print(f"Processed {file.path}")
            print(f"  Chunks: {result.chunks_created}")
            print(f"  Entities: {result.entities_extracted}")

    asyncio.run(_run())
```

## Status

**Current:** ✅ Core pipeline implemented
**Next Steps:**
1. Implement LLM-based entity extraction
2. Implement LLM-based relationship extraction
3. Add co-occurrence analysis queue
4. Integrate with CLI
5. Migrate from VaultIndexer (gradual)

## See Also

- `src/writeros/utils/indexer.py` - Current VaultIndexer (monolithic)
- `src/writeros/preprocessing/chunker.py` - UnifiedChunker (used by WriterOSChunker)
- `src/writeros/utils/embeddings.py` - Embedding service (used by WriterOSEmbedder)
