from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field, Relationship
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from .base import UUIDMixin, TimestampMixin
from .enums import EntityType, EntityStatus, CanonLayer, CanonStatus, NodeSignificance

class Entity(UUIDMixin, TimestampMixin, table=True):
    """
    Node in the knowledge graph.
    
    Integration with Chunks:
    - source_chunk_ids: chunks that ESTABLISHED this entity
    - mention_chunk_ids: ALL chunks that mention this entity
    - This enables both provenance and retrieval enhancement
    """
    __tablename__ = "entities"
    
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    # ============================================
    # IDENTITY
    # ============================================
    name: str = Field(index=True)
    entity_type: EntityType = Field(index=True)
    aliases: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    description: Optional[str] = None
    
    # ============================================
    # STATUS
    # ============================================
    status: EntityStatus = Field(default=EntityStatus.ALIVE, index=True)
    
    # Canon
    canon_layer: CanonLayer = Field(default=CanonLayer.PRIMARY)
    canon_status: CanonStatus = Field(default=CanonStatus.ACTIVE)
    
    # ============================================
    # CHUNK INTEGRATION (Backward Index)
    # ============================================
    # The chunk(s) that first established this entity exists
    source_chunk_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    primary_source_chunk_id: Optional[UUID] = Field(default=None, foreign_key="chunks.id")
    
    # All chunks that mention this entity (updated incrementally)
    mention_chunk_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    mention_count: int = Field(default=0)
    
    # Temporal bounds (derived from chunk sequences)
    first_appearance_sequence: Optional[int] = Field(default=None, index=True)
    last_appearance_sequence: Optional[int] = Field(default=None, index=True)
    
    # ============================================
    # EXTRACTION PROVENANCE
    # ============================================
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = Field(default="manual")
    # "manual", "llm_extraction", "ner", "user_confirmed"
    
    user_verified: bool = Field(default=False)
    verified_at: Optional[datetime] = None
    
    # ============================================
    # GRAPH METRICS (Computed)
    # ============================================
    # These are updated by background jobs after graph changes
    relationship_count: int = Field(default=0)
    pagerank_score: float = Field(default=0.0)
    betweenness_score: float = Field(default=0.0)
    cluster_id: Optional[int] = None
    
    # Significance (can be user-set or computed)
    significance: NodeSignificance = Field(default=NodeSignificance.MINOR)
    
    # ============================================
    # PROFILE COMPLETENESS (Quality)
    # ============================================
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    # How many expected attributes are filled
    
    has_conflicts: bool = Field(default=False)
    conflict_count: int = Field(default=0)
    
    # ============================================
    # METADATA
    # ============================================
    metadata_: Dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSONB))
    notes: Optional[str] = None

    # Vector Search
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))

    __table_args__ = (
        Index("ix_entities_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("idx_entity_vault_type", "vault_id", "entity_type"),
        Index("idx_entity_vault_significance", "vault_id", "significance"),
        Index("idx_entity_vault_sequence", "vault_id", "first_appearance_sequence"),
    )
