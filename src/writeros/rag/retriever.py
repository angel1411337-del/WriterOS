"""
RAG Retriever Service
Provides unified vector search across Documents, Entities, and Facts.
Supports temporal filtering to prevent spoilers and maintain narrative continuity.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select
from dataclasses import dataclass

from writeros.schema import Document, Entity, Fact, Event
from writeros.utils.db import engine
from writeros.utils.embeddings import EmbeddingService, get_embedding_service
from writeros.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    """Container for retrieval results with scores."""
    documents: List[Document]
    entities: List[Entity]
    facts: List[Fact]
    events: List[Event]
    scores: Dict[str, List[float]]
    temporal_context: Optional[Dict[str, Any]] = None


class RAGRetriever:
    """
    Unified RAG retrieval service for semantic search.
    Supports filtering by vault_id and customizable result limits.
    """

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedder = embedding_service or get_embedding_service()

    async def retrieve(
        self,
        query: str,
        vault_id: Optional[UUID] = None,
        limit: int = 5,
        include_documents: bool = True,
        include_entities: bool = True,
        include_facts: bool = True,
        include_events: bool = True,
        distance_metric: str = "cosine",  # "cosine" or "l2"
        max_sequence_order: Optional[int] = None,  # Temporal filter
        max_story_time: Optional[Dict[str, int]] = None,  # e.g., {"year": 300}
        temporal_mode: str = "god"  # "god" (no filter), "sequence", "story_time"
    ) -> RetrievalResult:
        """
        Perform semantic search across multiple data types with optional temporal filtering.

        Args:
            query: The search query string
            vault_id: Optional vault filter
            limit: Maximum results per type
            include_documents: Whether to search documents
            include_entities: Whether to search entities
            include_facts: Whether to search facts
            include_events: Whether to search events
            distance_metric: "cosine" (default) or "l2" distance
            max_sequence_order: Maximum sequence order (chapter/scene number) for temporal filtering
            max_story_time: Maximum story time (e.g., {"year": 300}) for temporal filtering
            temporal_mode: "god" (no filtering), "sequence" (use max_sequence_order), "story_time" (use max_story_time)

        Returns:
            RetrievalResult containing all matching items (filtered by temporal context if provided)
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)

        documents = []
        entities = []
        facts = []
        events = []
        scores = {"documents": [], "entities": [], "facts": [], "events": []}

        # Log temporal filtering
        if temporal_mode != "god":
            logger.info(
                "temporal_retrieval",
                mode=temporal_mode,
                max_sequence=max_sequence_order,
                max_story_time=max_story_time
            )

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

            # Search Events (with temporal filtering)
            if include_events:
                event_stmt = select(Event)

                if vault_id:
                    event_stmt = event_stmt.where(Event.vault_id == vault_id)

                # Apply temporal filtering
                if temporal_mode == "sequence" and max_sequence_order is not None:
                    event_stmt = event_stmt.where(
                        Event.sequence_order <= max_sequence_order
                    )
                    logger.info(
                        "temporal_filter_applied",
                        filter_type="sequence",
                        max_sequence=max_sequence_order
                    )

                elif temporal_mode == "story_time" and max_story_time is not None:
                    # Filter by story_time (JSONB comparison)
                    # For now, simple year comparison if available
                    if "year" in max_story_time:
                        # This requires custom SQL for JSONB comparison
                        # Simplified: We'll filter in Python for now
                        pass  # Will be applied post-query

                if distance_metric == "cosine":
                    event_stmt = event_stmt.order_by(
                        Event.embedding.cosine_distance(query_embedding)
                    ).limit(limit)
                else:
                    event_stmt = event_stmt.order_by(
                        Event.embedding.l2_distance(query_embedding)
                    ).limit(limit)

                events = list(session.exec(event_stmt).all())

                # Post-filter for story_time if needed
                if temporal_mode == "story_time" and max_story_time is not None:
                    events = self._filter_events_by_story_time(events, max_story_time)

        return RetrievalResult(
            documents=documents,
            entities=entities,
            facts=facts,
            events=events,
            scores=scores,
            temporal_context={
                "mode": temporal_mode,
                "max_sequence_order": max_sequence_order,
                "max_story_time": max_story_time
            }
        )

    def _filter_events_by_story_time(
        self,
        events: List[Event],
        max_story_time: Dict[str, int]
    ) -> List[Event]:
        """
        Filter events by story_time in Python (post-query).

        Args:
            events: List of events to filter
            max_story_time: Maximum story time dict (e.g., {"year": 300})

        Returns:
            Filtered list of events
        """
        filtered = []
        for event in events:
            if not event.story_time:
                # If no story_time, assume it's before everything (include it)
                filtered.append(event)
                continue

            # Simple year comparison for now
            if "year" in max_story_time and "year" in event.story_time:
                if event.story_time["year"] <= max_story_time["year"]:
                    filtered.append(event)
            else:
                # If we can't compare, include it (fallback to permissive)
                filtered.append(event)

        return filtered

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

        # Add temporal context if available
        if results.temporal_context and results.temporal_context.get("mode") != "god":
            tc = results.temporal_context
            if tc["mode"] == "sequence":
                sections.append(
                    f"⏱️ TEMPORAL CONTEXT: Showing events up to sequence order {tc['max_sequence_order']}"
                )
            elif tc["mode"] == "story_time":
                sections.append(
                    f"⏱️ TEMPORAL CONTEXT: Showing events up to story time {tc['max_story_time']}"
                )

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

        # Format Events (NEW)
        if results.events:
            event_lines = []
            for event in results.events:
                seq = f"[Seq: {event.sequence_order}]" if event.sequence_order else ""
                time_str = ""
                if event.story_time:
                    time_str = f" (Story Time: {event.story_time})"
                desc = event.description or event.name
                event_lines.append(f"- {seq} {desc}{time_str}")
            sections.append("📅 EVENTS:\n" + "\n".join(event_lines))

        if not sections:
            return "No relevant information found."

        return "\n\n".join(sections)


# Global instance for convenience
retriever = RAGRetriever()
