from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from .base import UUIDMixin, TimestampMixin
from .enums import EntityType, RelationType, FactType

class Entity(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
    vault_id: UUID = Field(index=True)

    type: EntityType = Field(index=True)
    name: str = Field(index=True)
    description: Optional[str] = None

    # Flexible JSON storage
    properties: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    
    # Stores CanonInfo structure
    canon: Dict[str, Any] = Field(default_factory=lambda: {"layer": "primary", "status": "active"}, sa_column=Column(JSONB))
    
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))

class Relationship(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "relationships"
    vault_id: UUID = Field(index=True)
    
    from_entity_id: UUID = Field(index=True, foreign_key="entities.id")
    to_entity_id: UUID = Field(index=True, foreign_key="entities.id")
    
    rel_type: RelationType = Field(index=True)
    description: Optional[str] = None
    
    properties: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    relationship_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    
    effective_from: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    effective_until: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    canon: Dict[str, Any] = Field(default_factory=lambda: {"layer": "primary"}, sa_column=Column(JSONB))

class Fact(UUIDMixin, table=True):
    __tablename__ = "facts"
    __table_args__ = (
        Index("ix_facts_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
    entity_id: UUID = Field(index=True, foreign_key="entities.id")

    fact_type: FactType = Field(index=True)
    content: str
    source: Optional[str] = None
    confidence: float = 1.0

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow) # Only created_at needed here
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))

class Event(UUIDMixin, table=True):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
    vault_id: UUID = Field(index=True)
    name: str
    description: Optional[str] = None

    # Temporal Data
    story_time: Dict[str, int] = Field(default_factory=dict, sa_column=Column(JSONB))
    narrative_time: Dict[str, int] = Field(default_factory=dict, sa_column=Column(JSONB))
    sequence_order: Optional[int] = Field(default=None, index=True)

    causes_event_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))
