"""
Cluster Semantic Chunker
Splits text into chunks based on semantic similarity using embeddings.
"""
from typing import List, Dict, Any, Optional
import numpy as np
from dataclasses import dataclass
import re

@dataclass
class Chunk:
    content: str
    embedding: List[float]
    coherence_score: float

class SemanticChunker:
    def __init__(
        self,
        min_chunk_size: int = 50,
        max_chunk_size: int = 400,
        embedding_model: str = "text-embedding-3-small"
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.embedding_model = embedding_model
        
        # Initialize embedding service (lazy load)
        self._embedder = None

    @property
    def embedder(self):
        if self._embedder is None:
            from writeros.utils.embeddings import EmbeddingService
            self._embedder = EmbeddingService()
        return self._embedder

    async def chunk_document(self, text: str, document_type: str = "default") -> List[Dict[str, Any]]:
        """
        Split document into semantically coherent chunks.
        """
        # 1. Split into sentences/segments
        segments = self._split_into_segments(text)
        
        if not segments:
            return []
            
        # 2. Embed all segments
        embeddings = await self.embedder.get_embeddings(segments)
        
        # 3. Cluster segments into chunks
        chunks = self._cluster_segments(segments, embeddings)
        
        return [
            {
                "content": chunk.content,
                "embedding": chunk.embedding,
                "coherence_score": chunk.coherence_score
            }
            for chunk in chunks
        ]

    def _split_into_segments(self, text: str) -> List[str]:
        """Split text into sentences or logical segments."""
        # Simple sentence splitting for now
        # In production, use spacy or nltk
        text = text.replace("\n", " ").replace("  ", " ")
        segments = re.split(r'(?<=[.!?]) +', text)
        return [s.strip() for s in segments if s.strip()]

    def _cluster_segments(self, segments: List[str], embeddings: List[List[float]]) -> List[Chunk]:
        """
        Group segments into chunks based on cosine similarity.
        """
        chunks: List[Chunk] = []
        current_chunk_segments: List[str] = []
        current_chunk_embeddings: List[List[float]] = []
        
        for i, (seg, emb) in enumerate(zip(segments, embeddings)):
            current_chunk_segments.append(seg)
            current_chunk_embeddings.append(emb)
            
            current_text = " ".join(current_chunk_segments)
            current_tokens = len(current_text.split()) # Approx token count
            
            # If chunk is getting too big, force split
            if current_tokens >= self.max_chunk_size:
                self._finalize_chunk(chunks, current_chunk_segments, current_chunk_embeddings)
                current_chunk_segments = []
                current_chunk_embeddings = []
                continue
                
            # Check semantic shift if we have enough content
            if current_tokens > self.min_chunk_size and i < len(segments) - 1:
                # Compare current chunk average embedding with next segment
                current_avg = np.mean(current_chunk_embeddings, axis=0)
                next_emb = embeddings[i+1]
                
                similarity = np.dot(current_avg, next_emb) / (np.linalg.norm(current_avg) * np.linalg.norm(next_emb))
                
                # Threshold for splitting (tunable)
                if similarity < 0.7: # Semantic shift detected
                    self._finalize_chunk(chunks, current_chunk_segments, current_chunk_embeddings)
                    current_chunk_segments = []
                    current_chunk_embeddings = []

        # Finalize last chunk
        if current_chunk_segments:
            self._finalize_chunk(chunks, current_chunk_segments, current_chunk_embeddings)
            
        return chunks

    def _finalize_chunk(self, chunks: List[Chunk], segments: List[str], embeddings: List[List[float]]):
        if not segments:
            return

        content = " ".join(segments)
        # Calculate centroid embedding for the chunk
        avg_embedding_np = np.mean(embeddings, axis=0)
        avg_embedding = avg_embedding_np.tolist()

        # Calculate coherence (avg similarity to centroid)
        centroid_norm = np.linalg.norm(avg_embedding_np)
        similarities = []

        for emb in embeddings:
            emb_np = np.array(emb)
            emb_norm = np.linalg.norm(emb_np)

            if centroid_norm == 0 or emb_norm == 0:
                similarities.append(0.0)
                continue

            sim = float(np.dot(emb_np, avg_embedding_np) / (centroid_norm * emb_norm))
            similarities.append(sim)

        mean_similarity = float(np.mean(similarities)) if similarities else 0.0
        coherence = float(np.clip((mean_similarity + 1) / 2, 0.0, 1.0))

        chunks.append(Chunk(
            content=content,
            embedding=avg_embedding,
            coherence_score=coherence
        ))
