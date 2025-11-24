# WriterOS Test Suite

Comprehensive test suite achieving **95%+ code coverage** with special focus on RAG (Retrieval-Augmented Generation) implementation.

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── preprocessing/
│   └── test_semantic_chunker.py   # ClusterSemanticChunker tests
├── services/
│   └── test_embedding_service.py  # EmbeddingService tests
├── rag/
│   ├── test_vector_search.py      # pgvector operations
│   └── test_graph_rag.py          # GraphRAG traversal
├── agents/
│   └── test_profiler_agent.py     # Agent RAG integration
├── integration/
│   └── test_rag_pipeline_e2e.py   # End-to-end pipeline tests
└── README.md                      # This file
```

## Running Tests

### All Tests
```bash
pytest
```

### With Coverage Report
```bash
pytest --cov=src/writeros --cov-report=html --cov-report=term-missing
```

### By Category
```bash
# Unit tests only (fast, mocked)
pytest -m unit

# Integration tests (requires Docker PostgreSQL)
pytest -m integration

# End-to-end tests
pytest -m e2e

# Exclude slow tests
pytest -m "not slow"
```

### Specific Test Files
```bash
# Test semantic chunker
pytest tests/preprocessing/test_semantic_chunker.py -v

# Test vector search
pytest tests/rag/test_vector_search.py -v

# Test GraphRAG
pytest tests/rag/test_graph_rag.py -v
```

## Prerequisites

### 1. Install Dependencies
```bash
pip install -e ".[dev]"
```

### 2. Start Docker PostgreSQL (for integration tests)
```bash
docker-compose up -d db
```

### 3. Set Environment Variables
```bash
# Create .env file
OPENAI_API_KEY=your-test-key-here
```

## Test Markers

- `@pytest.mark.unit` - Fast unit tests with mocked dependencies
- `@pytest.mark.integration` - Integration tests requiring database
- `@pytest.mark.e2e` - End-to-end pipeline tests
- `@pytest.mark.slow` - Tests that take >1 second

## Key Test Coverage Areas

### 1. **Preprocessing (ClusterSemanticChunker)**
- ✅ Sentence segmentation
- ✅ Semantic boundary detection
- ✅ Chunk size constraints
- ✅ Noise filtering
- ✅ Edge cases (empty text, very long text)

### 2. **Embedding Service**
- ✅ Singleton pattern
- ✅ Query and batch embedding
- ✅ Error handling (missing API key)
- ✅ OpenAI API mocking

### 3. **Vector Search (pgvector)**
- ✅ Cosine similarity search
- ✅ L2 distance search
- ✅ Vault ID filtering
- ✅ Result ranking
- ✅ Empty result handling

### 4. **GraphRAG**
- ✅ Graph traversal (BFS/DFS)
- ✅ Relationship filtering
- ✅ Temporal filtering
- ✅ Max hops limiting
- ✅ Cycle detection (time travel paradox)
- ✅ Family tree construction

### 5. **Agent RAG Integration**
- ✅ ProfilerAgent entity search
- ✅ Graph data generation
- ✅ Family tree building
- ✅ LLM mocking

### 6. **End-to-End Pipeline**
- ✅ Ingest → Chunk → Embed → Store
- ✅ Query → Retrieve → Rank → Return
- ✅ Multi-hop GraphRAG queries
- ✅ Performance benchmarks

## Mocking Strategy

### LLM Calls
All LLM calls are mocked using `pytest-mock`:
```python
@pytest.fixture
def mock_llm_client(mocker):
    mock = mocker.patch("writeros.agents.base.ChatOpenAI")
    # ... mock implementation
```

### Embeddings
Embeddings return deterministic vectors:
```python
mock_embedding_service.embed_query.return_value = [0.1] * 1536
```

### Database
- **Unit tests**: In-memory SQLite or mocked
- **Integration tests**: Docker PostgreSQL with test database

## Coverage Goals

- **Overall**: 95%+ coverage
- **RAG Components**: 100% coverage
  - `preprocessing/chunker.py`
  - `utils/embeddings.py`
  - `utils/indexer.py`
- **Vector Search**: 100% coverage of all search operations
- **GraphRAG**: 100% coverage of traversal logic

## Viewing Coverage Report

After running tests with coverage:
```bash
# Open HTML report
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux
```

## Continuous Integration

Tests run automatically on:
- Every push to `main`
- Every pull request
- Nightly builds

CI uses Docker Compose to spin up PostgreSQL.

## Troubleshooting

### "No module named 'writeros'"
```bash
pip install -e .
```

### "Connection refused" (PostgreSQL)
```bash
docker-compose up -d db
# Wait 5 seconds for DB to start
pytest
```

### "OPENAI_API_KEY not found"
```bash
# Tests should use mocked LLM, but if needed:
export OPENAI_API_KEY=test-key
```

### Slow tests
```bash
# Skip slow tests
pytest -m "not slow"
```

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Ensure coverage stays above 95%
3. Add appropriate markers (`@pytest.mark.unit`, etc.)
4. Mock external dependencies
5. Run full test suite before committing

## Performance Benchmarks

- **Semantic Chunking**: <5s for 10,000 words
- **Vector Search**: <1s for 100 entities
- **GraphRAG Traversal**: <2s for 3-hop query
- **Full Test Suite**: <30s (unit tests), <2min (all tests)
