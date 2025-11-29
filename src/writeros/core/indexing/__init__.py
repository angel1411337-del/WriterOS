"""
Core Indexing Pipeline

Modular, production-grade indexing architecture for WriterOS.

Components:
- pipeline.py: Main orchestrator
- chunker.py: Text chunking strategies
- embedder.py: Embedding generation
- extractor.py: Entity & relationship extraction
- linker.py: Bidirectional linking

This package represents the next-generation indexing system with:
- Clear separation of concerns
- Dependency injection
- Testable components
- Async/await throughout
"""

from .pipeline import IndexingPipeline, IndexingResult, ChunkExtractionResult

__all__ = [
    "IndexingPipeline",
    "IndexingResult",
    "ChunkExtractionResult",
]
