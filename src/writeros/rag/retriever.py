"""
RAG Retriever Service
Provides unified vector search across Documents, Entities, and Facts.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select
from dataclasses import dataclass

from writeros.schema import Document, Entity, Fact
from writeros.utils.db import engine
from writeros.utils.embeddings import EmbeddingService


@dataclass
class RetrievalResult:
    """Container for retrieval results with scores."""
    documents: List[Document]
    entities: List[Entity]
    facts: List[Fact]
    scores: Dict[str, List[float]]


class RAGRetriever:
    """
    Unified RAG retrieval service for semantic search.
    Supports filtering by vault_id and customizable result limits.
    """

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedder = embedding_service or EmbeddingService()

    async def retrieve(
        self,
        query: str,
        vault_id: Optional[UUID] = None,
        limit: int = 5,
        include_documents: bool = True,
        include_entities: bool = True,
        include_facts: bool = True,
        distance_metric: str = "cosine"  # "cosine" or "l2"
    ) -> RetrievalResult:
        """
        Perform semantic search across multiple data types.

        Args:
            query: The search query string
            vault_id: Optional vault filter
            limit: Maximum results per type
            include_documents: Whether to search documents
            include_entities: Whether to search entities
            include_facts: Whether to search facts
            distance_metric: "cosine" (default) or "l2" distance

        Returns:
            RetrievalResult containing all matching items
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        documents = []
        entities = []
        facts = []
        scores = {"documents": [], "entities": [], "facts": []}

        with Session(engine) as session:
            # Search Documents
            if include_documents:
                doc_stmt = select(Document)
                if vault_id:
                    doc_stmt = doc_stmt.where(Document.vault_id == vault_id)

                if distance_metric == "cosine":
                    doc_stmt = doc_stmt.order_by(
                        Document.embedding.cosine_distance(query_embedding)
                    ).limit(limit)
                else:
                    doc_stmt = doc_stmt.order_by(
                        Document.embedding.l2_distance(query_embedding)
                    ).limit(limit)

                documents = list(session.exec(doc_stmt).all())

            # Search Entities
            if include_entities:
                ent_stmt = select(Entity)
                if vault_id:
                    ent_stmt = ent_stmt.where(Entity.vault_id == vault_id)

                if distance_metric == "cosine":
                    ent_stmt = ent_stmt.order_by(
                        Entity.embedding.cosine_distance(query_embedding)
                    ).limit(limit)
                else:
                    ent_stmt = ent_stmt.order_by(
                        Entity.embedding.l2_distance(query_embedding)
                    ).limit(limit)

                entities = list(session.exec(ent_stmt).all())

            # Search Facts
            if include_facts:
                fact_stmt = select(Fact)

                if distance_metric == "cosine":
                    fact_stmt = fact_stmt.order_by(
                        Fact.embedding.cosine_distance(query_embedding)
                    ).limit(limit)
                else:
                    fact_stmt = fact_stmt.order_by(
                        Fact.embedding.l2_distance(query_embedding)
                    ).limit(limit)

                facts = list(session.exec(fact_stmt).all())

        return RetrievalResult(
            documents=documents,
            entities=entities,
            facts=facts,
            scores=scores
        )

    def format_results(self, results: RetrievalResult, max_content_length: int = 200) -> str:
        """
        Format retrieval results as a readable string for LLM context.

        Args:
            results: The retrieval results
            max_content_length: Maximum characters to include from content fields

        Returns:
            Formatted string with all results
        """
        sections = []

        # Format Documents
        if results.documents:
            doc_lines = []
            for doc in results.documents:
                content = doc.content[:max_content_length]
                if len(doc.content) > max_content_length:
                    content += "..."
                doc_lines.append(f"- [{doc.doc_type}] {doc.title}: {content}")
            sections.append("📄 DOCUMENTS:\n" + "\n".join(doc_lines))

        # Format Entities
        if results.entities:
            ent_lines = []
            for ent in results.entities:
                desc = ent.description or "No description"
                if len(desc) > max_content_length:
                    desc = desc[:max_content_length] + "..."
                ent_lines.append(f"- [{ent.type}] {ent.name}: {desc}")
            sections.append("👤 ENTITIES:\n" + "\n".join(ent_lines))

        # Format Facts
        if results.facts:
            fact_lines = []
            for fact in results.facts:
                source = f" (source: {fact.source})" if fact.source else ""
                fact_lines.append(f"- [{fact.fact_type}] {fact.content}{source}")
            sections.append("📌 FACTS:\n" + "\n".join(fact_lines))

        if not sections:
            return "No relevant information found."

        return "\n\n".join(sections)


# Global instance for convenience
retriever = RAGRetriever()
