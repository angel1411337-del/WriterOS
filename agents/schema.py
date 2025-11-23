"""
WriterOS Universal Schema (V2.5 - Complete)
"""
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

# ============================================
# ENUMS
# ============================================
class EntityType(str, Enum):
    CHARACTER = "character"
    LOCATION = "location"
    FACTION = "faction"
    ITEM = "item"
    ABILITY = "ability"
    MAGIC_SYSTEM = "magic_system"
    TECH_SYSTEM = "tech_system"
    EVENT = "event"
    PLOT_THREAD = "plot_thread"
    NOTE = "note"

class RelationType(str, Enum):
    FRIEND = "friend"
    ENEMY = "enemy"
    ALLY = "ally"
    RIVAL = "rival"
    FAMILY = "family"
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    LOCATED_IN = "located_in"
    CONNECTED_TO = "connected_to"
    MEMBER_OF = "member_of"
    LEADS = "leads"
    HAS_ABILITY = "has_ability"
    REQUIRES = "requires"
    CAUSES = "causes"
    RELATED_TO = "related_to"
    REFERENCES = "references"

class CanonLayer(str, Enum):
    PRIMARY = "primary"
    ALTERNATE = "alternate"
    DRAFT = "draft"
    RETCONNED = "retconned"

class CanonStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    PENDING = "pending"

class FactType(str, Enum):
    TRAIT = "trait"
    ABILITY = "ability"
    RELATIONSHIP = "relationship"
    EVENT = "event"
    FEAR = "fear"
    DESIRE = "desire"
    TRAUMA = "trauma"
    MOTIVATION = "motivation"

class ArcType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    FLAT = "flat"
    CORRUPTION = "corruption"
    REDEMPTION = "redemption"
    DISILLUSIONMENT = "disillusionment"
    COMING_OF_AGE = "coming_of_age"

class AnchorStatus(str, Enum):
    PENDING = "pending"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    COMPLETED = "completed"

# ============================================
# DATABASE MODELS (Tables)
# ============================================

class Entity(SQLModel, table=True):
    __tablename__ = "entities"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    vault_id: UUID = Field(index=True)

    type: EntityType = Field(index=True)
    name: str = Field(index=True)
    description: Optional[str] = None

    # Flexible JSON storage
    properties: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Canon Info
    canon: Dict[str, Any] = Field(default_factory=lambda: {"layer": "primary", "status": "active"}, sa_column=Column(JSONB))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))

class Relationship(SQLModel, table=True):
    __tablename__ = "relationships"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    vault_id: UUID = Field(index=True)
    from_entity_id: UUID = Field(index=True)
    to_entity_id: UUID = Field(index=True)
    rel_type: RelationType = Field(index=True)
    description: Optional[str] = None
    
    properties: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    relationship_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    
    # Temporal Data
    effective_from: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    effective_until: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))

    canon: Dict[str, Any] = Field(default_factory=lambda: {"layer": "primary"}, sa_column=Column(JSONB))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Fact(SQLModel, table=True):
    __tablename__ = "facts"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    entity_id: UUID = Field(index=True)

    fact_type: FactType = Field(index=True)
    content: str
    source: Optional[str] = None
    confidence: float = 1.0

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))

class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    vault_id: UUID = Field(index=True)
    name: str
    description: Optional[str] = None

    story_time: Dict[str, int] = Field(default_factory=dict, sa_column=Column(JSONB))
    narrative_time: Dict[str, int] = Field(default_factory=dict, sa_column=Column(JSONB))
    sequence_order: Optional[int] = Field(default=None, index=True)

    causes_event_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))

class Anchor(SQLModel, table=True):
    __tablename__ = "anchors"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    vault_id: UUID = Field(index=True)

    name: str
    description: Optional[str] = None
    target_location: Dict[str, int] = Field(default_factory=dict, sa_column=Column(JSONB))

    prerequisites: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))

    status: AnchorStatus = Field(default=AnchorStatus.PENDING, index=True)
    prerequisites_met: int = 0
    prerequisites_total: int = 0
    chapters_remaining: Optional[int] = None
    warning_threshold: int = 10

    anchor_category: str = "plot"
    character_id: Optional[UUID] = None
    target_state_changes: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Document(SQLModel, table=True):
    """RAG Storage for Chapters, Scenes, and Notes"""
    __tablename__ = "documents"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    vault_id: UUID = Field(index=True)

    title: str
    content: str
    doc_type: str # chapter, scene, note, craft_advice

    metadata_: Dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSONB))

    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# ============================================
# PSYCHOLOGY V2 MODELS (Tables)
# ============================================

class CharacterState(SQLModel, table=True):
    __tablename__ = "character_states"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    character_id: UUID = Field(index=True)

    story_location: Dict[str, int] = Field(default_factory=dict, sa_column=Column(JSONB))
    sequence_order: int = Field(index=True)

    psych_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    created_at: datetime = Field(default_factory=datetime.utcnow)

class CharacterArc(SQLModel, table=True):
    __tablename__ = "character_arcs"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    character_id: UUID = Field(index=True)
    vault_id: UUID = Field(index=True)

    arc_type: ArcType
    arc_description: str

    starting_state_id: UUID
    ending_state_id: Optional[UUID] = None
    current_state_id: Optional[UUID] = None

    metrics: Dict[str, float] = Field(default_factory=dict, sa_column=Column(JSONB))

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ============================================
# CHAT & PERSISTENCE (Tables)
# ============================================

class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    vault_id: UUID = Field(index=True)
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(index=True)
    role: str # user, assistant, system
    content: str
    agent: Optional[str] = None # which agent responded
    
    context_used: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ============================================
# LOGGING (Table)
# ============================================

class InteractionEvent(SQLModel, table=True):
    __tablename__ = "interactions"

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: str = Field(index=True)
    vault_id: str = Field(index=True)

    event_type: str = Field(index=True)
    event_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    context: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    timestamp: datetime = Field(default_factory=datetime.utcnow)

class CanonInfo(SQLModel):
    layer: CanonLayer = CanonLayer.PRIMARY
    status: CanonStatus = CanonStatus.ACTIVE