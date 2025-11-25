"""
Vault Indexer
Indexes Markdown files from the vault into the Vector Database using Semantic Chunking.

Features:
- Supports multiple chunking strategies (cluster, greedy, fixed, auto)
- Embedding caching for performance
- Automatic strategy selection based on document size
- Narrator extraction for unreliable narrator detection (Phase 2.5)
"""
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select, delete

from writeros.schema import Document
from writeros.preprocessing import UnifiedChunker, ChunkingStrategy
from writeros.utils.db import engine
from writeros.utils.embeddings import get_embedding_service
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class VaultIndexer:
    def __init__(
        self,
        vault_path: str,
        vault_id: UUID,
        embedding_model: str = "text-embedding-3-small",
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.AUTO,
        enable_cache: bool = True,
        override_metadata: Optional[Dict[str, Any]] = None
    ):
        self.vault_path = Path(vault_path)
        self.vault_id = vault_id

        # Override metadata for structured ingestion (Phase 2.5)
        self.override_metadata = override_metadata or {}

        # Initialize unified chunker with caching
        self.chunker = UnifiedChunker(
            strategy=chunking_strategy,
            min_chunk_size=50,
            max_chunk_size=400,
            enable_cache=enable_cache,
            cache_size=1000
        )

        # Helper for single embeddings if needed
        self.embedder = get_embedding_service()

        logger.info(
            "vault_indexer_initialized",
            vault_path=str(vault_path),
            vault_id=str(vault_id),
            strategy=chunking_strategy,
            cache_enabled=enable_cache,
            has_override_metadata=bool(self.override_metadata)
        )

    async def index_vault(
        self,
        directories: List[str] = None,
        force_reindex: bool = False,
        include_pdfs: bool = True
    ) -> Dict[str, Any]:
        """
        Index vault files into pgvector.

        Args:
            directories: Directories to index
            force_reindex: Delete existing documents first
            include_pdfs: Whether to process PDF files

        Returns:
            Dict with indexing results including chunking stats
        """
        if directories is None:
            directories = ["Story_Bible", "Writing_Bible", "Manuscripts"]

        if force_reindex:
            logger.info("force_reindex_triggered", vault_id=str(self.vault_id))
            with Session(engine) as session:
                statement = delete(Document).where(Document.vault_id == self.vault_id)
                session.exec(statement)
                session.commit()

        results = {
            "files_processed": 0,
            "chunks_created": 0,
            "pdfs_processed": 0,
            "errors": []
        }

        for directory in directories:
            dir_path = self.vault_path / directory
            if not dir_path.exists():
                continue

            # Process Markdown files
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

            # Process PDF files (if enabled)
            if include_pdfs:
                for pdf_file in dir_path.rglob("*.pdf"):
                    try:
                        chunks_count = await self.index_pdf(pdf_file)
                        results["pdfs_processed"] += 1
                        results["chunks_created"] += chunks_count
                    except Exception as e:
                        logger.error(
                            "pdf_indexing_failed",
                            file=str(pdf_file),
                            error=str(e)
                        )
                        results["errors"].append({
                            "file": str(pdf_file),
                            "error": str(e)
                        })

        # Add chunking statistics
        results["chunking_stats"] = self.chunker.get_stats()

        logger.info(
            "vault_indexing_complete",
            files=results["files_processed"],
            pdfs=results["pdfs_processed"],
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

        # 3. Extract narrator claims if configured (Phase 2.5)
        narrator_claims = []
        if self.override_metadata.get("has_unreliable_narrators"):
            narrator_claims = self.extract_narrator_claims(content)
            logger.info(
                "narrator_extraction_enabled",
                file=str(file_path),
                claims_found=len(narrator_claims)
            )

        # 4. Chunking using UnifiedChunker
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

        # 5. Database Transaction
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
                # Build metadata - merge override with chunk-specific metadata
                chunk_metadata = {
                    "source_file": relative_path,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "coherence_score": chunk.get("coherence_score", 1.0)
                }

                # Inject override metadata (Phase 2.5 - Citadel Pipeline)
                if self.override_metadata:
                    chunk_metadata.update(self.override_metadata)

                # Add narrator claims if extracted (Phase 2.5)
                if narrator_claims:
                    # Find claims that appear in this chunk
                    chunk_claims = [
                        claim for claim in narrator_claims
                        if claim["narrator"] in chunk["content"] or claim["claim"] in chunk["content"]
                    ]

                    if chunk_claims:
                        chunk_metadata["narrator_claims"] = chunk_claims
                        chunk_metadata["has_conflicting_sources"] = True

                doc = Document(
                    vault_id=self.vault_id,
                    title=f"{file_path.stem} (chunk {i+1})",
                    content=chunk["content"],
                    doc_type=doc_type,
                    embedding=chunk["embedding"],
                    metadata_=chunk_metadata
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

    async def index_pdf(self, file_path: Path) -> int:
        """
        Index a PDF file using PDFProcessor and ClusterSemanticChunker.

        Args:
            file_path: Path to PDF file

        Returns:
            Number of chunks created
        """
        try:
            # Lazy import to avoid dependency if not using PDFs
            from writeros.utils.pdf_processor import PDFProcessor

            logger.info(
                "indexing_pdf",
                file=str(file_path)
            )

            # Create PDF processor
            pdf_processor = PDFProcessor(
                vault_id=self.vault_id,
                chunking_strategy=ChunkingStrategy.AUTO,
                enable_cache=True
            )

            # Process PDF (without entity extraction - just chunking and storage)
            results = await pdf_processor.process_pdf(
                pdf_path=file_path,
                extract_entities=False,  # Entities extracted separately
                override_metadata=self.override_metadata
            )

            logger.info(
                "pdf_indexed",
                file=str(file_path),
                chunks=results["chunks_created"]
            )

            return results["chunks_created"]

        except ImportError as e:
            logger.error(
                "pdf_processor_import_failed",
                error=str(e),
                hint="Install PyPDF2: pip install PyPDF2"
            )
            return 0
        except Exception as e:
            logger.error(
                "pdf_indexing_failed",
                file=str(file_path),
                error=str(e)
            )
            raise

    def extract_narrator_claims(self, text: str) -> List[Dict[str, str]]:
        """
        Extract narrator attributions from text.

        Used for Phase 2.5 (Citadel Pipeline) to identify unreliable narrators.

        Patterns:
        - "Mushroom claims that..."
        - "According to Septon Eustace..."
        - "Grand Maester Munkun writes..."

        Returns:
            List of dicts with {"narrator": str, "claim": str}
        """
        claims = []

        # Pattern 1: "X claims that Y"
        pattern1 = r"(\w+(?:\s+\w+)*)\s+(?:claims?|states?|says?|writes?|reports?)\s+that\s+(.+?)(?:\.|;|,\s+and|$)"
        matches1 = re.finditer(pattern1, text, re.IGNORECASE)

        for match in matches1:
            narrator = match.group(1).strip()
            claim = match.group(2).strip()

            # Filter out common false positives
            if narrator.lower() not in ["he", "she", "they", "it", "the", "this"]:
                claims.append({
                    "narrator": narrator,
                    "claim": claim,
                    "pattern": "claims_that"
                })

        # Pattern 2: "According to X, Y"
        pattern2 = r"[Aa]ccording to\s+(\w+(?:\s+\w+)*),\s+(.+?)(?:\.|;|$)"
        matches2 = re.finditer(pattern2, text)

        for match in matches2:
            narrator = match.group(1).strip()
            claim = match.group(2).strip()

            claims.append({
                "narrator": narrator,
                "claim": claim,
                "pattern": "according_to"
            })

        # Pattern 3: "X's account states..."
        pattern3 = r"(\w+(?:\s+\w+)*)'s\s+account\s+(?:states?|claims?|says?)\s+(.+?)(?:\.|;|$)"
        matches3 = re.finditer(pattern3, text, re.IGNORECASE)

        for match in matches3:
            narrator = match.group(1).strip()
            claim = match.group(2).strip()

            claims.append({
                "narrator": narrator,
                "claim": claim,
                "pattern": "account_states"
            })

        if claims:
            logger.info(
                "narrator_claims_extracted",
                count=len(claims),
                narrators=list(set([c["narrator"] for c in claims]))
            )

        return claims
