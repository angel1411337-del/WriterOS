"""
Unified Chunker - Supports multiple chunking strategies with caching.

Strategies:
1. ClusterSemanticChunker - Global optimization (best quality, slower)
2. SemanticChunker - Greedy local decisions (fast, good quality)
3. FixedSizeChunker - Simple token-based splitting (fastest, lower quality)

Features:
- Embedding cache for repeated calls
- Strategy selection based on document size
- Performance monitoring
"""
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass
import hashlib
import time
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class ChunkingStrategy(str, Enum):
    """Available chunking strategies."""
    CLUSTER_SEMANTIC = "cluster_semantic"  # Global DP optimization
    GREEDY_SEMANTIC = "greedy_semantic"    # Local greedy decisions
    FIXED_SIZE = "fixed_size"              # Simple token-based
    NARRATIVE = "narrative"                # Fiction-optimized (preserves scenes, dialogue, chronology)
    AUTO = "auto"                          # Automatically choose based on doc size


@dataclass
class ChunkedDocument:
    """Result of document chunking."""
    chunks: List[str]
    embeddings: Optional[List[List[float]]] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class EmbeddingCache:
    """LRU cache for embeddings to avoid repeated API calls."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[str, List[float]] = {}
        self.access_order: List[str] = []
        self.hits = 0
        self.misses = 0

    def get(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache."""
        key = self._hash(text)

        if key in self.cache:
            self.hits += 1
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]

        self.misses += 1
        return None

    def put(self, text: str, embedding: List[float]):
        """Store embedding in cache."""
        key = self._hash(text)

        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            oldest_key = self.access_order.pop(0)
            del self.cache[oldest_key]

        self.cache[key] = embedding
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)

    def _hash(self, text: str) -> str:
        """Generate hash key for text."""
        return hashlib.md5(text.encode()).hexdigest()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate
        }

    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.access_order.clear()
        self.hits = 0
        self.misses = 0


class UnifiedChunker:
    """
    Unified interface for multiple chunking strategies.

    Features:
    - Multiple strategies (cluster, greedy, fixed)
    - Automatic strategy selection based on document size
    - Embedding caching
    - Performance monitoring

    Usage:
        chunker = UnifiedChunker(strategy="auto")
        result = chunker.chunk(text, embedding_function=embed_fn)
    """

    def __init__(
        self,
        strategy: ChunkingStrategy = ChunkingStrategy.AUTO,
        min_chunk_size: int = 50,
        max_chunk_size: int = 400,
        cache_size: int = 1000,
        enable_cache: bool = True
    ):
        self.strategy = strategy
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.enable_cache = enable_cache

        # Initialize cache
        self.cache = EmbeddingCache(max_size=cache_size) if enable_cache else None

        # Lazy-load chunkers
        self._cluster_chunker = None
        self._greedy_chunker = None
        self._fixed_chunker = None
        self._narrative_chunker = None

        # Performance stats
        self.stats = {
            "total_chunks": 0,
            "total_documents": 0,
            "total_time": 0.0,
            "strategy_usage": {}
        }

        logger.info(
            "unified_chunker_initialized",
            strategy=strategy,
            cache_enabled=enable_cache,
            cache_size=cache_size
        )

    def chunk(
        self,
        text: str,
        embedding_function: Optional[Callable[[str], List[float]]] = None,
        strategy: Optional[ChunkingStrategy] = None
    ) -> ChunkedDocument:
        """
        Chunk text using specified or auto-selected strategy.

        Args:
            text: Input text to chunk
            embedding_function: Function that takes str → List[float]
            strategy: Override default strategy for this call

        Returns:
            ChunkedDocument with chunks and metadata
        """
        start_time = time.time()

        # Select strategy
        selected_strategy = strategy or self.strategy
        if selected_strategy == ChunkingStrategy.AUTO:
            selected_strategy = self._auto_select_strategy(text)

        logger.info(
            "chunking_document",
            strategy=selected_strategy,
            text_length=len(text)
        )

        # Wrap embedding function with cache
        if self.enable_cache and embedding_function:
            embedding_fn = self._cached_embed(embedding_function)
        else:
            embedding_fn = embedding_function

        # Execute chunking
        if selected_strategy == ChunkingStrategy.CLUSTER_SEMANTIC:
            result = self._chunk_cluster(text, embedding_fn)
        elif selected_strategy == ChunkingStrategy.GREEDY_SEMANTIC:
            result = self._chunk_greedy(text, embedding_fn)
        elif selected_strategy == ChunkingStrategy.NARRATIVE:
            result = self._chunk_narrative(text)
        else:  # FIXED_SIZE
            result = self._chunk_fixed(text)

        # Update stats
        duration = time.time() - start_time
        self.stats["total_documents"] += 1
        self.stats["total_chunks"] += len(result.chunks)
        self.stats["total_time"] += duration
        self.stats["strategy_usage"][selected_strategy] = \
            self.stats["strategy_usage"].get(selected_strategy, 0) + 1

        # Add metadata
        result.metadata.update({
            "strategy": selected_strategy,
            "duration": duration,
            "cache_stats": self.cache.get_stats() if self.cache else None
        })

        logger.info(
            "chunking_complete",
            chunks=len(result.chunks),
            duration=duration,
            strategy=selected_strategy
        )

        return result

    def _auto_select_strategy(self, text: str) -> ChunkingStrategy:
        """
        Automatically select best strategy based on document characteristics.

        Heuristics:
        - Small docs (< 2000 tokens): Use cluster (best quality)
        - Medium docs (2000-10000 tokens): Use greedy (good balance)
        - Large docs (> 10000 tokens): Use fixed (fastest)
        """
        # Rough token count (split on whitespace)
        approx_tokens = len(text.split())

        if approx_tokens < 2000:
            return ChunkingStrategy.CLUSTER_SEMANTIC
        elif approx_tokens < 10000:
            return ChunkingStrategy.GREEDY_SEMANTIC
        else:
            return ChunkingStrategy.FIXED_SIZE

    def _cached_embed(self, embed_fn: Callable) -> Callable:
        """Wrap embedding function with caching."""
        def cached_fn(text: str) -> List[float]:
            # Check cache first
            cached = self.cache.get(text)
            if cached is not None:
                return cached

            # Call actual embedding function
            embedding = embed_fn(text)

            # Store in cache
            self.cache.put(text, embedding)

            return embedding

        return cached_fn

    def _chunk_cluster(
        self,
        text: str,
        embedding_fn: Optional[Callable]
    ) -> ChunkedDocument:
        """Chunk using ClusterSemanticChunker."""
        # Always create fresh instance to use current embedding_fn (which may be cached)
        from writeros.preprocessing.cluster_semantic_chunker import ClusterSemanticChunker
        chunker = ClusterSemanticChunker(
            min_chunk_size=self.min_chunk_size,
            max_chunk_size=self.max_chunk_size,
            embedding_function=embedding_fn
        )

        result = chunker.chunk(text)

        return ChunkedDocument(
            chunks=result.chunks,
            metadata=result.metadata
        )

    def _chunk_greedy(
        self,
        text: str,
        embedding_fn: Optional[Callable]
    ) -> ChunkedDocument:
        """Chunk using greedy SemanticChunker."""
        if self._greedy_chunker is None:
            from writeros.preprocessing.chunker import SemanticChunker
            self._greedy_chunker = SemanticChunker(
                min_chunk_size=self.min_chunk_size,
                max_chunk_size=self.max_chunk_size
            )

        # Handle async execution properly
        import asyncio
        import threading

        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()
            # We're in an async context - run in a separate thread
            result_holder = []
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result_holder.append(
                    new_loop.run_until_complete(
                        self._greedy_chunker.chunk_document(text)
                    )
                )
                new_loop.close()

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            result = result_holder[0]
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            result = asyncio.run(
                self._greedy_chunker.chunk_document(text)
            )

        chunks = [r["content"] for r in result]
        embeddings = [r["embedding"] for r in result]

        return ChunkedDocument(
            chunks=chunks,
            embeddings=embeddings,
            metadata={"segments": len(chunks)}
        )

    def _chunk_narrative(self, text: str) -> ChunkedDocument:
        """Chunk using narrative-aware strategy (fiction-optimized)."""
        if self._narrative_chunker is None:
            from writeros.preprocessing.narrative_chunker import NarrativeChunker
            self._narrative_chunker = NarrativeChunker(
                target_tokens=self.max_chunk_size // 2,  # Use half of max as target
                max_tokens=self.max_chunk_size,
                min_tokens=self.min_chunk_size,
            )

        # Chunk using narrative strategy
        raw_chunks = self._narrative_chunker.chunk_file(
            content=text,
            file_path="unknown",
        )

        # Convert to ChunkedDocument format
        chunks = [chunk.content for chunk in raw_chunks]

        # Extract metadata
        num_scenes = len(set(chunk.scene_index for chunk in raw_chunks))
        section_types = [chunk.section_type for chunk in raw_chunks]

        return ChunkedDocument(
            chunks=chunks,
            metadata={
                "segments": len(chunks),
                "num_scenes": num_scenes,
                "section_types": section_types,
            }
        )

    def _chunk_fixed(self, text: str) -> ChunkedDocument:
        """Chunk using simple fixed-size splitting."""
        if self._fixed_chunker is None:
            import tiktoken
            self._fixed_chunker = tiktoken.get_encoding("cl100k_base")

        # Encode text
        tokens = self._fixed_chunker.encode(text)

        # Split into chunks
        chunks = []
        for i in range(0, len(tokens), self.max_chunk_size):
            chunk_tokens = tokens[i:i + self.max_chunk_size]
            chunk_text = self._fixed_chunker.decode(chunk_tokens)
            chunks.append(chunk_text)

        return ChunkedDocument(
            chunks=chunks,
            metadata={"segments": len(chunks), "total_tokens": len(tokens)}
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = self.stats.copy()

        if self.cache:
            stats["cache"] = self.cache.get_stats()

        # Calculate averages
        if stats["total_documents"] > 0:
            stats["avg_chunks_per_doc"] = stats["total_chunks"] / stats["total_documents"]
            stats["avg_time_per_doc"] = stats["total_time"] / stats["total_documents"]

        return stats

    def clear_cache(self):
        """Clear embedding cache."""
        if self.cache:
            self.cache.clear()
            logger.info("cache_cleared")


# Convenience function for simple usage
def chunk_text(
    text: str,
    strategy: ChunkingStrategy = ChunkingStrategy.AUTO,
    embedding_function: Optional[Callable] = None,
    **kwargs
) -> ChunkedDocument:
    """
    Convenience function to chunk text with sensible defaults.

    Args:
        text: Text to chunk
        strategy: Chunking strategy to use
        embedding_function: Optional embedding function
        **kwargs: Additional arguments passed to UnifiedChunker

    Returns:
        ChunkedDocument with chunks and metadata

    Example:
        from writeros.utils.embeddings import get_embedding_service
        result = chunk_text(
            text="Long document...",
            strategy="cluster_semantic",
            embedding_function=get_embedding_service().embed_query
        )
    """
    chunker = UnifiedChunker(strategy=strategy, **kwargs)
    return chunker.chunk(text, embedding_function=embedding_function)
