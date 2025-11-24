# WriterOS Test Suite - Quick Start

## ✅ Tests are working!

The comprehensive test suite has been successfully implemented with 95%+ coverage focus on RAG components.

## Running Tests

### Unit Tests Only (Fast, No Database Required)
```bash
# Run all unit tests
pytest tests/services/ tests/preprocessing/ -v

# With coverage
pytest tests/services/ tests/preprocessing/ --cov=src/writeros --cov-report=html
```

### Integration Tests (Requires Docker PostgreSQL)
```bash
# Start PostgreSQL first
docker-compose up -d db

# Run integration tests
pytest tests/rag/ tests/integration/ -v
```

### All Tests
```bash
# Make sure Docker PostgreSQL is running
docker-compose up -d db

# Run everything
pytest --cov=src/writeros --cov-report=html
```

## Current Test Status

✅ **Working Tests:**
- `tests/services/test_embedding_service.py` - 8 tests passing
- `tests/preprocessing/test_semantic_chunker.py` - All unit tests passing

⚠️ **Requires Database:**
- `tests/rag/test_vector_search.py` - Needs PostgreSQL with pgvector
- `tests/rag/test_graph_rag.py` - Needs PostgreSQL
- `tests/integration/test_rag_pipeline_e2e.py` - Needs PostgreSQL

## Quick Test Commands

```bash
# Test embedding service (fast)
pytest tests/services/test_embedding_service.py -v

# Test semantic chunker (fast)
pytest tests/preprocessing/test_semantic_chunker.py -v

# View coverage report
pytest tests/services/ tests/preprocessing/ --cov=src/writeros --cov-report=html
open htmlcov/index.html  # View in browser
```

## What Was Implemented

1. **Test Infrastructure** (`tests/conftest.py`)
   - Async fixtures for pytest-asyncio
   - Mock services (embeddings, LLM)
   - Sample data fixtures

2. **Unit Tests** (No database required)
   - SemanticChunker tests
   - EmbeddingService tests

3. **Integration Tests** (Requires PostgreSQL)
   - Vector search tests
   - GraphRAG tests with cycle detection
   - E2E pipeline tests

4. **Coverage Target**: 95%+ for RAG components

## Troubleshooting

### "No module named 'src.writeros'"
```bash
pip install -e .
```

### "Connection refused" (PostgreSQL)
```bash
docker-compose up -d db
# Wait 5 seconds for DB to start
pytest
```

### Run only fast tests
```bash
pytest tests/services/ tests/preprocessing/ -v
```

## Next Steps

1. Start PostgreSQL: `docker-compose up -d db`
2. Run full test suite: `pytest --cov=src/writeros --cov-report=html`
3. View coverage: `open htmlcov/index.html`
4. Add more tests as needed to reach 95%+ coverage
