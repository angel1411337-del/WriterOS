"""
Vault Indexer
Indexes Markdown files from the vault into the Vector Database using Semantic Chunking.

Features:
- Supports multiple chunking strategies (cluster, greedy, fixed, auto)
- Embedding caching for performance
- Automatic strategy selection based on document size
"""
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select, delete

from writeros.schema import Document
from writeros.preprocessing import UnifiedChunker, ChunkingStrategy
from writeros.utils.db import engine
from writeros.utils.embeddings import EmbeddingService
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class VaultIndexer:
    def __init__(
        self,
        vault_path: str,
        vault_id: UUID,
        embedding_model: str = "text-embedding-3-small",
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.AUTO,
        enable_cache: bool = True
    ):
        self.vault_path = Path(vault_path)
        self.vault_id = vault_id

        # Initialize unified chunker with caching
        self.chunker = UnifiedChunker(
            strategy=chunking_strategy,
            min_chunk_size=50,
            max_chunk_size=400,
            enable_cache=enable_cache,
            cache_size=1000
        )

        # Helper for single embeddings if needed
        self.embedder = EmbeddingService()

        logger.info(
            "vault_indexer_initialized",
            vault_path=str(vault_path),
            vault_id=str(vault_id),
            strategy=chunking_strategy,
            cache_enabled=enable_cache
        )

    async def index_vault(self, directories: List[str] = None) -> Dict[str, Any]:
        """
        Index vault files into pgvector.

        Returns:
            Dict with indexing results including chunking stats
        """
        if directories is None:
            directories = ["Story_Bible", "Writing_Bible", "Manuscripts"]

        results = {
            "files_processed": 0,
            "chunks_created": 0,
            "errors": []
        }

        for directory in directories:
            dir_path = self.vault_path / directory
            if not dir_path.exists():
                continue

            for md_file in dir_path.rglob("*.md"):
                try:
                    chunks_count = await self.index_file(md_file)
                    results["files_processed"] += 1
                    results["chunks_created"] += chunks_count
                except Exception as e:
                    logger.error(
                        "file_indexing_failed",
                        file=str(md_file),
                        error=str(e)
                    )
                    results["errors"].append({
                        "file": str(md_file),
                        "error": str(e)
                    })

        # Add chunking statistics
        results["chunking_stats"] = self.chunker.get_stats()

        logger.info(
            "vault_indexing_complete",
            files=results["files_processed"],
            chunks=results["chunks_created"],
            errors=len(results["errors"])
        )

        return results

    async def index_file(self, file_path: Path) -> int:
        """
        Index a single file using ClusterSemanticChunker.
        Returns number of chunks created.
        """
        # 1. Read content
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Fallback for non-utf8
            content = file_path.read_text(encoding='latin-1')
            
        if not content.strip():
            return 0

        # 2. Determine Doc Type
        doc_type = self._infer_doc_type(file_path)

        # 3. Chunking using UnifiedChunker
        logger.info(
            "chunking_file",
            file=str(file_path),
            content_length=len(content)
        )

        result = self.chunker.chunk(
            text=content,
            embedding_function=self.embedder.embed_query
        )

        # Convert to format expected by database
        chunks = []
        for i, chunk_text in enumerate(result.chunks):
            # Get or compute embedding for chunk
            if result.embeddings and i < len(result.embeddings):
                embedding = result.embeddings[i]
            else:
                # Compute embedding if not already done
                embedding = self.embedder.embed_query(chunk_text)

            chunks.append({
                "content": chunk_text,
                "embedding": embedding,
                "coherence_score": 1.0  # Placeholder
            })

        logger.info(
            "file_chunked",
            file=str(file_path),
            chunks=len(chunks),
            strategy=result.metadata.get("strategy"),
            duration=result.metadata.get("duration")
        )

        # 4. Database Transaction
        relative_path = str(file_path.relative_to(self.vault_path)).replace("\\", "/")
        
        with Session(engine) as session:
            # Delete existing chunks for this file (Re-index)
            statement = delete(Document).where(
                Document.vault_id == self.vault_id,
                Document.metadata_['source_file'].astext == relative_path
            )
            session.exec(statement)
            
            # Insert new chunks
            for i, chunk in enumerate(chunks):
                doc = Document(
                    vault_id=self.vault_id,
                    title=f"{file_path.stem} (chunk {i+1})",
                    content=chunk["content"],
                    doc_type=doc_type,
                    embedding=chunk["embedding"],
                    metadata_={
                        "source_file": relative_path,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "coherence_score": chunk.get("coherence_score", 1.0)
                    }
                )
                session.add(doc)
            
            session.commit()
            
        return len(chunks)

    def _infer_doc_type(self, file_path: Path) -> str:
        """Infer document type from file path."""
        path_str = str(file_path).replace("\\", "/")

        if "Characters" in path_str:
            return "character"
        elif "Locations" in path_str:
            return "location"
        elif "Factions" in path_str:
            return "faction"
        elif "Writing_Bible" in path_str:
            return "craft_advice"
        elif "Manuscripts" in path_str:
            return "manuscript"
        else:
            return "note"

    def get_stats(self) -> Dict[str, Any]:
        """
        Get chunking performance statistics.

        Returns:
            Dict with cache stats, strategy usage, and performance metrics
        """
        return self.chunker.get_stats()

    def clear_cache(self):
        """Clear the embedding cache."""
        self.chunker.clear_cache()
        logger.info("indexer_cache_cleared")
