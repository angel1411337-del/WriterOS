"""
Provenance System Schema
Tracks origin, evolution, and usage of facts ("Time Machine" features).

Design Philosophy:
- Event Sourcing: State is derived from a log of changes.
- Epistemic Tracking: Knowledge is separate from truth.
- Dependency Graph: Text depends on facts; changes propagate.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field
from sqlalchemy import Column, JSON

from .base import UUIDMixin, TimestampMixin
from .enums import (
    StateChangeEventType,
    KnowledgeSourceType,
    DependencyType,
    PresenceType,
    IngestionSourceType
)

# ============================================
# 1. STATE CHANGE EVENT (The Log of History)
# ============================================
class StateChangeEvent(UUIDMixin, TimestampMixin, table=True):
    """
    Logs a specific change to an entity's state.
    Replaying these events reconstructs the state at any point in time.
    """
    __tablename__ = "state_change_events"
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Who changed?
    entity_id: UUID = Field(index=True, foreign_key="entities.id")

    # What changed?
    event_type: StateChangeEventType = Field(index=True)
    
    # Details
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # When? (The Two Clocks)
    world_timestamp: Optional[int] = Field(default=None, index=True)  # In-universe time
    narrative_sequence: Optional[int] = Field(default=None, index=True) # Story order
    
    # Causality
    source_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")
    dimension: str = Field(default="reality") # reality, dream, vision
    
    # Retcon Support
    supersedes_event_id: Optional[UUID] = Field(default=None) # If this is a retcon
    is_superseded: bool = Field(default=False)

# ============================================
# 2. CHARACTER KNOWLEDGE (Epistemic State)
# ============================================
class CharacterKnowledge(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks what a character believes to be true.
    """
    __tablename__ = "character_knowledge"
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    character_id: UUID = Field(index=True, foreign_key="entities.id")
    
    # Link to objective truth (optional)
    fact_id: Optional[UUID] = Field(default=None, foreign_key="facts.id")
    
    # Subjective belief
    knowledge_content: str
    subject_entity_id: Optional[UUID] = Field(default=None) # Who/what is this about?
    
    # Provenance of belief
    source_type: KnowledgeSourceType = Field(default=KnowledgeSourceType.UNKNOWN)
    source_entity_id: Optional[UUID] = Field(default=None) # Who told them?
    learned_in_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")
    
    # Meta
    confidence: float = 1.0
    is_accurate: bool = True # Does it match world truth?
    
    # Forgetting/Retcon
    forgotten_at_sequence: Optional[int] = None
    superseded_by_id: Optional[UUID] = None

# ============================================
# 3. CONTENT DEPENDENCY (The "What Breaks" Graph)
# ============================================
class ContentDependency(UUIDMixin, TimestampMixin, table=True):
    """
    Links narrative text to the facts/events it assumes.
    """
    __tablename__ = "content_dependencies"
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # The Dependent (The Text)
    dependent_scene_id: UUID = Field(index=True, foreign_key="scenes.id")
    dependent_text_excerpt: Optional[str] = None
    
    # The Dependency (The Fact)
    dependency_type: DependencyType
    dependency_id: UUID # ID of the Fact, Event, or Entity
    
    # The Assumption
    assumption: str # Plain text: "Jon has Longclaw"
    
    # Status
    is_valid: bool = True
    invalidated_at: Optional[datetime] = None
    invalidation_reason: Optional[str] = None
    
    # AI Meta
    auto_detected: bool = False
    confidence: float = 1.0

# ============================================
# 4. SCENE PRESENCE (Who was where)
# ============================================
class ScenePresence(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks entity presence in a scene.
    """
    __tablename__ = "scene_presence"
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    scene_id: UUID = Field(index=True, foreign_key="scenes.id")
    entity_id: UUID = Field(index=True, foreign_key="entities.id")
    
    presence_type: PresenceType = Field(default=PresenceType.ACTIVE)
    location_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    
    notes: Optional[str] = None

# ============================================
# 5. INGESTION RECORD (Data Origin)
# ============================================
class IngestionRecord(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks how data entered the system.
    """
    __tablename__ = "ingestion_records"
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    source_type: IngestionSourceType
    source_path: Optional[str] = None
    
    # What was ingested?
    target_table: str
    target_id: UUID
    
    # AI Meta
    provided_fields: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    inferred_fields: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    needs_review: bool = False
    review_reason: Optional[str] = None
