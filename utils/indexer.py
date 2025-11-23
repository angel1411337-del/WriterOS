"""
Vault Indexer
Indexes Markdown files from the vault into the Vector Database using Semantic Chunking.
"""
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select, delete

from src.writeros.schema import Document
from preprocessing.chunker import SemanticChunker
from utils.db import engine
from utils.embeddings import EmbeddingService

class VaultIndexer:
    def __init__(
        self,
        vault_path: str,
        vault_id: UUID,
        embedding_model: str = "text-embedding-3-small"
    ):
        self.vault_path = Path(vault_path)
        self.vault_id = vault_id
        
        self.chunker = SemanticChunker(
            min_chunk_size=50,
            max_chunk_size=400,
            embedding_model=embedding_model
        )
        
        # Helper for single embeddings if needed
        self.embedder = EmbeddingService()

    async def index_vault(self, directories: List[str] = None) -> Dict[str, Any]:
        """
        Index vault files into pgvector.
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
                    results["errors"].append({
                        "file": str(md_file),
                        "error": str(e)
                    })
        
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
        
        # 3. Chunking
        # If very short, treat as single chunk
        if len(content.split()) < 50:
            embedding = await self.embedder.get_embedding(content)
            chunks = [{
                "content": content,
                "embedding": embedding,
                "coherence_score": 1.0
            }]
        else:
            chunks = await self.chunker.chunk_document(content, document_type=doc_type)

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
