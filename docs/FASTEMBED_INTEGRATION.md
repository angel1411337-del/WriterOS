# FastEmbed Integration Guide

## Overview

WriterOS now uses **FastEmbed** for local, fast, and **FREE** text embeddings instead of OpenAI's embedding API. This reduces costs to zero for embeddings while maintaining high quality.

## Benefits

- **FREE**: No API costs for embeddings
- **FAST**: Local inference, no network latency
- **PRIVATE**: Your data never leaves your machine
- **HIGH QUALITY**: Uses state-of-the-art BGE models from BAAI
- **LIBERAL USE**: Embed as much as you want without cost concerns

## Model Details

**Default Model:** `BAAI/bge-small-en-v1.5`
- Dimension: 384
- Performance: Excellent for most RAG tasks
- Speed: Very fast on CPU

**Alternative Models:**
- `BAAI/bge-base-en-v1.5` - Higher quality (768 dims), slightly slower
- `BAAI/bge-large-en-v1.5` - Best quality (1024 dims), slower

## System Requirements

### Windows

**REQUIRED:** Visual C++ 2015-2022 Redistributable (x64)

Download: https://aka.ms/vs/17/release/vc_redist.x64.exe

**Installation Steps:**
1. Download the installer from the link above
2. Run the installer (requires admin rights)
3. Restart your terminal/IDE after installation
4. Verify: `python -c "from fastembed import TextEmbedding; print('OK')"`

**Common Issues:**
```
ImportError: DLL load failed while importing onnxruntime_pybind11_state
```
**Solution:** Install the Visual C++ Redistributable

### Linux

No additional dependencies required. FastEmbed works out of the box.

### macOS

No additional dependencies required. FastEmbed works out of the box.

## Usage

### Basic Usage

```python
from writeros.utils.embeddings import get_embedding_service

# Get the default embedding service (BAAI/bge-small-en-v1.5)
embedder = get_embedding_service()

# Embed a single query
query_embedding = embedder.embed_query("What is the meaning of life?")
# Returns: List[float] with 384 dimensions

# Embed multiple documents
docs = ["Document 1", "Document 2", "Document 3"]
doc_embeddings = embedder.embed_documents(docs)
# Returns: List[List[float]], each with 384 dimensions
```

### Async Usage

```python
# Async wrapper for compatibility with async code
embeddings = await embedder.get_embeddings(["text1", "text2"])
```

### Using a Different Model

```python
from writeros.utils.embeddings import get_embedding_service

# Use a larger, higher-quality model
embedder = get_embedding_service(embedding_model="BAAI/bge-base-en-v1.5")
```

### Singleton Pattern

The embedding service uses a singleton pattern per model, so multiple calls return the same instance:

```python
service1 = get_embedding_service()
service2 = get_embedding_service()
assert service1 is service2  # True - same instance
```

## Performance

### Speed Comparison

| Model | Embedding Time (100 texts) |
|-------|---------------------------|
| OpenAI API | ~2-3 seconds (network) |
| FastEmbed (CPU) | ~0.5-1 second (local) |
| FastEmbed (GPU) | ~0.1-0.3 seconds (local) |

### Cost Comparison

| Service | Cost per 1M tokens |
|---------|-------------------|
| OpenAI text-embedding-3-small | $0.02 |
| FastEmbed (local) | **$0.00** |

**Annual Savings Example:**
- 10M embeddings/year with OpenAI: $200/year
- 10M embeddings/year with FastEmbed: **$0/year**

## Technical Details

### Model Download

On first use, FastEmbed automatically downloads the model (~90MB for bge-small):

```python
# First time - downloads model
embedder = get_embedding_service()
# Downloading model BAAI/bge-small-en-v1.5... (this happens once)

# Subsequent uses - instant
embedder = get_embedding_service()
# Model already cached, ready to use
```

**Model Cache Location:**
- Windows: `C:\Users\<username>\.cache\fastembed`
- Linux/Mac: `~/.cache/fastembed`

### ONNX Runtime

FastEmbed uses ONNX Runtime for efficient inference:
- CPU: Optimized with ONNX Runtime
- GPU: Automatically uses CUDA if available
- Memory: ~200-500MB for bge-small model

## Migration from OpenAI Embeddings

### Before (OpenAI)

```python
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=api_key
)
result = embeddings.embed_query("text")
```

### After (FastEmbed)

```python
from writeros.utils.embeddings import get_embedding_service

embeddings = get_embedding_service()
result = embeddings.embed_query("text")
```

**Changes:**
1. No API key needed
2. No network calls
3. Slightly different embedding dimensions (1536 → 384)
4. Need to rebuild vector database with new embeddings

## Rebuilding Vector Database

If migrating from OpenAI embeddings, you need to regenerate all embeddings:

```bash
# 1. Backup your database
pg_dump writeros > backup.sql

# 2. Clear existing embeddings
python -c "
from writeros.utils.db import get_db_session
from writeros.schema.chunks import Chunk

with get_db_session() as session:
    session.query(Chunk).update({Chunk.embedding: None})
    session.commit()
print('Embeddings cleared')
"

# 3. Regenerate embeddings with FastEmbed
python -m writeros.preprocessing.unified_chunker --reindex-all
```

## Troubleshooting

### Windows: DLL Load Failed

**Error:**
```
ImportError: DLL load failed while importing onnxruntime_pybind11_state
```

**Solution:**
1. Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe
2. Restart terminal/IDE
3. Retry

### Model Download Fails

**Error:**
```
HTTPError: 403 Forbidden
```

**Solution:**
```bash
# Use mirror or VPN if Hugging Face is blocked
export HF_ENDPOINT=https://hf-mirror.com
python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"
```

### Out of Memory

**Error:**
```
RuntimeError: out of memory
```

**Solution:**
```python
# Use smaller model
from writeros.utils.embeddings import get_embedding_service
embedder = get_embedding_service(embedding_model="BAAI/bge-small-en-v1.5")

# Or batch your embeddings
texts = [...]  # Large list
batch_size = 32
for i in range(0, len(texts), batch_size):
    batch = texts[i:i+batch_size]
    embeddings = embedder.embed_documents(batch)
```

## Best Practices

### 1. Use Liberal Embeddings

Since embeddings are now free, you can:
- Embed more chunks for better granularity
- Re-embed frequently for updates
- Experiment with different chunking strategies
- Create multiple indexes for different use cases

### 2. Batch Processing

```python
# Good - batch processing
docs = load_all_documents()
embeddings = embedder.embed_documents(docs)

# Avoid - one at a time (slower)
for doc in docs:
    embedding = embedder.embed_query(doc)
```

### 3. Model Selection

- **Small** (`bge-small`): Default, fast, good quality
- **Base** (`bge-base`): Better quality, ~2x slower
- **Large** (`bge-large`): Best quality, ~4x slower

Choose based on your latency vs. quality needs.

### 4. Caching

The singleton pattern ensures model is loaded once:

```python
# Model loaded once, reused everywhere
from writeros.utils.embeddings import get_embedding_service

def function1():
    embedder = get_embedding_service()  # Uses cached instance

def function2():
    embedder = get_embedding_service()  # Same instance
```

## Related Documentation

- [Environment Setup](./ENVIRONMENT_SETUP.md) - System requirements
- [Vector Indexes](./VECTOR_INDEXES.md) - Optimizing vector search
- [Chunking System](./CHUNKING_SYSTEM.md) - Text chunking strategies

## Support

**Issues?** Check:
1. Visual C++ Redistributable installed (Windows)
2. Model downloaded successfully
3. Enough disk space (~90MB per model)
4. Python 3.8+ installed

**Still stuck?** Open an issue with:
- OS and Python version
- Error message
- Output of: `pip show fastembed onnxruntime`
