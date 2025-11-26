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
                    # Filter by story_time (JSONB comparison in SQL)
                    if "year" in max_story_time:
                        from sqlalchemy import func, cast, Integer, or_

                        # Filter events where:
                        # 1. story_time is NULL (no time info, include by default), OR
                        # 2. story_time->>'year' is NULL (no year field), OR
                        # 3. story_time->>'year' <= max_year
                        max_year = max_story_time["year"]
                        event_stmt = event_stmt.where(
                            or_(
                                Event.story_time.is_(None),
                                Event.story_time['year'].as_string().is_(None),
                                cast(Event.story_time['year'].as_string(), Integer) <= max_year
                            )
                        )
                        logger.info(
                            "temporal_filter_applied",
                            filter_type="story_time",
                            max_year=max_year
                        )

                if distance_metric == "cosine":
                    event_stmt = event_stmt.order_by(
                        Event.embedding.cosine_distance(query_embedding)
                    ).limit(limit)
                else:
                    event_stmt = event_stmt.order_by(
                        Event.embedding.l2_distance(query_embedding)
                    ).limit(limit)

                events = list(session.exec(event_stmt).all())

                # Note: story_time filtering is now done in SQL (see lines 158-179)
                # No post-query filtering needed

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
        DEPRECATED: Filter events by story_time in Python (post-query).

        This method is kept for backwards compatibility but is no longer used.
        Filtering is now done in SQL for better performance (see lines 158-179).

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


    async def retrieve_iterative(
        self,
        initial_query: str,
        vault_id: Optional[UUID] = None,
        max_hops: int = 10,
        limit_per_hop: int = 3,
        **kwargs
    ) -> RetrievalResult:
        """
        Performs iterative multi-hop retrieval to gather deeper context.
        
        Process:
        1. Retrieve initial context based on query
        2. Analyze what was found and identify gaps
        3. Generate follow-up query to fill gaps
        4. Retrieve more context
        5. Repeat up to max_hops times
        
        Args:
            initial_query: The starting query
            vault_id: Optional vault filter
            max_hops: Maximum number of retrieval iterations (default: 10)
            limit_per_hop: Results to retrieve per hop (default: 3)
            **kwargs: Additional arguments passed to retrieve()
            
        Returns:
            Aggregated RetrievalResult from all hops
        """
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        from writeros.utils.llm_client import LLMClient
        import os
        
        logger.info("iterative_retrieval_started", query=initial_query, max_hops=max_hops)
        
        # Initialize LLM for query refinement
        llm = LLMClient(model_name="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
        
        # Aggregated results
        all_documents = []
        all_entities = []
        all_facts = []
        all_events = []
        all_scores = {"documents": [], "entities": [], "facts": [], "events": []}
        
        current_query = initial_query
        seen_ids = {"documents": set(), "entities": set(), "facts": set(), "events": set()}
        
        for hop in range(max_hops):
            logger.info("retrieval_hop", hop=hop+1, query=current_query[:100])
            
            # Retrieve for this hop
            hop_results = await self.retrieve(
                query=current_query,
                vault_id=vault_id,
                limit=limit_per_hop,
                **kwargs
            )
            
            # Deduplicate and aggregate results
            new_results_found = False
            
            for doc in hop_results.documents:
                if doc.id not in seen_ids["documents"]:
                    all_documents.append(doc)
                    seen_ids["documents"].add(doc.id)
                    new_results_found = True
            
            for entity in hop_results.entities:
                if entity.id not in seen_ids["entities"]:
                    all_entities.append(entity)
                    seen_ids["entities"].add(entity.id)
                    new_results_found = True
            
            for fact in hop_results.facts:
                if fact.id not in seen_ids["facts"]:
                    all_facts.append(fact)
                    seen_ids["facts"].add(fact.id)
                    new_results_found = True
            
            for event in hop_results.events:
                if event.id not in seen_ids["events"]:
                    all_events.append(event)
                    seen_ids["events"].add(event.id)
                    new_results_found = True
            
            # If no new results, stop early
            if not new_results_found:
                logger.info("iterative_retrieval_converged", hop=hop+1)
                break
            
            # If this is the last hop, don't generate a follow-up query
            if hop == max_hops - 1:
                break
            
            # Generate follow-up query based on current context
            context_summary = self.format_results(hop_results, max_content_length=100)
            
            refinement_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are refining a search query based on retrieved context.

Your goal: Generate a follow-up query that will retrieve COMPLEMENTARY information.

Rules:
1. Identify gaps in the current context
2. Ask about related entities, events, or facts NOT yet retrieved
3. Keep it concise (one sentence)
4. Don't repeat the original query verbatim

Example:
Original: "Who is Jon Snow?"
Context: "Jon Snow is Ned Stark's bastard son"
Follow-up: "What is Jon Snow's relationship with the Night's Watch?"
"""),
                ("user", """Original Query: {original_query}

Current Context Retrieved:
{context_summary}

Generate a follow-up query to gather complementary information:""")
            ])
            
            chain = refinement_prompt | llm | StrOutputParser()
            try:
                current_query = await chain.ainvoke({
                    "original_query": initial_query,
                    "context_summary": context_summary
                })
                logger.info("query_refined", new_query=current_query[:100])
            except Exception as e:
                logger.error("query_refinement_failed", error=str(e))
                break  # Stop if we can't refine
        
        logger.info(
            "iterative_retrieval_complete",
            hops=hop+1,
            total_docs=len(all_documents),
            total_entities=len(all_entities),
            total_facts=len(all_facts),
            total_events=len(all_events)
        )
        
        # Return aggregated results
        return RetrievalResult(
            documents=all_documents,
            entities=all_entities,
            facts=all_facts,
            events=all_events,
            scores=all_scores,
            temporal_context=hop_results.temporal_context if hop_results else None
        )


# Global instance for convenience
retriever = RAGRetriever()
