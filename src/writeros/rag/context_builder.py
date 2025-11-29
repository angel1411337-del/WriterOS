"""
Entity-centric context building using graph structure.

Purpose:
Builds comprehensive context about an entity by traversing the knowledge graph
and selecting the most relevant chunks within a token budget. Used for
entity-focused queries and agent prompts that need full entity context.

Design Decisions:
1. Used Strategy pattern for prioritization to allow different ordering strategies
2. Separated context building (EntityContextBuilder) from prioritization (ContextPriorityStrategy)
3. Token budget tracking to prevent exceeding LLM context limits
4. Incremental chunk addition with early termination for efficiency

Reasoning:
- Strategy pattern allows pluggable prioritization (by usage, by recency, by importance)
- Separation of concerns makes code testable and maintainable
- Token tracking prevents expensive truncation at LLM level
- Incremental addition avoids loading all chunks into memory

Key Dependencies:
- sqlmodel: Database ORM for fetching entities and chunks
- writeros.schema: Entity, Chunk, Relationship models
- writeros.utils.db: Database session management
- writeros.core.logging: Structured logging

Usage:
    from writeros.rag.context_builder import EntityContextBuilder

    builder = EntityContextBuilder(max_tokens=4000)
    chunks = await builder.build_context(entity_id, vault_id)

See Also:
    - graph_retrieval.py: Graph-enhanced retrieval
    - retriever.py: Main RAG retriever
"""
from abc import ABC, abstractmethod
from typing import List, Set, Optional
from uuid import UUID
from dataclasses import dataclass, field

from sqlmodel import Session, select
from sqlalchemy import or_

from writeros.schema import Entity, Chunk, Relationship
from writeros.utils.db import engine
from writeros.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ContextBuildResult:
    """
    Result of context building operation.

    Purpose:
    Encapsulates the chunks selected for context along with metadata
    about the selection process for debugging and optimization.

    Attributes:
        chunks: List of chunks selected for context
        total_tokens: Total token count of selected chunks
        chunks_by_source: Breakdown of chunks by source type
        budget_utilized: Percentage of token budget used (0.0-1.0)
    """
    chunks: List[Chunk]
    total_tokens: int
    chunks_by_source: dict = field(default_factory=dict)
    budget_utilized: float = 0.0

    def __post_init__(self):
        """
        Calculate derived fields after initialization.

        Design Decision:
        Use __post_init__ for derived calculations instead of properties.

        Reasoning:
        __post_init__ runs once at creation time, properties would recalculate
        on every access. Since these values don't change after creation,
        __post_init__ is more efficient.
        """
        if not self.chunks_by_source:
            self.chunks_by_source = {
                "primary_source": 0,
                "relationship_sources": 0,
                "mention_chunks": 0
            }


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class ContextPriorityStrategy(ABC):
    """
    Abstract base class for chunk prioritization strategies.

    Purpose:
    Defines interface for different prioritization strategies when selecting
    chunks within a token budget. Enables pluggable prioritization logic.

    Design Decision:
    Used ABC instead of Protocol for explicit interface contract.

    Reasoning:
    - Enforces that subclasses implement required methods
    - Makes intent clear (this is an interface)
    - IDE autocomplete support for method signatures
    """

    @abstractmethod
    def prioritize_chunks(
        self,
        chunks: List[Chunk],
        entity_id: UUID
    ) -> List[Chunk]:
        """
        Sort chunks by priority for the given entity.

        Args:
            chunks: List of candidate chunks to prioritize
            entity_id: Entity for which context is being built

        Returns:
            Chunks sorted by priority (highest first)

        Design Decision:
        Accept entity_id even though not all strategies use it.

        Reasoning:
        Future strategies may need entity context (e.g., prioritize chunks
        about entity's relationships). Accepting it now prevents interface
        changes when adding new strategies.
        """
        pass


# ============================================================================
# CONCRETE PRIORITIZATION STRATEGIES
# ============================================================================

class UsageBasedPriority(ContextPriorityStrategy):
    """
    Prioritize chunks by usage frequency.

    Purpose:
    Selects chunks that have been retrieved most frequently, under the
    assumption that high-usage chunks contain important information.

    Design Decision:
    Use usage_count field from Chunk model rather than computing dynamically.

    Reasoning:
    usage_count is updated incrementally during retrieval operations, making
    it O(1) to access here. Computing it dynamically would require querying
    retrieval history (expensive). Trade-off: usage_count may be slightly
    stale, but performance gain is significant.

    Complexity:
    Time: O(n log n) for sorting
    Space: O(1) (in-place sort)
    """

    def prioritize_chunks(
        self,
        chunks: List[Chunk],
        entity_id: UUID
    ) -> List[Chunk]:
        """
        Sort chunks by usage_count (descending).

        Implementation Note:
        Uses sort() with reverse=True instead of sorted() to sort in-place
        and avoid creating a new list.
        """
        chunks.sort(key=lambda c: c.usage_count, reverse=True)
        return chunks


class RecencyBasedPriority(ContextPriorityStrategy):
    """
    Prioritize chunks by recency (most recently indexed first).

    Purpose:
    Selects newest chunks first, useful for evolving entities where recent
    information supersedes older context.

    Use Cases:
    - Entities with evolving states (e.g., character development over time)
    - Recently updated entities (new information available)
    - Debugging (focus on recent changes)

    Complexity:
    Time: O(n log n) for sorting
    Space: O(1) (in-place sort)
    """

    def prioritize_chunks(
        self,
        chunks: List[Chunk],
        entity_id: UUID
    ) -> List[Chunk]:
        """
        Sort chunks by indexed_at timestamp (descending).

        Implementation Note:
        Chunks without indexed_at are placed last (considered oldest).
        """
        chunks.sort(
            key=lambda c: c.indexed_at if c.indexed_at else 0,
            reverse=True
        )
        return chunks


class NarrativeSequencePriority(ContextPriorityStrategy):
    """
    Prioritize chunks by narrative sequence order.

    Purpose:
    Maintains chronological story order, useful for understanding character
    development and plot progression.

    Design Decision:
    Place chunks without narrative_sequence at the end rather than beginning.

    Reasoning:
    Chunks without sequence are typically metadata or out-of-narrative content
    (notes, appendices). They're less important for understanding the story
    progression than sequenced narrative chunks.

    Use Cases:
    - Character arc analysis (need chronological progression)
    - Plot timeline understanding
    - Avoiding spoilers (can truncate at specific sequence)

    Complexity:
    Time: O(n log n) for sorting
    Space: O(1) (in-place sort)
    """

    def prioritize_chunks(
        self,
        chunks: List[Chunk],
        entity_id: UUID
    ) -> List[Chunk]:
        """
        Sort chunks by narrative_sequence (ascending).

        Implementation Note:
        Chunks without narrative_sequence are assigned a large value (999999)
        to place them at the end of the sorted list.
        """
        chunks.sort(
            key=lambda c: c.narrative_sequence if c.narrative_sequence else 999999
        )
        return chunks


# ============================================================================
# MAIN CONTEXT BUILDER
# ============================================================================

class EntityContextBuilder:
    """
    Builds comprehensive context about an entity using graph structure.

    Purpose:
    Constructs a token-budget-aware context by traversing the knowledge graph
    and selecting the most relevant chunks. Used for entity-focused queries
    and agent prompts.

    Algorithm:
    1. Add primary source chunk (highest priority - defines the entity)
    2. Add relationship source chunks (connections to other entities)
    3. Add attribute source chunks (properties and characteristics)
    4. Fill remaining budget with high-value mention chunks

    Design Decisions:
    1. Four-tier prioritization (primary > relationships > attributes > mentions)
    2. Token budget tracking with early termination
    3. Deduplication to prevent duplicate chunks
    4. Configurable prioritization strategy via dependency injection

    Reasoning:
    - Four tiers reflect importance: entity definition > connections > properties > context
    - Token tracking prevents expensive LLM truncation
    - Deduplication improves context quality (no redundant information)
    - Strategy injection allows different use cases (usage-based vs recency-based)

    Performance:
    Time Complexity: O(n log n) where n = total candidate chunks (dominated by sorting)
    Space Complexity: O(n) for storing candidate chunks
    Database Queries: 4-5 queries (entity, relationships, attributes, chunks)

    Attributes:
        max_tokens: Maximum token budget for context
        priority_strategy: Strategy for prioritizing chunks within budget

    Usage:
        # Default usage-based prioritization
        builder = EntityContextBuilder(max_tokens=4000)
        result = await builder.build_context(entity_id, vault_id)

        # Custom recency-based prioritization
        builder = EntityContextBuilder(
            max_tokens=4000,
            priority_strategy=RecencyBasedPriority()
        )
        result = await builder.build_context(entity_id, vault_id)

    See Also:
        - ContextPriorityStrategy: Interface for prioritization strategies
        - UsageBasedPriority: Prioritize by usage frequency
        - RecencyBasedPriority: Prioritize by recency
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        priority_strategy: Optional[ContextPriorityStrategy] = None,
        session: Optional[Session] = None
    ):
        """
        Initialize the context builder.

        Args:
            max_tokens: Maximum token budget for context (default: 4000)
            priority_strategy: Strategy for prioritizing chunks (default: UsageBasedPriority)
            session: Optional database session for testing (default: creates new session)

        Raises:
            ValueError: If max_tokens is not positive

        Design Decision:
        Default to UsageBasedPriority rather than requiring strategy parameter.
        Accept optional session parameter for testability.

        Reasoning:
        - Usage-based is the most common use case (prioritize important chunks).
        - Making it the default reduces boilerplate for common usage while
          still allowing customization via dependency injection.
        - Optional session allows tests to inject a session with uncommitted
          test data, while production code creates its own sessions.
        - This follows dependency injection pattern for better testability.
        """
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")

        self.max_tokens = max_tokens
        self.priority_strategy = priority_strategy or UsageBasedPriority()
        self._session = session

        logger.info(
            "context_builder_initialized",
            max_tokens=max_tokens,
            strategy=self.priority_strategy.__class__.__name__
        )

    async def build_context(
        self,
        entity_id: UUID,
        vault_id: UUID
    ) -> ContextBuildResult:
        """
        Build comprehensive context about an entity.

        Process:
        1. Fetch entity from database
        2. Add primary source chunk (entity definition)
        3. Add relationship source chunks (connections)
        4. Fill remaining budget with mention chunks (usage context)

        Args:
            entity_id: UUID of entity to build context for
            vault_id: Vault containing the entity

        Returns:
            ContextBuildResult with selected chunks and metadata

        Raises:
            ValueError: If entity not found
            ValueError: If entity does not belong to specified vault

        Design Decision:
        Use incremental chunk addition with early termination instead of
        loading all candidates and filtering.

        Reasoning:
        Early termination saves memory and database queries. If we reach
        token budget at step 2, we don't need to fetch mentions.
        For large entities with many mentions, this is a significant optimization.

        Performance:
        Typical case: 4-5 DB queries, ~100ms
        Worst case: Same (early termination prevents expensive operations)
        """
        logger.info("context_build_started", entity_id=str(entity_id), vault_id=str(vault_id))

        # Fetch entity
        entity = await self._get_entity(entity_id, vault_id)

        # Track selected chunks and token budget
        selected_chunks: List[Chunk] = []
        selected_chunk_ids: Set[UUID] = set()
        token_count = 0
        chunks_by_source = {
            "primary_source": 0,
            "relationship_sources": 0,
            "mention_chunks": 0
        }

        # 1. Primary source chunk (highest priority)
        if entity.primary_source_chunk_id and token_count < self.max_tokens:
            primary_chunk = await self._get_chunk(entity.primary_source_chunk_id)
            if primary_chunk:
                selected_chunks.append(primary_chunk)
                selected_chunk_ids.add(primary_chunk.id)
                token_count += primary_chunk.token_count
                chunks_by_source["primary_source"] = 1

                logger.debug(
                    "primary_source_added",
                    chunk_id=str(primary_chunk.id),
                    tokens=primary_chunk.token_count
                )

        # 2. Relationship source chunks
        if token_count < self.max_tokens:
            rel_added = await self._add_relationship_chunks(
                entity_id,
                vault_id,
                selected_chunks,
                selected_chunk_ids,
                token_count
            )
            chunks_by_source["relationship_sources"] = rel_added

        # Update token count after relationship chunks
        token_count = sum(c.token_count for c in selected_chunks)

        # 3. Fill remaining space with high-value mention chunks
        if token_count < self.max_tokens and entity.mention_chunk_ids:
            mention_added = await self._add_mention_chunks(
                entity,
                selected_chunks,
                selected_chunk_ids,
                token_count
            )
            chunks_by_source["mention_chunks"] = mention_added

        # Final token count
        token_count = sum(c.token_count for c in selected_chunks)
        budget_utilized = token_count / self.max_tokens if self.max_tokens > 0 else 0.0

        logger.info(
            "context_build_complete",
            entity_id=str(entity_id),
            chunks_selected=len(selected_chunks),
            total_tokens=token_count,
            budget_utilized=f"{budget_utilized:.1%}",
            chunks_by_source=chunks_by_source
        )

        return ContextBuildResult(
            chunks=selected_chunks,
            total_tokens=token_count,
            chunks_by_source=chunks_by_source,
            budget_utilized=budget_utilized
        )

    async def _get_entity(self, entity_id: UUID, vault_id: UUID) -> Entity:
        """
        Fetch entity from database with validation.

        Args:
            entity_id: UUID of entity to fetch
            vault_id: Expected vault ID

        Returns:
            Entity instance

        Raises:
            ValueError: If entity not found or vault mismatch

        Design Decision:
        Use injected session if available, otherwise create new session.

        Reasoning:
        - Production code: Creates new session (self._session is None)
        - Test code: Uses injected session to access uncommitted test data
        - Follows dependency injection pattern for testability
        """
        if self._session:
            # Use injected session (testing mode)
            entity = self._session.get(Entity, entity_id)
        else:
            # Create new session (production mode)
            with Session(engine) as session:
                entity = session.get(Entity, entity_id)

        if not entity:
            raise ValueError(f"Entity not found: {entity_id}")

        if entity.vault_id != vault_id:
            raise ValueError(
                f"Entity {entity_id} belongs to vault {entity.vault_id}, "
                f"not {vault_id}"
            )

        return entity

    async def _get_chunk(self, chunk_id: UUID) -> Optional[Chunk]:
        """
        Fetch chunk from database.

        Args:
            chunk_id: UUID of chunk to fetch

        Returns:
            Chunk instance or None if not found

        Design Decision:
        Return None instead of raising exception for missing chunks.
        Use injected session if available, otherwise create new session.

        Reasoning:
        Missing chunks can occur due to:
        - Data integrity issues (chunk deleted but reference remains)
        - Race conditions (chunk deleted between query and fetch)
        Returning None allows graceful degradation rather than failing
        the entire context build operation.

        Session handling follows same pattern as _get_entity for consistency
        and testability.
        """
        if self._session:
            # Use injected session (testing mode)
            return self._session.get(Chunk, chunk_id)
        else:
            # Create new session (production mode)
            with Session(engine) as session:
                return session.get(Chunk, chunk_id)

    async def _add_relationship_chunks(
        self,
        entity_id: UUID,
        vault_id: UUID,
        selected_chunks: List[Chunk],
        selected_chunk_ids: Set[UUID],
        current_token_count: int
    ) -> int:
        """
        Add chunks from entity relationships.

        Design Decision:
        Limit to 10 relationships rather than fetching all.

        Reasoning:
        For highly connected entities (e.g., main characters with 50+ relationships),
        fetching all relationships is expensive and most won't fit in token budget.
        Limiting to 10 balances coverage with performance.

        Args:
            entity_id: Entity whose relationships to fetch
            vault_id: Vault context
            selected_chunks: List to append chunks to (mutated in place)
            selected_chunk_ids: Set of already selected chunk IDs (mutated in place)
            current_token_count: Current token count before adding relationships

        Returns:
            Number of relationship chunks added
        """
        # Use injected session if available, otherwise create new session
        if self._session:
            session = self._session
            # Fetch relationships (limit to 10 for performance)
            stmt = select(Relationship).where(
                or_(
                    Relationship.source_entity_id == entity_id,
                    Relationship.target_entity_id == entity_id
                ),
                Relationship.vault_id == vault_id,
                Relationship.is_active == True
            ).limit(10)

            relationships = list(session.exec(stmt).all())

            added_count = 0
            for rel in relationships:
                if current_token_count >= self.max_tokens:
                    break

                if rel.primary_source_chunk_id and rel.primary_source_chunk_id not in selected_chunk_ids:
                    chunk = session.get(Chunk, rel.primary_source_chunk_id)
                    if chunk and current_token_count + chunk.token_count <= self.max_tokens:
                        selected_chunks.append(chunk)
                        selected_chunk_ids.add(chunk.id)
                        current_token_count += chunk.token_count
                        added_count += 1

            return added_count
        else:
            with Session(engine) as session:
                # Fetch relationships (limit to 10 for performance)
                stmt = select(Relationship).where(
                    or_(
                        Relationship.source_entity_id == entity_id,
                        Relationship.target_entity_id == entity_id
                    ),
                    Relationship.vault_id == vault_id,
                    Relationship.is_active == True
                ).limit(10)

                relationships = list(session.exec(stmt).all())

                added_count = 0
                for rel in relationships:
                    if current_token_count >= self.max_tokens:
                        break

                    if rel.primary_source_chunk_id and rel.primary_source_chunk_id not in selected_chunk_ids:
                        chunk = session.get(Chunk, rel.primary_source_chunk_id)
                        if chunk and current_token_count + chunk.token_count <= self.max_tokens:
                            selected_chunks.append(chunk)
                            selected_chunk_ids.add(chunk.id)
                            current_token_count += chunk.token_count
                            added_count += 1

                return added_count

    async def _add_mention_chunks(
        self,
        entity: Entity,
        selected_chunks: List[Chunk],
        selected_chunk_ids: Set[UUID],
        current_token_count: int
    ) -> int:
        """
        Add high-value mention chunks to fill remaining budget.

        Design Decision:
        Use priority_strategy to sort mention chunks before adding.

        Reasoning:
        Different use cases need different prioritization:
        - Research: usage-based (most important chunks)
        - Recent events: recency-based (newest information)
        - Character arc: narrative-sequence (chronological)

        Args:
            entity: Entity whose mention chunks to add
            selected_chunks: List to append chunks to (mutated in place)
            selected_chunk_ids: Set of already selected chunk IDs (mutated in place)
            current_token_count: Current token count before adding mentions

        Returns:
            Number of mention chunks added
        """
        if not entity.mention_chunk_ids:
            return 0

        # Use injected session if available, otherwise create new session
        if self._session:
            session = self._session
            # Fetch mention chunks
            chunk_uuids = [UUID(cid) for cid in entity.mention_chunk_ids]
            stmt = select(Chunk).where(Chunk.id.in_(chunk_uuids))
            mention_chunks = list(session.exec(stmt).all())

            # Apply prioritization strategy
            mention_chunks = self.priority_strategy.prioritize_chunks(
                mention_chunks,
                entity.id
            )

            added_count = 0
            for chunk in mention_chunks:
                if current_token_count >= self.max_tokens:
                    break

                if chunk.id not in selected_chunk_ids:
                    if current_token_count + chunk.token_count <= self.max_tokens:
                        selected_chunks.append(chunk)
                        selected_chunk_ids.add(chunk.id)
                        current_token_count += chunk.token_count
                        added_count += 1

            return added_count
        else:
            with Session(engine) as session:
                # Fetch mention chunks
                chunk_uuids = [UUID(cid) for cid in entity.mention_chunk_ids]
                stmt = select(Chunk).where(Chunk.id.in_(chunk_uuids))
                mention_chunks = list(session.exec(stmt).all())

                # Apply prioritization strategy
                mention_chunks = self.priority_strategy.prioritize_chunks(
                    mention_chunks,
                    entity.id
                )

                added_count = 0
                for chunk in mention_chunks:
                    if current_token_count >= self.max_tokens:
                        break

                    if chunk.id not in selected_chunk_ids:
                        if current_token_count + chunk.token_count <= self.max_tokens:
                            selected_chunks.append(chunk)
                            selected_chunk_ids.add(chunk.id)
                            current_token_count += chunk.token_count
                            added_count += 1

                return added_count
