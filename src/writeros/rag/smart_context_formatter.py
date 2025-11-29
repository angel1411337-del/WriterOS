"""
Smart Context Formatter for Agent Prompts

Design Decision:
Replaces the "text blob" approach with intelligent, entity-focused context building.

Problem with Old Approach (format_results):
- Dumps all documents/entities/facts as one giant concatenated string
- No prioritization or relevance filtering
- Agents receive 100k+ chars of mostly irrelevant context
- "Text blob" is hard for LLMs to parse and reason about

Solution:
- Extract entities from the user query
- Use EntityContextBuilder to get prioritized, relevant chunks
- Format context hierarchically with clear sections
- Respect token budgets to prevent overload

Reasoning:
- Entity-focused retrieval provides better context quality
- Hierarchical formatting is easier for LLMs to parse
- Token budgets prevent context window overflow
- Clear separation of concepts (entities vs general documents)
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select

from writeros.schema import Entity, Chunk
from writeros.rag.context_builder import EntityContextBuilder, UsageBasedPriority
from writeros.utils.db import engine
from writeros.utils.embeddings import get_embedding_service
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class SmartContextFormatter:
    """
    Intelligent context formatter that builds structured, relevant context.

    Design Pattern:
    Uses EntityContextBuilder to create focused context for key entities
    instead of dumping everything as an unstructured text blob.

    Algorithm:
    1. Extract entities mentioned in the query (via embedding similarity)
    2. For each key entity, build structured context using EntityContextBuilder
    3. Add general document context (non-entity-specific information)
    4. Format everything hierarchically with clear sections
    """

    def __init__(self):
        self.embedder = get_embedding_service()

    async def format_context(
        self,
        query: str,
        vault_id: UUID,
        documents: List[Any] = None,
        entities: List[Entity] = None,
        max_total_tokens: int = 8000,
        max_entities: int = 5,
        session: Optional[Session] = None
    ) -> str:
        """
        Build intelligent, structured context for agent prompts.

        Design Decision:
        Prioritize entity-focused context over generic document dumps.

        Reasoning:
        Narrative fiction queries are almost always about entities (characters,
        locations, events). Entity-focused context provides better relevance
        than dumping all retrieved documents.

        Args:
            query: User's query/question
            vault_id: Vault to search in
            documents: Retrieved documents (optional, for backward compatibility)
            entities: Retrieved entities (optional)
            max_total_tokens: Total token budget across all context
            max_entities: Maximum number of entities to include detailed context for
            session: Optional database session for testing

        Returns:
            Formatted context string with hierarchical structure

        Example Output:
            ## Key Entities

            ### Ned Stark (CHARACTER)
            **Primary Source:**
            Ned Stark is Lord of Winterfell and Warden of the North...

            **Relationships:**
            - Married to Catelyn Tully
            - Father of Robb, Sansa, Arya, Bran, Rickon

            **Context:**
            [Prioritized mention chunks about Ned]

            ### Jon Snow (CHARACTER)
            [Similar structure]

            ## General Context
            [Non-entity-specific documents]
        """
        logger.info(
            "smart_context_formatting_started",
            query_length=len(query),
            max_total_tokens=max_total_tokens,
            max_entities=max_entities,
            has_entities=bool(entities),
            has_documents=bool(documents)
        )

        sections = []
        tokens_used = 0

        # Budget allocation:
        # - 60% for entity context (4800 tokens if max=8000)
        # - 40% for general documents (3200 tokens)
        entity_budget = int(max_total_tokens * 0.6)
        document_budget = max_total_tokens - entity_budget

        # 1. Extract and build entity-focused context
        if entities:
            entity_section = await self._build_entity_context(
                query=query,
                entities=entities[:max_entities],
                vault_id=vault_id,
                token_budget=entity_budget,
                session=session
            )
            if entity_section:
                sections.append("## Key Entities\n\n" + entity_section)
                # Estimate tokens (rough: 4 chars per token)
                tokens_used += len(entity_section) // 4

        # 2. Add general document context (non-entity-specific)
        if documents and tokens_used < max_total_tokens:
            remaining_budget = min(document_budget, max_total_tokens - tokens_used)
            doc_section = self._build_document_context(
                documents=documents,
                token_budget=remaining_budget
            )
            if doc_section:
                sections.append("## General Context\n\n" + doc_section)
                tokens_used += len(doc_section) // 4

        # 3. Add query for reference
        result = f"# Context for Query: {query}\n\n" + "\n\n".join(sections)

        logger.info(
            "smart_context_formatting_complete",
            sections_created=len(sections),
            estimated_tokens=tokens_used,
            budget_utilized=f"{(tokens_used / max_total_tokens):.1%}"
        )

        return result

    async def _build_entity_context(
        self,
        query: str,
        entities: List[Entity],
        vault_id: UUID,
        token_budget: int,
        session: Optional[Session] = None
    ) -> str:
        """
        Build structured context for key entities.

        Design Decision:
        Use EntityContextBuilder to get prioritized chunks per entity.

        Reasoning:
        - Each entity gets its own context budget
        - Prioritization ensures most relevant chunks come first
        - Clear hierarchical structure for LLM parsing
        """
        entity_sections = []
        tokens_per_entity = token_budget // max(len(entities), 1)

        for entity in entities:
            try:
                # Use EntityContextBuilder to get structured context
                builder = EntityContextBuilder(
                    max_tokens=tokens_per_entity,
                    priority_strategy=UsageBasedPriority(),
                    session=session
                )

                context_result = await builder.build_context(
                    entity_id=entity.id,
                    vault_id=vault_id
                )

                # Format entity section
                entity_section = self._format_entity_section(
                    entity=entity,
                    chunks=context_result.chunks
                )
                entity_sections.append(entity_section)

                logger.debug(
                    "entity_context_built",
                    entity_name=entity.name,
                    chunks_included=len(context_result.chunks),
                    tokens_used=context_result.total_tokens
                )

            except Exception as e:
                logger.warning(
                    "entity_context_build_failed",
                    entity_name=entity.name,
                    error=str(e)
                )
                # Fall back to basic description
                if entity.description:
                    entity_sections.append(
                        f"### {entity.name} ({entity.entity_type.value})\n"
                        f"{entity.description}\n"
                    )

        return "\n\n".join(entity_sections)

    def _format_entity_section(
        self,
        entity: Entity,
        chunks: List[Chunk]
    ) -> str:
        """
        Format entity with its context chunks hierarchically.

        Design Decision:
        Structure: Entity name → Primary source → Relationships → Mentions

        Reasoning:
        Clear hierarchy makes it easy for LLMs to understand:
        - What the entity is (primary source)
        - Who they're connected to (relationships)
        - What they're doing (mentions/usage)
        """
        lines = [f"### {entity.name} ({entity.entity_type.value.upper()})"]

        if not chunks:
            if entity.description:
                lines.append(f"\n{entity.description}")
            return "\n".join(lines)

        # Categorize chunks by type (primary, relationship, mention)
        primary_chunks = []
        relationship_chunks = []
        mention_chunks = []

        for chunk in chunks:
            # Check if this is the primary source
            if entity.primary_source_chunk_id and chunk.id == entity.primary_source_chunk_id:
                primary_chunks.append(chunk)
            # Check if chunk mentions this entity in relationships
            # (This is a simplified heuristic - real implementation would check relationship table)
            elif chunk.mentioned_entity_ids and str(entity.id) in chunk.mentioned_entity_ids:
                # If chunk has multiple entities, it's likely a relationship chunk
                if len(chunk.mentioned_entity_ids) > 1:
                    relationship_chunks.append(chunk)
                else:
                    mention_chunks.append(chunk)
            else:
                mention_chunks.append(chunk)

        # Format primary source
        if primary_chunks:
            lines.append("\n**Definition:**")
            for chunk in primary_chunks:
                lines.append(f"{chunk.content.strip()}")

        # Format relationships
        if relationship_chunks:
            lines.append("\n**Relationships:**")
            for chunk in relationship_chunks[:3]:  # Limit to top 3
                lines.append(f"- {chunk.content.strip()}")

        # Format mentions/context
        if mention_chunks:
            lines.append("\n**Context:**")
            for chunk in mention_chunks[:5]:  # Limit to top 5
                # Truncate very long chunks
                content = chunk.content.strip()
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(f"- {content}")

        return "\n".join(lines)

    def _build_document_context(
        self,
        documents: List[Any],
        token_budget: int
    ) -> str:
        """
        Build context from general documents.

        Design Decision:
        Keep this simple - just list documents with titles and summaries.

        Reasoning:
        General documents are secondary to entity context.
        If the query is about entities (most fiction queries are),
        the entity context is more valuable.
        """
        if not documents:
            return ""

        doc_lines = []
        tokens_used = 0
        chars_per_token = 4  # Rough estimate

        for doc in documents:
            # Estimate tokens for this document
            content = getattr(doc, 'content', '')
            if not content:
                continue

            # Truncate to fit budget
            max_chars = (token_budget - tokens_used) * chars_per_token
            if max_chars <= 0:
                break

            if len(content) > max_chars:
                content = content[:max_chars] + "..."

            title = getattr(doc, 'title', 'Untitled')
            doc_type = getattr(doc, 'doc_type', 'document')

            doc_lines.append(f"**[{doc_type}] {title}**\n{content}")

            tokens_used += len(content) // chars_per_token

        return "\n\n".join(doc_lines)


# Global instance for convenience
smart_formatter = SmartContextFormatter()
