"""
ClusterSemanticChunker - Global semantic chunking via dynamic programming.

This implementation follows the algorithm from Chroma Research:
https://research.trychroma.com/evaluating-chunking

Key idea: Maximize total intra-chunk similarity while respecting max chunk size.
Uses dynamic programming to find the globally optimal segmentation.
"""
from typing import List, Tuple, Optional, Callable
import numpy as np
from dataclasses import dataclass
import tiktoken
from writeros.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkResult:
    """Result of chunking operation."""
    chunks: List[str]
    metadata: dict


class ClusterSemanticChunker:
    """
    Global semantic chunker using dynamic programming optimization.

    Algorithm:
    1. Split text into small base segments (e.g., 50 tokens each)
    2. Embed all segments
    3. Build similarity matrix (cosine similarity, mean-centered)
    4. Use DP to find optimal segmentation that maximizes intra-chunk similarity
    5. Merge segments into final chunks

    Params:
        min_chunk_size: Size of base segments (tokens)
        max_chunk_size: Maximum tokens per final chunk
        embedding_function: Function that takes str → List[float]
        tokenizer: Tiktoken encoding name (default: "cl100k_base" for OpenAI)
    """

    def __init__(
        self,
        min_chunk_size: int = 50,
        max_chunk_size: int = 400,
        embedding_function: Optional[Callable[[str], List[float]]] = None,
        tokenizer: str = "cl100k_base"
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.embedding_function = embedding_function

        # Load tokenizer
        try:
            self.tokenizer = tiktoken.get_encoding(tokenizer)
        except Exception as e:
            logger.warning("tokenizer_load_failed", error=str(e), fallback="cl100k_base")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Compute max clusters per chunk
        self.max_cluster = max(1, max_chunk_size // min_chunk_size)

        logger.info(
            "cluster_semantic_chunker_initialized",
            min_chunk_size=min_chunk_size,
            max_chunk_size=max_chunk_size,
            max_cluster=self.max_cluster
        )

    def chunk(self, text: str) -> ChunkResult:
        """
        Chunk text using global semantic optimization.

        Args:
            text: Input text to chunk

        Returns:
            ChunkResult with chunks and metadata
        """
        if not text or not text.strip():
            return ChunkResult(chunks=[], metadata={"segments": 0, "chunks": 0})

        # Step 1: Split into base segments
        logger.info("splitting_base_segments", min_chunk_size=self.min_chunk_size)
        base_segments = self._split_into_base_segments(text)

        if len(base_segments) == 0:
            return ChunkResult(chunks=[], metadata={"segments": 0, "chunks": 0})

        if len(base_segments) == 1:
            return ChunkResult(
                chunks=base_segments,
                metadata={"segments": 1, "chunks": 1, "avg_chunk_size": len(text)}
            )

        logger.info("base_segments_created", count=len(base_segments))

        # Step 2: Embed all segments
        if self.embedding_function is None:
            # Fallback: use simple token-overlap similarity
            logger.warning("no_embedding_function", fallback="token_overlap")
            return self._chunk_with_token_overlap(base_segments)

        logger.info("embedding_segments", count=len(base_segments))
        embeddings = self._embed_segments(base_segments)

        # Step 3: Build similarity matrix
        logger.info("building_similarity_matrix")
        similarity_matrix = self._build_similarity_matrix(embeddings)

        # Step 4: Find optimal segmentation via DP
        logger.info("finding_optimal_segmentation", max_cluster=self.max_cluster)
        chunk_boundaries = self._find_optimal_segmentation(similarity_matrix)

        # Step 5: Merge segments into final chunks
        chunks = self._merge_segments(base_segments, chunk_boundaries)

        # Compute metadata
        avg_chunk_size = sum(len(c) for c in chunks) / len(chunks) if chunks else 0

        logger.info(
            "chunking_complete",
            segments=len(base_segments),
            chunks=len(chunks),
            avg_chunk_size=int(avg_chunk_size)
        )

        return ChunkResult(
            chunks=chunks,
            metadata={
                "segments": len(base_segments),
                "chunks": len(chunks),
                "avg_chunk_size": avg_chunk_size,
                "algorithm": "cluster_semantic"
            }
        )

    def _split_into_base_segments(self, text: str) -> List[str]:
        """
        Split text into small base segments of approximately min_chunk_size tokens.

        Strategy:
        1. Try to split on paragraph boundaries (\n\n)
        2. Fall back to sentence boundaries (. ! ?)
        3. Fall back to token count if needed
        """
        # First try paragraph splitting
        paragraphs = text.split('\n\n')
        segments = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Count tokens in paragraph
            token_count = len(self.tokenizer.encode(para))

            if token_count <= self.min_chunk_size:
                # Small enough, keep as is
                segments.append(para)
            else:
                # Split into sentences
                sentences = self._split_sentences(para)

                # Group sentences into min_chunk_size token segments
                current_segment = []
                current_tokens = 0

                for sent in sentences:
                    sent_tokens = len(self.tokenizer.encode(sent))

                    if current_tokens + sent_tokens <= self.min_chunk_size * 1.5:
                        # Add to current segment (allow 50% overflow)
                        current_segment.append(sent)
                        current_tokens += sent_tokens
                    else:
                        # Flush current segment
                        if current_segment:
                            segments.append(' '.join(current_segment))
                        current_segment = [sent]
                        current_tokens = sent_tokens

                # Flush remaining
                if current_segment:
                    segments.append(' '.join(current_segment))

        return segments

    def _split_sentences(self, text: str) -> List[str]:
        """Simple sentence splitter on . ! ?"""
        import re
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _embed_segments(self, segments: List[str]) -> np.ndarray:
        """
        Embed all segments using the embedding function.

        Returns:
            NxD array where N = len(segments), D = embedding dimension
        """
        embeddings = []

        # Batch embed for efficiency
        for segment in segments:
            try:
                emb = self.embedding_function(segment)
                embeddings.append(emb)
            except Exception as e:
                logger.error("embedding_failed", error=str(e), segment_preview=segment[:50])
                # Use zero vector as fallback
                embeddings.append([0.0] * 1536)  # Standard OpenAI dimension

        return np.array(embeddings, dtype=np.float32)

    def _build_similarity_matrix(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Build mean-centered cosine similarity matrix.

        Process:
        1. Compute pairwise cosine similarities
        2. Compute mean off-diagonal value
        3. Subtract mean (center the matrix)
        4. Zero out diagonal (don't reward self-similarity)

        Returns:
            NxN mean-centered similarity matrix
        """
        N = len(embeddings)

        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized = embeddings / norms

        # Compute cosine similarity matrix: normalized @ normalized.T
        similarity = normalized @ normalized.T

        # Compute mean off-diagonal value
        # (sum of all - diagonal) / (N^2 - N)
        total_sum = similarity.sum()
        diagonal_sum = np.trace(similarity)
        off_diagonal_sum = total_sum - diagonal_sum

        if N > 1:
            mean_similarity = off_diagonal_sum / (N * N - N)
        else:
            mean_similarity = 0.0

        # Mean-center the matrix
        similarity = similarity - mean_similarity

        # Zero out diagonal
        np.fill_diagonal(similarity, 0)

        logger.debug(
            "similarity_matrix_built",
            size=N,
            mean=float(mean_similarity),
            min=float(similarity.min()),
            max=float(similarity.max())
        )

        return similarity

    def _compute_chunk_reward(
        self,
        similarity_matrix: np.ndarray,
        start: int,
        end: int
    ) -> float:
        """
        Compute reward for a chunk spanning [start, end] inclusive.

        Reward = sum of all similarities within the chunk's sub-matrix.
        Higher reward means more semantically coherent chunk.
        """
        if start > end or start < 0 or end >= len(similarity_matrix):
            return 0.0

        # Extract sub-matrix
        sub_matrix = similarity_matrix[start:end+1, start:end+1]

        # Sum all similarities (including diagonal which is 0)
        reward = float(sub_matrix.sum())

        return reward

    def _find_optimal_segmentation(
        self,
        similarity_matrix: np.ndarray
    ) -> List[Tuple[int, int]]:
        """
        Find globally optimal segmentation using dynamic programming.

        DP recurrence:
        dp[i] = maximum total reward for segments [0..i]

        For each i, try all possible last chunk sizes:
          size ∈ [1, min(i+1, max_cluster)]
          start = i - size + 1
          candidate_reward = reward(start, i) + dp[start-1]

        Choose size that maximizes candidate_reward.

        Returns:
            List of (start, end) tuples representing optimal chunks
        """
        N = len(similarity_matrix)

        # DP arrays
        dp = np.zeros(N, dtype=np.float32)
        start_idx = np.zeros(N, dtype=np.int32)

        # Fill DP table
        for i in range(N):
            best_score = float('-inf')
            best_start = 0

            # Try all possible chunk sizes ending at i
            max_size = min(i + 1, self.max_cluster)

            for size in range(1, max_size + 1):
                start = i - size + 1

                # Compute reward for chunk [start, i]
                reward = self._compute_chunk_reward(similarity_matrix, start, i)

                # Add previous best if not first chunk
                if start > 0:
                    reward += dp[start - 1]

                # Update best
                if reward > best_score:
                    best_score = reward
                    best_start = start

            dp[i] = best_score
            start_idx[i] = best_start

        # Backtrack to reconstruct chunks
        chunks = []
        i = N - 1

        while i >= 0:
            start = start_idx[i]
            chunks.append((start, i))
            i = start - 1

        chunks.reverse()

        logger.info(
            "optimal_segmentation_found",
            num_chunks=len(chunks),
            total_reward=float(dp[N-1])
        )

        return chunks

    def _merge_segments(
        self,
        base_segments: List[str],
        chunk_boundaries: List[Tuple[int, int]]
    ) -> List[str]:
        """Merge base segments according to chunk boundaries."""
        chunks = []

        for start, end in chunk_boundaries:
            # Join segments [start, end] inclusive
            chunk_text = ' '.join(base_segments[start:end+1])
            chunks.append(chunk_text)

        return chunks

    def _chunk_with_token_overlap(self, segments: List[str]) -> ChunkResult:
        """
        Fallback chunker when no embedding function provided.
        Uses simple token overlap heuristic.
        """
        # Group segments greedily by token count
        chunks = []
        current_chunk = []
        current_tokens = 0

        for segment in segments:
            seg_tokens = len(self.tokenizer.encode(segment))

            if current_tokens + seg_tokens <= self.max_chunk_size:
                current_chunk.append(segment)
                current_tokens += seg_tokens
            else:
                # Flush current chunk
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [segment]
                current_tokens = seg_tokens

        # Flush remaining
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return ChunkResult(
            chunks=chunks,
            metadata={
                "segments": len(segments),
                "chunks": len(chunks),
                "algorithm": "token_overlap_fallback"
            }
        )
