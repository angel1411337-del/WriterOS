"""
WriterOS Preprocessing Module

Text processing and chunking utilities for RAG pipelines.
"""

from writeros.preprocessing.cluster_semantic_chunker import (
    ClusterSemanticChunker,
    ChunkResult
)
from writeros.preprocessing.chunker import (
    SemanticChunker,
    Chunk
)
from writeros.preprocessing.unified_chunker import (
    UnifiedChunker,
    ChunkingStrategy,
    ChunkedDocument,
    EmbeddingCache,
    chunk_text
)

__all__ = [
    # Cluster semantic chunker (global optimization)
    "ClusterSemanticChunker",
    "ChunkResult",

    # Greedy semantic chunker (local decisions)
    "SemanticChunker",
    "Chunk",

    # Unified interface
    "UnifiedChunker",
    "ChunkingStrategy",
    "ChunkedDocument",
    "EmbeddingCache",
    "chunk_text",
]
