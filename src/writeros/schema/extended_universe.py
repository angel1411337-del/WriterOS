"""
Extended Universe Schema
Supports Advanced Lore, Historian, and Prophecy engines.

Design Philosophy:
- POV Management: Track what each character knows/believes
- Narrator System: Multiple narrative voices and reliability
- Fact Conflicts: Handle contradictions and unreliable narrators
- Prophecy Tracking: Predictions, visions, and their fulfillment
- Entity Merging: Consolidate duplicate characters/places

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
# 1. POV BOUNDARY (Knowledge Management)
# ============================================
class POVBoundary(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks what each character knows at different points in time.
    Prevents omniscient POV errors.

    Example: "Frodo doesn't know Gandalf is alive until Fangorn"
    """
    __tablename__ = "pov_boundaries"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Who knows what?
    character_id: UUID = Field(foreign_key="entities.id", index=True)
    known_fact_id: UUID = Field(foreign_key="facts.id", index=True)

    # When did they learn it?
    learned_at_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")
    learned_at_timestamp: Optional[datetime] = None  # In-story time

    # How reliable is their knowledge?
    certainty: float = Field(default=1.0, ge=0.0, le=1.0)  # 1.0 = knows for certain, 0.5 = suspects
    is_false_belief: bool = False  # They think they know, but they're wrong

    # Forgetting (optional)
    forgotten_at_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")

    # Source of knowledge
    source: Optional[str] = None  # "witnessed directly", "told by X", "inferred"

    # Metadata
    notes: Optional[str] = None


# ============================================
# 2. NARRATOR (Voice Management)
# ============================================
class Narrator(UUIDMixin, TimestampMixin, table=True):
    """
    Defines narrative voices for multi-POV or frame stories.

    Examples:
    - "Kvothe (present day)" - Unreliable narrator
    - "Omniscient Third Person"
    - "Watson" (Sherlock Holmes stories)
    """
    __tablename__ = "narrators"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Identity
    name: str = Field(index=True)  # "Kvothe (present)", "Watson", "Omniscient"

    # If the narrator is a character
    character_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")

    # Narrator type
    narrator_type: str = Field(default="first_person")
    # Options: "first_person", "third_person_limited", "third_person_omniscient",
    #          "second_person", "stream_of_consciousness"

    # Reliability
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)
    # 1.0 = fully reliable (objective truth)
    # 0.5 = partially unreliable (bias or limited knowledge)
    # 0.0 = completely unreliable (liar or delusional)

    # Bias and perspective
    biases: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Example: ["distrusts authority", "romanticizes past", "minimizes own role"]

    # Active in which scenes?
    # (Scenes can link back to narrator_id if needed)

    # Metadata
    description: Optional[str] = None
    notes: Optional[str] = None


# ============================================
# 3. FACT CONFLICT (Contradiction Management)
# ============================================
class FactConflict(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks contradictions between facts.
    Helps Historian agent resolve inconsistencies.

    Examples:
    - "Gandalf says he's 2000 years old, but timeline suggests 3000"
    - "Character A remembers event differently than Character B"
    """
    __tablename__ = "fact_conflicts"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # The conflicting facts
    fact_a_id: UUID = Field(foreign_key="facts.id", index=True)
    fact_b_id: UUID = Field(foreign_key="facts.id", index=True)

    # Conflict type
    conflict_type: str = Field(default="contradiction")
    # Options: "contradiction", "inconsistent_timeline", "unreliable_narrator",
    #          "retcon", "perspective_difference"

    # Resolution status
    status: str = Field(default="unresolved", index=True)
    # Options: "unresolved", "resolved", "intentional", "ignored"

    # Resolution (if any)
    resolution_notes: Optional[str] = None
    canonical_fact_id: Optional[UUID] = Field(default=None, foreign_key="facts.id")
    # Which fact is the "true" one?

    # Severity
    severity: int = Field(default=5, ge=1, le=10)
    # 10 = major plot hole, 1 = minor detail

    # Detection
    detected_by: str = Field(default="user")  # "user", "historian_agent", "inference"
    detected_at_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")


# ============================================
# 4. PROPHECY VISION (Future Events)
# ============================================
class ProphecyVision(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks predictions, visions, and prophecies.
    Monitors fulfillment and subversions.

    Examples:
    - "The chosen one will defeat the Dark Lord"
    - "A great fire will consume the city"
    """
    __tablename__ = "prophecy_visions"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # The prophecy
    description: str
    full_text: Optional[str] = None  # Original wording (important for interpretation)

    # Who made the prophecy?
    prophet_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    prophecy_source: Optional[str] = None  # "Oracle", "Dream", "Ancient Text"

    # When was it made/discovered?
    uttered_at_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")
    discovered_at_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")

    # Status
    status: str = Field(default="pending", index=True)
    # Options: "pending", "fulfilled", "partially_fulfilled", "subverted", "failed"

    # Fulfillment
    fulfilled_at_scene_id: Optional[UUID] = Field(default=None, foreign_key="scenes.id")
    fulfillment_notes: Optional[str] = None

    # Interpretation
    is_ambiguous: bool = True
    possible_interpretations: List[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Plot importance
    importance: int = Field(default=5, ge=1, le=10)

    # Metadata
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Example: ["macguffin", "red_herring", "major_plot_point"]


# ============================================
# 5. ENTITY MERGE CANDIDATE (Deduplication)
# ============================================
class EntityMergeCandidate(UUIDMixin, TimestampMixin, table=True):
    """
    Identifies potential duplicate entities.
    Helps Archivist consolidate "Strider" and "Aragorn".

    AI-suggested merges require user approval.
    """
    __tablename__ = "entity_merge_candidates"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # The potential duplicates
    primary_entity_id: UUID = Field(foreign_key="entities.id", index=True)
    duplicate_entity_id: UUID = Field(foreign_key="entities.id", index=True)

    # Confidence
    similarity_score: float = Field(ge=0.0, le=1.0)
    # Based on: name similarity, alias overlap, embedding similarity

    # Evidence
    evidence: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    # Example:
    # {
    #   "name_similarity": 0.92,
    #   "shared_aliases": ["The King"],
    #   "embedding_distance": 0.15,
    #   "co_occurrence_count": 47
    # }

    # Status
    status: str = Field(default="pending", index=True)
    # Options: "pending", "approved", "rejected", "merged"

    # Resolution
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None  # "user", "auto_merge"
    merge_notes: Optional[str] = None

    # Detection
    detected_by: str = Field(default="archivist_agent")  # "user", "archivist_agent", "inference"


# ============================================
# 6. LORE ENTRY (Advanced Worldbuilding)
# ============================================
class LoreEntry(UUIDMixin, TimestampMixin, table=True):
    """
    Structured worldbuilding knowledge.
    Supplements the generic Fact model with richer context.

    Examples:
    - Magic System rules
    - Historical events (not in main plot)
    - Cultural practices
    - Languages and their grammar
    """
    __tablename__ = "lore_entries"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Identity
    title: str = Field(index=True)
    category: str = Field(index=True)
    # Examples: "magic_system", "history", "culture", "language", "technology", "religion"

    # Content
    content: str
    summary: Optional[str] = None  # Short version for quick reference

    # Links
    related_entity_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    related_scene_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Canonicity
    canon: Dict[str, Any] = Field(
        default_factory=lambda: {"layer": "primary", "status": "active"},
        sa_column=Column(JSONB)
    )

    # Usage
    times_referenced: int = 0

    # Metadata
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    source_document_id: Optional[UUID] = Field(default=None, foreign_key="documents.id")


# ============================================
# 7. SCENE NARRATOR LINK (Who tells this scene?)
# ============================================
class SceneNarrator(UUIDMixin, TimestampMixin, table=True):
    """
    Links scenes to their narrator.
    Supports multi-POV narratives with different voices.
    """
    __tablename__ = "scene_narrators"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # The link
    scene_id: UUID = Field(foreign_key="scenes.id", index=True)
    narrator_id: UUID = Field(foreign_key="narrators.id", index=True)

    # Reliability override (for this specific scene)
    reliability_override: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Narrative distance
    narrative_distance: str = Field(default="immediate")
    # Options: "immediate" (as it happens), "recent" (days later),
    #          "distant" (years later, memory faded)

    # Metadata
    notes: Optional[str] = None
