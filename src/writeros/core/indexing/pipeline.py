"""
Main indexing orchestrator.

Coordinates: chunking → embedding → extraction → linking

This is a modular, production-grade indexing pipeline that separates concerns
and allows for easy testing, extension, and maintenance.
"""

from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel
from sqlmodel import Session

from writeros.preprocessing import UnifiedChunker
from writeros.utils.embeddings import get_embedding_service
from writeros.schema import Document, Entity, Relationship
from writeros.utils.db import engine
from writeros.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# RESULT MODELS
# ============================================================================

class ChunkExtractionResult(BaseModel):
    """Result from processing a single chunk."""
    chunk_id: UUID
    entity_count: int
    relationship_count: int


class IndexingResult(BaseModel):
    """Result from processing an entire file."""
    chunks_created: int
    entities_extracted: int
    relationships_extracted: int
    file_path: str


# ============================================================================
# COMPONENT PROTOCOLS (Abstract Interfaces)
# ============================================================================

class Chunker:
    """Protocol for chunking strategies."""
    async def chunk_file(
        self,
        vault_id: UUID,
        file_path: str,
        content: str,
        narrative_sequence: Optional[int] = None,
    ) -> List[Document]:
        """Chunk a file into Document objects."""
        raise NotImplementedError


class Embedder:
    """Protocol for embedding generation."""
    async def embed_chunks(self, chunks: List[Document]) -> List[Document]:
        """Generate embeddings for chunks (modifies in place)."""
        raise NotImplementedError


class EntityExtractor:
    """Protocol for entity extraction."""
    async def extract(self, chunk: Document) -> List[Entity]:
        """Extract entities from a chunk."""
        raise NotImplementedError


class RelationshipExtractor:
    """Protocol for relationship extraction."""
    async def extract(
        self,
        chunk: Document,
        entities: List[Entity]
    ) -> List[Relationship]:
        """Extract relationships from a chunk."""
        raise NotImplementedError


class BidirectionalLinker:
    """Protocol for bidirectional linking."""
    async def link_chunk_to_graph(
        self,
        chunk: Document,
        entities: List[Entity],
        relationships: List[Relationship],
    ):
        """Update all bidirectional links between chunk and graph."""
        raise NotImplementedError


# ============================================================================
# CONCRETE IMPLEMENTATIONS (Adapters to existing WriterOS components)
# ============================================================================

class WriterOSChunker(Chunker):
    """Adapter for WriterOS UnifiedChunker."""

    def __init__(self, chunker: UnifiedChunker):
        self.chunker = chunker

    async def chunk_file(
        self,
        vault_id: UUID,
        file_path: str,
        content: str,
        narrative_sequence: Optional[int] = None,
    ) -> List[Document]:
        """Chunk file using UnifiedChunker."""
        chunks = await self.chunker.chunk_text_async(
            text=content,
            metadata={
                "vault_id": str(vault_id),
                "file_path": file_path,
                "narrative_sequence": narrative_sequence,
            }
        )

        # Convert to Document objects
        documents = []
        for i, chunk in enumerate(chunks):
            # Extract narrative metadata from chunk
            chunk_metadata = chunk.get("metadata", {})
            scene_index = chunk_metadata.get("scene_index")
            section_type = chunk_metadata.get("section_type")

            # Build scene_id for POV Boundary system
            scene_id = None
            if scene_index is not None:
                scene_id = f"{file_path}:scene_{scene_index}"

            # Store narrative metadata in Document.metadata_
            narrative_metadata = {
                "scene_index": scene_index,
                "scene_id": scene_id,
                "section_type": section_type,
                "has_overlap": chunk_metadata.get("has_overlap", False),
                "line_start": chunk_metadata.get("line_start"),
                "line_end": chunk_metadata.get("line_end"),
                "char_start": chunk_metadata.get("char_start"),
                "char_end": chunk_metadata.get("char_end"),
            }

            doc = Document(
                vault_id=vault_id,
                file_path=file_path,
                title=f"{file_path} - Chunk {i+1}",
                content=chunk["text"],
                chunk_index=i,
                doc_type="markdown",
                narrative_sequence=narrative_sequence,
                metadata_=narrative_metadata,
            )
            documents.append(doc)

        return documents


class WriterOSEmbedder(Embedder):
    """Adapter for WriterOS embedding service."""

    def __init__(self):
        self.embedding_service = get_embedding_service()

    async def embed_chunks(self, chunks: List[Document]) -> List[Document]:
        """Generate embeddings for chunks."""
        # Batch embed all chunks
        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_service.embed_documents_async(texts)

        # Assign embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        return chunks


class LLMEntityExtractor(EntityExtractor):
    """LLM-based entity extractor (placeholder for future implementation)."""

    async def extract(self, chunk: Document) -> List[Entity]:
        """Extract entities from chunk using LLM."""
        # TODO: Implement LLM-based entity extraction
        # For now, return empty list
        logger.debug("entity_extraction_placeholder", chunk_id=str(chunk.id))
        return []


class LLMRelationshipExtractor(RelationshipExtractor):
    """LLM-based relationship extractor (placeholder for future implementation)."""

    async def extract(
        self,
        chunk: Document,
        entities: List[Entity]
    ) -> List[Relationship]:
        """Extract relationships from chunk using LLM."""
        # TODO: Implement LLM-based relationship extraction
        # For now, return empty list
        logger.debug("relationship_extraction_placeholder", chunk_id=str(chunk.id))
        return []


class DatabaseLinker(BidirectionalLinker):
    """Database-backed bidirectional linker."""

    async def link_chunk_to_graph(
        self,
        chunk: Document,
        entities: List[Entity],
        relationships: List[Relationship],
    ):
        """Update all bidirectional links between chunk and graph."""
        with Session(engine) as session:
            # Save entities
            for entity in entities:
                session.add(entity)

            # Save relationships
            for relationship in relationships:
                session.add(relationship)

            # Commit all changes
            session.commit()

            logger.debug(
                "bidirectional_links_updated",
                chunk_id=str(chunk.id),
                entities=len(entities),
                relationships=len(relationships)
            )


# ============================================================================
# MAIN INDEXING PIPELINE
# ============================================================================

class IndexingPipeline:
    """
    Processes files through the full indexing pipeline.

    Flow:
    1. Chunk the file
    2. Generate embeddings
    3. Extract entities (Chunk → Graph)
    4. Extract relationships (Chunk → Graph)
    5. Update bidirectional links
    6. Trigger co-occurrence analysis (async)
    """

    def __init__(
        self,
        chunker: Chunker,
        embedder: Embedder,
        entity_extractor: EntityExtractor,
        relationship_extractor: RelationshipExtractor,
        linker: BidirectionalLinker,
    ):
        self.chunker = chunker
        self.embedder = embedder
        self.entity_extractor = entity_extractor
        self.relationship_extractor = relationship_extractor
        self.linker = linker

        logger.info("indexing_pipeline_initialized")

    async def process_file(
        self,
        vault_id: UUID,
        file_path: str,
        content: str,
        narrative_sequence: Optional[int] = None,
    ) -> IndexingResult:
        """Process a single file through the pipeline."""

        logger.info("processing_file", file_path=file_path, vault_id=str(vault_id))

        # 1. Chunk
        chunks = await self.chunker.chunk_file(
            vault_id=vault_id,
            file_path=file_path,
            content=content,
            narrative_sequence=narrative_sequence,
        )

        logger.debug("chunks_created", count=len(chunks))

        # 2. Embed
        chunks = await self.embedder.embed_chunks(chunks)

        logger.debug("embeddings_generated", count=len(chunks))

        # 3. Save chunks first (need IDs for linking)
        saved_chunks = await self._save_chunks(chunks)

        logger.debug("chunks_saved", count=len(saved_chunks))

        # 4. Extract & Link (this is the Chunk → Graph flow)
        extraction_results = []
        for chunk in saved_chunks:
            result = await self._process_chunk_to_graph(chunk)
            extraction_results.append(result)

        # 5. Queue co-occurrence analysis (async background job)
        # TODO: Implement co-occurrence analysis queue
        # await self.queue_co_occurrence_analysis(vault_id)

        total_entities = sum(r.entity_count for r in extraction_results)
        total_relationships = sum(r.relationship_count for r in extraction_results)

        logger.info(
            "file_processing_complete",
            file_path=file_path,
            chunks=len(saved_chunks),
            entities=total_entities,
            relationships=total_relationships
        )

        return IndexingResult(
            chunks_created=len(saved_chunks),
            entities_extracted=total_entities,
            relationships_extracted=total_relationships,
            file_path=file_path,
        )

    async def _save_chunks(self, chunks: List[Document]) -> List[Document]:
        """Save chunks to database and return with IDs."""
        with Session(engine) as session:
            for chunk in chunks:
                session.add(chunk)
            session.commit()

            # Refresh to get IDs
            for chunk in chunks:
                session.refresh(chunk)

        return chunks

    async def _process_chunk_to_graph(self, chunk: Document) -> ChunkExtractionResult:
        """
        CHUNK → GRAPH FLOW

        1. Extract entities from chunk
        2. Extract relationships from chunk
        3. Update bidirectional links
        """

        logger.debug("processing_chunk_to_graph", chunk_id=str(chunk.id))

        # Extract entities
        entities = await self.entity_extractor.extract(chunk)

        # Extract relationships (needs entities for context)
        relationships = await self.relationship_extractor.extract(chunk, entities)

        # Update all bidirectional links
        await self.linker.link_chunk_to_graph(
            chunk=chunk,
            entities=entities,
            relationships=relationships,
        )

        return ChunkExtractionResult(
            chunk_id=chunk.id,
            entity_count=len(entities),
            relationship_count=len(relationships),
        )


# ============================================================================
# FACTORY FUNCTION (Easy initialization with defaults)
# ============================================================================

def create_default_pipeline() -> IndexingPipeline:
    """
    Create an IndexingPipeline with default WriterOS implementations.

    This is the recommended way to initialize the pipeline for production use.
    """
    from writeros.preprocessing import UnifiedChunker, ChunkingStrategy

    # Create components
    unified_chunker = UnifiedChunker(
        strategy=ChunkingStrategy.NARRATIVE,  # Fiction-optimized chunking (preserves scenes, dialogue, chronology)
        min_chunk_size=50,
        max_chunk_size=400,
        enable_cache=True,
    )

    chunker = WriterOSChunker(unified_chunker)
    embedder = WriterOSEmbedder()
    entity_extractor = LLMEntityExtractor()
    relationship_extractor = LLMRelationshipExtractor()
    linker = DatabaseLinker()

    # Assemble pipeline
    pipeline = IndexingPipeline(
        chunker=chunker,
        embedder=embedder,
        entity_extractor=entity_extractor,
        relationship_extractor=relationship_extractor,
        linker=linker,
    )

    logger.info("default_pipeline_created")

    return pipeline
