from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin
from .enums import AnchorStatus

class Anchor(UUIDMixin, TimestampMixin, table=True):
    """
    Plot points that must happen (The Architect's Domain).
    Now explicitly compatible with Scene/Chapter logic.
    """
    __tablename__ = "anchors"
    vault_id: UUID = Field(index=True)

    name: str
    description: Optional[str] = None
    
    # Target Location: e.g. {"chapter": 5} or {"scene_id": "..."}
    target_location: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    prerequisites: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))

    status: AnchorStatus = Field(default=AnchorStatus.PENDING, index=True)
    
    # Links logic
    character_id: Optional[UUID] = Field(default=None) # Link to Entity
    
    # Validation results
    chapters_remaining: Optional[int] = None
    on_track_score: float = 1.0 # 0.0 to 1.0 probability of hitting anchor

    # Prerequisites tracking (used by ArchitectAgent)
    prerequisites_met: int = Field(default=0)
    prerequisites_total: int = Field(default=0)

    canon: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
