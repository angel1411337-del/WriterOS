from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin
from .enums import ArcType

class CharacterState(UUIDMixin, table=True):
    __tablename__ = "character_states"
    
    character_id: UUID = Field(index=True, foreign_key="entities.id")

    story_location: Dict[str, int] = Field(default_factory=dict, sa_column=Column(JSONB))
    sequence_order: int = Field(index=True)

    # The Psychologist Agent's output goes here
    psych_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    created_at: datetime = Field(default_factory=datetime.utcnow)

class CharacterArc(UUIDMixin, table=True):
    __tablename__ = "character_arcs"
    
    character_id: UUID = Field(index=True, foreign_key="entities.id")
    vault_id: UUID = Field(index=True)

    arc_type: ArcType
    arc_description: str

    starting_state_id: UUID
    ending_state_id: Optional[UUID] = None
    current_state_id: Optional[UUID] = None

    metrics: Dict[str, float] = Field(default_factory=dict, sa_column=Column(JSONB))

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TransformationMoment(UUIDMixin, table=True):
    """
    Specific scenes or events where a character's values/beliefs shift.
    """
    __tablename__ = "transformation_moments"
    
    character_id: UUID = Field(index=True, foreign_key="entities.id")
    scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")
    
    trigger_event: str
    old_belief: str
    new_belief: str
    
    impact_score: int = Field(ge=1, le=10) # How big was this change?
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
