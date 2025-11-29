"""
PDF Processor for WriterOS

Extracts text from PDFs, processes through ClusterSemanticChunker,
and populates the knowledge graph with entities and relationships.

Features:
- PDF text extraction with PyPDF2
- Metadata extraction (title, author, page count)
- Integration with ClusterSemanticChunker
- Entity extraction from chunks
- Automatic graph population
"""
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from writeros.preprocessing import UnifiedChunker, ChunkingStrategy
from writeros.agents.profiler import ProfilerAgent
from writeros.schema import Document, Entity, Relationship, EntityType, RelationType
from writeros.utils.embeddings import get_embedding_service
from writeros.utils.db import engine
from writeros.core.logging import get_logger
from sqlmodel import Session, select, delete

logger = get_logger(__name__)


class PDFProcessor:
    """
    Processes PDF files for WriterOS knowledge graph.

    Workflow:
    1. Extract text from PDF
    2. Extract metadata (title, author, page count)
    3. Chunk text using ClusterSemanticChunker
    4. Extract entities from chunks using ProfilerAgent
    5. Create relationships between entities
    6. Store in database
    """

    def __init__(
        self,
        vault_id: UUID,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.AUTO,
        enable_cache: bool = True
    ):
        if PyPDF2 is None:
            raise ImportError(
                "PyPDF2 is required for PDF processing. "
                "Install with: pip install PyPDF2"
            )

        self.vault_id = vault_id

        # Initialize chunker
        self.chunker = UnifiedChunker(
            strategy=chunking_strategy,
            min_chunk_size=100,  # Larger for PDFs
            max_chunk_size=600,
            enable_cache=enable_cache,
            cache_size=1000
        )

        # Initialize embedding service
        self.embedder = get_embedding_service()

        # Initialize profiler for entity extraction
        self.profiler = ProfilerAgent()

        logger.info(
            "pdf_processor_initialized",
            vault_id=str(vault_id),
            strategy=chunking_strategy
        )

    async def process_pdf(
        self,
        pdf_path: Path,
        extract_entities: bool = True,
        override_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a PDF file end-to-end.

        Args:
            pdf_path: Path to PDF file
            extract_entities: Whether to extract entities and build graph
            override_metadata: Optional metadata to inject

        Returns:
            Dict with processing results
        """
        logger.info(
            "processing_pdf",
            file=str(pdf_path),
            extract_entities=extract_entities
        )

        results = {
            "file": str(pdf_path),
            "pages_extracted": 0,
            "chunks_created": 0,
            "entities_created": 0,
            "relationships_created": 0,
            "errors": []
        }

        try:
            # Step 1: Extract text and metadata
            pdf_data = self.extract_pdf(pdf_path)
            results["pages_extracted"] = pdf_data["page_count"]

            # Step 2: Chunk text
            chunks = await self.chunk_pdf_text(
                text=pdf_data["text"],
                pdf_metadata=pdf_data["metadata"]
            )
            results["chunks_created"] = len(chunks)

            # Step 3: Store chunks in database
            await self.store_chunks(
                chunks=chunks,
                pdf_path=pdf_path,
                pdf_metadata=pdf_data["metadata"],
                override_metadata=override_metadata
            )

            # Step 4: Extract entities and build graph (optional)
            if extract_entities and pdf_data["text"].strip():
                graph_results = await self.extract_and_build_graph(
                    text=pdf_data["text"],
                    chunks=chunks,
                    pdf_metadata=pdf_data["metadata"]
                )
                results["entities_created"] = graph_results["entities_created"]
                results["relationships_created"] = graph_results["relationships_created"]

            logger.info(
                "pdf_processing_complete",
                file=str(pdf_path),
                chunks=results["chunks_created"],
                entities=results["entities_created"]
            )

        except Exception as e:
            logger.error(
                "pdf_processing_failed",
                file=str(pdf_path),
                error=str(e)
            )
            results["errors"].append(str(e))

        return results

    def extract_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Extract text and metadata from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with 'text', 'metadata', 'page_count'
        """
        logger.info("extracting_pdf", file=str(pdf_path))

        text_pages = []
        metadata = {}

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # Extract metadata
                if pdf_reader.metadata:
                    metadata = {
                        "title": pdf_reader.metadata.get('/Title', pdf_path.stem),
                        "author": pdf_reader.metadata.get('/Author', 'Unknown'),
                        "subject": pdf_reader.metadata.get('/Subject'),
                        "creator": pdf_reader.metadata.get('/Creator'),
                        "producer": pdf_reader.metadata.get('/Producer'),
                    }
                else:
                    metadata = {"title": pdf_path.stem}

                # Extract text from all pages
                page_count = len(pdf_reader.pages)
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_pages.append({
                                "page_num": page_num + 1,
                                "text": page_text
                            })
                    except Exception as e:
                        logger.warning(
                            "page_extraction_failed",
                            page=page_num + 1,
                            error=str(e)
                        )

                # Combine all pages
                full_text = "\n\n".join([p["text"] for p in text_pages])

                logger.info(
                    "pdf_extracted",
                    file=str(pdf_path),
                    pages=page_count,
                    text_length=len(full_text)
                )

                return {
                    "text": full_text,
                    "metadata": metadata,
                    "page_count": page_count,
                    "pages": text_pages
                }

        except Exception as e:
            logger.error(
                "pdf_extraction_failed",
                file=str(pdf_path),
                error=str(e)
            )
            raise

    async def chunk_pdf_text(
        self,
        text: str,
        pdf_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk PDF text using ClusterSemanticChunker.

        Args:
            text: Full PDF text
            pdf_metadata: PDF metadata

        Returns:
            List of chunk dicts with content and embeddings
        """
        logger.info(
            "chunking_pdf_text",
            text_length=len(text),
            title=pdf_metadata.get("title")
        )

        if not text.strip():
            return []

        # Use UnifiedChunker (which uses ClusterSemanticChunker under the hood)
        result = self.chunker.chunk(
            text=text,
            embedding_function=self.embedder.embed_query
        )

        # Convert to format expected by database
        chunks = []
        for i, chunk_text in enumerate(result.chunks):
            # Get or compute embedding for chunk
            if result.embeddings and i < len(result.embeddings):
                embedding = result.embeddings[i]
            else:
                embedding = self.embedder.embed_query(chunk_text)

            chunks.append({
                "content": chunk_text,
                "embedding": embedding,
                "chunk_index": i,
                "coherence_score": 1.0  # Placeholder
            })

        logger.info(
            "pdf_text_chunked",
            chunks=len(chunks),
            strategy=result.metadata.get("strategy"),
            duration=result.metadata.get("duration")
        )

        return chunks

    async def store_chunks(
        self,
        chunks: List[Dict[str, Any]],
        pdf_path: Path,
        pdf_metadata: Dict[str, Any],
        override_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store chunks in database as Document entries.

        Args:
            chunks: List of chunk dicts
            pdf_path: Path to PDF file
            pdf_metadata: PDF metadata
            override_metadata: Optional metadata to inject
        """
        logger.info(
            "storing_pdf_chunks",
            file=str(pdf_path),
            chunks=len(chunks)
        )

        with Session(engine) as session:
            # Delete existing chunks for this PDF (re-index)
            statement = delete(Document).where(
                Document.vault_id == self.vault_id,
                Document.metadata_['source_file'].astext == str(pdf_path.name)
            )
            session.exec(statement)

            # Insert new chunks
            for chunk in chunks:
                # Build metadata
                chunk_metadata = {
                    "source_file": pdf_path.name,
                    "source_type": "pdf",
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": len(chunks),
                    "coherence_score": chunk.get("coherence_score", 1.0),
                    "pdf_title": pdf_metadata.get("title"),
                    "pdf_author": pdf_metadata.get("author"),
                }

                # Merge override metadata
                if override_metadata:
                    chunk_metadata.update(override_metadata)

                doc = Document(
                    vault_id=self.vault_id,
                    title=f"{pdf_metadata.get('title', pdf_path.stem)} (chunk {chunk['chunk_index'] + 1})",
                    content=chunk["content"],
                    doc_type="pdf",
                    embedding=chunk["embedding"],
                    metadata_=chunk_metadata
                )
                session.add(doc)

            session.commit()

        logger.info(
            "pdf_chunks_stored",
            file=str(pdf_path),
            chunks=len(chunks)
        )

    async def extract_and_build_graph(
        self,
        text: str,
        chunks: List[Dict[str, Any]],
        pdf_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract entities from PDF text and build knowledge graph.

        Args:
            text: Full PDF text
            chunks: List of chunks
            pdf_metadata: PDF metadata

        Returns:
            Dict with entities_created, relationships_created
        """
        logger.info(
            "extracting_entities_from_pdf",
            title=pdf_metadata.get("title")
        )

        # Use ProfilerAgent to extract entities
        extraction_result = await self.profiler.run(
            full_text=text,
            existing_notes="",  # No existing context
            title=pdf_metadata.get("title", "PDF Document")
        )

        entities_created = 0
        relationships_created = 0

        with Session(engine) as session:
            # Store characters
            for char_profile in extraction_result.characters:
                # Check if entity already exists
                existing = await self.profiler.resolve_entity_by_era(
                    name=char_profile.name,
                    vault_id=self.vault_id
                )

                if not existing:
                    # Create new entity
                    entity = await self.profiler.find_or_create_entity(
                        name=char_profile.name,
                        entity_type=EntityType.CHARACTER,
                        vault_id=self.vault_id,
                        description=f"Role: {char_profile.role}",
                        override_metadata={
                            "source_pdf": pdf_metadata.get("title"),
                            "role": char_profile.role,
                            "visual_traits": [
                                {"feature": vt.feature, "description": vt.description}
                                for vt in char_profile.visual_traits
                            ]
                        }
                    )
                    entities_created += 1
                    logger.info("entity_created_from_pdf", name=char_profile.name)

                    # Create relationships
                    for rel in char_profile.relationships:
                        # Find or create target entity
                        target_entity = await self.profiler.find_or_create_entity(
                            name=rel.target,
                            entity_type=EntityType.CHARACTER,
                            vault_id=self.vault_id
                        )

                        # Map relationship type
                        rel_type_map = {
                            "sibling": RelationType.SIBLING,
                            "parent": RelationType.PARENT,
                            "child": RelationType.CHILD,
                            "spouse": RelationType.SPOUSE,
                            "enemy": RelationType.ENEMY,
                            "rival": RelationType.RIVAL,
                            "ally": RelationType.ALLY,
                            "mentor": RelationType.MENTOR,
                        }
                        rel_type = rel_type_map.get(rel.rel_type.lower(), RelationType.ALLY)

                        # Create relationship
                        rel_obj = Relationship(
                            vault_id=self.vault_id,
                            source_entity_id=entity.id,
                            target_entity_id=target_entity.id,
                            relationship_type=rel_type,
                            description=rel.details or f"{rel.rel_type} relationship",
                            relationship_metadata={"confidence": 0.8, "source": "pdf_extraction"}
                        )
                        session.add(rel_obj)
                        relationships_created += 1

            # Store organizations
            for org_profile in extraction_result.organizations:
                entity = await self.profiler.find_or_create_entity(
                    name=org_profile.name,
                    entity_type=EntityType.ORGANIZATION,
                    vault_id=self.vault_id,
                    description=f"Type: {org_profile.org_type}. Ideology: {org_profile.ideology}",
                    override_metadata={
                        "source_pdf": pdf_metadata.get("title"),
                        "org_type": org_profile.org_type,
                        "leader": org_profile.leader,
                        "key_assets": org_profile.key_assets,
                        "rivals": org_profile.rivals
                    }
                )
                entities_created += 1

            # Store locations
            for loc_profile in extraction_result.locations:
                entity = await self.profiler.find_or_create_entity(
                    name=loc_profile.name,
                    entity_type=EntityType.LOCATION,
                    vault_id=self.vault_id,
                    description=f"Geography: {loc_profile.geography}. Visual: {loc_profile.visual_signature}",
                    override_metadata={
                        "source_pdf": pdf_metadata.get("title"),
                        "geography": loc_profile.geography,
                        "visual_signature": loc_profile.visual_signature
                    }
                )
                entities_created += 1

            session.commit()

        logger.info(
            "graph_populated_from_pdf",
            entities=entities_created,
            relationships=relationships_created
        )

        return {
            "entities_created": entities_created,
            "relationships_created": relationships_created
        }

    async def process_pdf_directory(
        self,
        directory: Path,
        extract_entities: bool = True,
        override_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process all PDFs in a directory.

        Args:
            directory: Directory containing PDFs
            extract_entities: Whether to extract entities
            override_metadata: Optional metadata to inject

        Returns:
            Dict with aggregated results
        """
        logger.info(
            "processing_pdf_directory",
            directory=str(directory)
        )

        results = {
            "directory": str(directory),
            "files_processed": 0,
            "total_chunks": 0,
            "total_entities": 0,
            "total_relationships": 0,
            "errors": []
        }

        # Find all PDFs
        pdf_files = list(directory.rglob("*.pdf"))

        if not pdf_files:
            logger.warning("no_pdfs_found", directory=str(directory))
            return results

        logger.info("found_pdfs", count=len(pdf_files))

        # Process each PDF
        for pdf_path in pdf_files:
            try:
                pdf_results = await self.process_pdf(
                    pdf_path=pdf_path,
                    extract_entities=extract_entities,
                    override_metadata=override_metadata
                )

                results["files_processed"] += 1
                results["total_chunks"] += pdf_results["chunks_created"]
                results["total_entities"] += pdf_results["entities_created"]
                results["total_relationships"] += pdf_results["relationships_created"]

                if pdf_results["errors"]:
                    results["errors"].extend([
                        {"file": str(pdf_path), "error": err}
                        for err in pdf_results["errors"]
                    ])

            except Exception as e:
                logger.error(
                    "pdf_processing_failed",
                    file=str(pdf_path),
                    error=str(e)
                )
                results["errors"].append({
                    "file": str(pdf_path),
                    "error": str(e)
                })

        logger.info(
            "pdf_directory_processing_complete",
            directory=str(directory),
            files=results["files_processed"],
            chunks=results["total_chunks"],
            entities=results["total_entities"]
        )

        return results
