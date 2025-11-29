"""
Temporal Anchoring Schema
Supports the Two-Clock System and Relative Anchors.

Design Philosophy:
- Flexible chronology: Supports both absolute dates and relative ordering
- Era Tags: Group events by narrative phases ("The War Years", "Before the Fall")
- Ordering Constraints: Explicit "must-be-before" relationships
- World Calendars: Custom time systems (e.g., "Year 742 of the Third Age")

Part of WriterOS v2.5 Temporal/Extended Engine Layer.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from sqlmodel import Field, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin


# ============================================
# 1. ORDERING CONSTRAINT (The Dependency Graph)
# ============================================
class OrderingConstraint(UUIDMixin, TimestampMixin, table=True):
    """
    Explicit temporal relationships between scenes.
    Enables the Chronologist to resolve ambiguous timelines.

    Example: "Battle of Helm's Deep must happen BEFORE Destruction of the Ring"
    """
    __tablename__ = "ordering_constraints"

    # 🔒 SECURITY: Must link to Vault (Multi-Tenancy)
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # The Relationship
    source_scene_id: UUID = Field(foreign_key="scenes.id", index=True)
    target_scene_id: UUID = Field(foreign_key="scenes.id", index=True)

    # Constraint Type
    constraint_type: str = Field(default="must_be_before")  # "must_be_before", "must_be_after", "simultaneous"

    # Optional: Confidence score (for AI-suggested constraints)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Source of constraint
    source: str = Field(default="user")  # "user", "chronologist_agent", "inference"

    # Metadata
    notes: Optional[str] = None


# ============================================
# 2. ERA TAG (Narrative Phases)
# ============================================
class EraTag(UUIDMixin, TimestampMixin, table=True):
    """
    Groups events into narrative phases.

    Examples:
    - "The War Years" (scenes 45-67)
    - "Before the Fall" (chapters 1-3)
    - "The Reconstruction Era" (Part II)
    """
    __tablename__ = "era_tags"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Identity
    name: str = Field(index=True)  # "The War Years", "Before the Fall"
    description: Optional[str] = None

    # Visual representation
    color: Optional[str] = None  # "#FF5733" (for timeline UI)
    icon: Optional[str] = None   # "⚔️", "🏰"

    # Ordering
    sequence_order: int = 0  # For sorting eras chronologically

    # Duration (if applicable)
    start_date: Optional[datetime] = None  # Real-world or in-universe date
    end_date: Optional[datetime] = None


# ============================================
# 3. TIME FRAME (The Two-Clock System)
# ============================================
class TimeFrame(UUIDMixin, TimestampMixin, table=True):
    """
    Links Scene to both Real-World time and In-Universe time.

    The Two-Clock System:
    - real_world_date: "June 15, 2024" (reader's calendar)
    - world_date: "Year 742, 3rd Age, Day of Fire" (in-universe)
    """
    __tablename__ = "time_frames"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Link to Scene
    scene_id: UUID = Field(foreign_key="scenes.id", index=True, unique=True)

    # Real-World Time (optional)
    real_world_date: Optional[datetime] = None
    real_world_description: Optional[str] = None  # "Summer 2024"

    # In-Universe Time (flexible format)
    world_date: Optional[str] = None  # "Year 742 of the Third Age"
    world_date_sort_key: Optional[int] = None  # Numeric key for sorting (e.g., 742003 for sorting)

    # Era Link
    era_id: Optional[UUID] = Field(default=None, foreign_key="era_tags.id")

    # Duration
    duration_minutes: Optional[int] = None  # Scene duration in story time

    # Relative position
    days_since_story_start: Optional[int] = None  # For relative timeline


# ============================================
# 4. WORLD DATE (Custom Calendar Systems)
# ============================================
class WorldDate(UUIDMixin, TimestampMixin, table=True):
    """
    Defines custom calendar systems for fantasy/sci-fi worlds.

    Examples:
    - "Gregorian Calendar"
    - "The Elven Calendar of Lorien"
    - "Stardate System (Star Trek)"
    """
    __tablename__ = "world_dates"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Calendar Identity
    name: str = Field(index=True)  # "Elven Calendar", "Imperial Calendar"
    description: Optional[str] = None

    # Structure
    # Stored as JSONB for flexibility
    calendar_structure: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB)
    )
    # Example:
    # {
    #   "months": ["Thawing", "Planting", "Harvest", ...],
    #   "days_per_month": 30,
    #   "special_days": {"Day of Fire": "Thawing 15"}
    # }

    # Conversion formula to numeric sort key (optional)
    conversion_formula: Optional[str] = None  # Python expression or description

    # Default calendar for this vault?
    is_default: bool = False


# ============================================
# 5. TEMPORAL ANCHOR (The Navigator's Tool)
# ============================================
class TemporalAnchor(UUIDMixin, TimestampMixin, table=True):
    """
    Milestone events that serve as reference points.

    Examples:
    - "The Battle of Hogwarts" (Harry Potter)
    - "The Red Wedding" (Game of Thrones)

    Used by Navigator agent to orient the reader.
    """
    __tablename__ = "temporal_anchors"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Identity
    name: str = Field(index=True)  # "The Battle of Hogwarts"
    description: Optional[str] = None

    # Link to Scene (optional - may be abstract)
    scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")

    # Temporal position
    time_frame_id: Optional[UUID] = Field(default=None, foreign_key="time_frames.id")

    # Importance
    importance: int = Field(default=5, ge=1, le=10)  # 10 = major plot turning point

    # Usage tracking
    times_referenced: int = 0  # How often this anchor is used for context
