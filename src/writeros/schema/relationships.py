from typing import List, Optional
from uuid import UUID
from sqlmodel import Field
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin
from .enums import RelationType, CanonLayer

class Relationship(UUIDMixin, TimestampMixin, table=True):
    """
    Edge in the knowledge graph.
    
    Chunk Integration:
    - source_chunk_ids: chunks that ESTABLISH this relationship
    - co_occurrence_weight: strength derived from how often entities appear together
    """
    __tablename__ = "relationships"
    
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    # ============================================
    # THE EDGE
    # ============================================
    source_entity_id: UUID = Field(index=True, foreign_key="entities.id")
    target_entity_id: UUID = Field(index=True, foreign_key="entities.id")
    relationship_type: RelationType = Field(index=True)
    
    # Directionality
    is_bidirectional: bool = Field(default=False)
    
    # ============================================
    # TEMPORAL BOUNDS (Story Time)
    # ============================================
    established_at_sequence: Optional[int] = Field(default=None, index=True)
    ended_at_sequence: Optional[int] = None
    is_active: bool = Field(default=True, index=True)
    
    # ============================================
    # CHUNK INTEGRATION
    # ============================================
    # Chunks that explicitly establish this relationship
    source_chunk_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    primary_source_chunk_id: Optional[UUID] = Field(default=None, foreign_key="chunks.id")
    
    # Direct quote establishing the relationship
    quote: Optional[str] = None
    
    # Co-occurrence metrics (computed from chunk analysis)
    co_occurrence_count: int = Field(default=0)
    # How many chunks mention BOTH entities
    
    co_occurrence_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    # Normalized: co_occurrence_count / max(entity_a_mentions, entity_b_mentions)
    
    avg_proximity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    # How close entities appear within shared chunks (1.0 = same sentence)
    
    # ============================================
    # RELATIONSHIP STRENGTH
    # ============================================
    strength: float = Field(default=1.0, ge=0.0, le=1.0)
    # Overall strength (can combine explicit + co-occurrence)
    
    sentiment: Optional[str] = None
    # "positive", "negative", "neutral", "complex", "evolving"
    
    # ============================================
    # PROVENANCE
    # ============================================
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = Field(default="manual")
    # "manual", "llm_extraction", "co_occurrence_inference", "user_confirmed"
    
    user_verified: bool = Field(default=False)
    
    # ============================================
    # CANON
    # ============================================
    canon_layer: CanonLayer = Field(default=CanonLayer.PRIMARY)
    
    # ============================================
    # METADATA
    # ============================================
    notes: Optional[str] = None

    __table_args__ = (
        Index("idx_rel_vault_type", "vault_id", "relationship_type"),
        Index("idx_rel_source_target", "source_entity_id", "target_entity_id"),
        Index("idx_rel_vault_active", "vault_id", "is_active"),
    )

    @property
    def bidirectional(self) -> bool:
        from .enums import is_bidirectional
        return is_bidirectional(self.relationship_type)
