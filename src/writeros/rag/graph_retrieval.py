"""
Graph-Enhanced Retrieval Extension for RAG Retriever.

This module provides chunk-level retrieval with graph-based re-ranking.
Add these methods to RAGRetriever class in retriever.py or use as standalone functions.
"""
from typing import List, Set, Optional
from uuid import UUID
from sqlmodel import Session, select
from dataclasses import dataclass, field
from sqlalchemy import or_, func

from writeros.schema import Entity
from writeros.schema.chunks import Chunk
from writeros.schema.relationships import Relationship
from writeros.utils.db import engine
from writeros.utils.embeddings import get_embedding_service
from writeros.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """Container for chunk retrieval results with graph-based scoring."""
    chunk: Chunk
    similarity: float
    relevance_boost: float = 0.0
    adjusted_score: float = 0.0
    mentioned_entity_ids: List[str] = field(default_factory=list)


async def extract_entities_from_query(query: str, vault_id: Optional[UUID] = None) -> List[Entity]:
    """
    Extract entities mentioned in the query using vector search.

    Args:
        query: The query string
        vault_id: Optional vault filter

    Returns:
        List of top 3 most relevant entities
    """
    embedder = get_embedding_service()
    query_embedding = embedder.embed_query(query)

    with Session(engine) as session:
        stmt = select(Entity)
        if vault_id:
            stmt = stmt.where(Entity.vault_id == vault_id)

        stmt = stmt.order_by(
            Entity.embedding.cosine_distance(query_embedding)
        ).limit(3)

        return list(session.exec(stmt).all())


async def get_entity_neighbors(
    entity_id: UUID,
    vault_id: Optional[UUID] = None
) -> Set[UUID]:
    """
    Get 1-hop neighbors of an entity via the relationships table.

    Args:
        entity_id: The entity whose neighbors to find
        vault_id: Optional vault filter

    Returns:
        Set of neighbor entity IDs
    """
    with Session(engine) as session:
        stmt = select(Relationship).where(
            or_(
                Relationship.source_entity_id == entity_id,
                Relationship.target_entity_id == entity_id
            )
        )

        if vault_id:
            stmt = stmt.where(Relationship.vault_id == vault_id)

        relationships = session.exec(stmt).all()

        neighbors = set()
        for rel in relationships:
            if rel.source_entity_id == entity_id:
                neighbors.add(rel.target_entity_id)
            else:
                neighbors.add(rel.source_entity_id)

        return neighbors


async def vector_search_chunks(
    query: str,
    vault_id: UUID,
    k: int
) -> List[RetrievedChunk]:
    """
    Vector search on chunks table with similarity scores.

    Args:
        query: The search query
        vault_id: Vault to search within
        k: Number of results to return

    Returns:
        List of RetrievedChunk objects with similarity scores
    """
    embedder = get_embedding_service()
    query_embedding = embedder.embed_query(query)

    with Session(engine) as session:
        # Select chunks with their cosine distance
        stmt = select(
            Chunk,
            Chunk.embedding.cosine_distance(query_embedding).label('distance')
        ).where(
            Chunk.vault_id == vault_id
        ).order_by(
            Chunk.embedding.cosine_distance(query_embedding)
        ).limit(k)

        results = session.exec(stmt).all()

        # Convert to RetrievedChunk with similarity scores
        retrieved_chunks = []
        for chunk, distance in results:
            # Convert distance to similarity (1 - distance for cosine)
            similarity = 1.0 - float(distance) if distance is not None else 0.0

            retrieved_chunks.append(RetrievedChunk(
                chunk=chunk,
                similarity=similarity,
                mentioned_entity_ids=chunk.mentioned_entity_ids or []
            ))

        return retrieved_chunks


async def retrieve_chunks_with_graph(
    query: str,
    vault_id: UUID,
    k: int = 5,
    expand_graph: bool = True,
    entity_boost_direct: float = 0.3,
    entity_boost_indirect: float = 0.1
) -> List[RetrievedChunk]:
    """
    Use graph structure to enhance chunk retrieval.

    Process:
    1. Standard vector retrieval on chunks (retrieve k*2 candidates)
    2. Extract entities from query
    3. Find 1-hop neighbors of query entities
    4. Re-rank chunks based on entity mentions:
       - Direct mentions of query entities get higher boost
       - Mentions of related entities get smaller boost
    5. Return top k chunks sorted by adjusted score

    Args:
        query: The search query
        vault_id: Vault to search within
        k: Number of final results to return
        expand_graph: Whether to use graph expansion (default: True)
        entity_boost_direct: Boost for direct entity mentions (default: 0.3)
        entity_boost_indirect: Boost for indirect entity mentions (default: 0.1)

    Returns:
        List of top k chunks sorted by adjusted_score (similarity + relevance_boost)
    """
    logger.info("graph_enhanced_retrieval_started", query=query[:100], k=k, expand_graph=expand_graph)

    # 1. Standard vector retrieval
    initial_chunks = await vector_search_chunks(query, vault_id, k=k * 2)

    if not expand_graph:
        return initial_chunks[:k]

    # 2. Identify entities in query
    query_entities = await extract_entities_from_query(query, vault_id)
    query_entity_ids = {str(e.id) for e in query_entities}

    logger.info("query_entities_extracted", count=len(query_entities), entities=[e.name for e in query_entities])

    # 3. Get related entities from graph (1-hop neighbors)
    related_entity_ids = set()
    for entity in query_entities:
        neighbors = await get_entity_neighbors(entity.id, vault_id)
        related_entity_ids.update(str(n) for n in neighbors)

    logger.info("related_entities_found", count=len(related_entity_ids))

    # 4. Boost chunks that mention related entities
    for chunk in initial_chunks:
        mentioned = set(chunk.mentioned_entity_ids)

        # Direct mention of query entities = high boost
        direct_overlap = mentioned & query_entity_ids

        # Mention of related entities = smaller boost
        indirect_overlap = mentioned & related_entity_ids

        chunk.relevance_boost = (
            len(direct_overlap) * entity_boost_direct +
            len(indirect_overlap) * entity_boost_indirect
        )
        chunk.adjusted_score = chunk.similarity + chunk.relevance_boost

    # 5. Re-rank by adjusted score
    initial_chunks.sort(key=lambda c: c.adjusted_score, reverse=True)

    # 6. Optionally add high-value chunks for related entities not in initial results
    if len(initial_chunks) < k:
        logger.info("expanding_results", current_count=len(initial_chunks), target=k)

        with Session(engine) as session:
            for entity_id_str in related_entity_ids:
                if len(initial_chunks) >= k:
                    break

                try:
                    entity_id = UUID(entity_id_str)
                    entity = session.get(Entity, entity_id)

                    if entity and entity.primary_source_chunk_id:
                        # Check if this chunk is already in results
                        chunk_ids = {str(rc.chunk.id) for rc in initial_chunks}
                        if str(entity.primary_source_chunk_id) not in chunk_ids:
                            source_chunk = session.get(Chunk, entity.primary_source_chunk_id)
                            if source_chunk:
                                initial_chunks.append(RetrievedChunk(
                                    chunk=source_chunk,
                                    similarity=0.5,  # Default similarity
                                    relevance_boost=entity_boost_indirect,
                                    adjusted_score=0.5 + entity_boost_indirect,
                                    mentioned_entity_ids=source_chunk.mentioned_entity_ids or []
                                ))
                except (ValueError, AttributeError):
                    continue

    logger.info(
        "graph_enhanced_retrieval_complete",
        returned_count=len(initial_chunks[:k]),
        avg_boost=sum(c.relevance_boost for c in initial_chunks[:k]) / min(k, len(initial_chunks)) if initial_chunks else 0
    )

    return initial_chunks[:k]
