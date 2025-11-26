"""
Subplot Schema - Quick Win Implementation

Enables tracking of parallel storylines (A-story, B-story, C-story) in complex narratives.

Features:
- Subplot hierarchy (nested subplots)
- Scene-subplot links with contribution tracking
- Subplot status and priority
- Character association
- Plot thread integration
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from sqlmodel import Field, Relationship
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin
from .enums import SubplotStatus, ThreadRole


class Subplot(UUIDMixin, TimestampMixin, table=True):
    """
    Represents a subplot or plot thread in the narrative.

    Examples:
    - LOTR A-story: Frodo's quest to destroy the ring
    - LOTR B-story: Aragorn's path to kingship
    - LOTR C-story: Merry & Pippin with Ents
    """
    __tablename__ = "subplots"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # Identity
    name: str = Field(index=True, description="Subplot name (e.g., 'Frodo's Quest')")
    description: Optional[str] = Field(default=None, description="Brief summary of this subplot")

    # Hierarchy
    parent_plot_id: Optional[UUID] = Field(
        default=None,
        foreign_key="subplots.id",
        description="Link to parent plot for nested subplots"
    )

    # Character Association
    main_character_id: Optional[UUID] = Field(
        default=None,
        foreign_key="entities.id",
        description="Primary character driving this subplot"
    )
    related_character_ids: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB),
        description="Other characters involved in this subplot"
    )

    # Status Tracking
    status: SubplotStatus = Field(
        default=SubplotStatus.SETUP,
        description="Current lifecycle stage of subplot"
    )

    # Priority & Importance
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Importance to overall story (1=minor, 10=critical)"
    )

    # Scope Tracking
    first_appearance_scene_id: Optional[UUID] = Field(
        default=None,
        foreign_key="scenes.id",
        description="Scene where this subplot first appears"
    )
    resolution_scene_id: Optional[UUID] = Field(
        default=None,
        foreign_key="scenes.id",
        description="Scene where this subplot resolves"
    )

    # Metrics
    scene_count: int = Field(
        default=0,
        description="Number of scenes that service this subplot"
    )
    total_contribution: float = Field(
        default=0.0,
        description="Sum of all scene contributions to this subplot"
    )

    # Health Tracking
    health_score: int = Field(
        default=100,
        ge=0,
        le=100,
        description="Health indicator (100=healthy, <50=needs attention)"
    )

    # Metadata
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    notes: Optional[str] = None

    def update_metrics(self, session):
        """
        Recalculate subplot metrics based on scene links.

        Args:
            session: Database session
        """
        from sqlmodel import select
        from .library import Scene  # Local import to avoid circular dependency

        # Count scenes linked to this subplot
        links = session.exec(
            select(SceneSubplotLink).where(
                SceneSubplotLink.subplot_id == self.id
            )
        ).all()

        self.scene_count = len(links)
        self.total_contribution = sum(link.contribution for link in links)

        # Calculate health score
        self.health_score = self._calculate_health(links)

    def _calculate_health(self, links: List["SceneSubplotLink"]) -> int:
        """
        Calculate subplot health based on various factors.

        Factors:
        - Scene distribution (is subplot present throughout story?)
        - Contribution levels (are scenes advancing the subplot?)
        - Resolution status (is subplot resolved if status is resolution?)

        Args:
            links: Scene-subplot links

        Returns:
            Health score (0-100)
        """
        if not links:
            return 50  # No data yet

        health = 100

        # Check if subplot appears regularly (not abandoned midway)
        if self.status in [SubplotStatus.RISING, SubplotStatus.CLIMAX]:
            # Subplot should have scenes
            if self.scene_count < 3:
                health -= 20  # Too few scenes for an active subplot

        # Check if subplot is resolved
        if self.status == SubplotStatus.RESOLUTION:
            if not self.resolution_scene_id:
                health -= 30  # Marked as resolved but no resolution scene

        # Check contribution levels
        avg_contribution = self.total_contribution / len(links) if links else 0
        if avg_contribution < 0.3:
            health -= 20  # Scenes barely touch on this subplot

        return max(0, health)


class SceneSubplotLink(UUIDMixin, TimestampMixin, table=True):
    """
    Junction table linking scenes to subplots.

    Tracks how much each scene contributes to each subplot.
    """
    __tablename__ = "scene_subplot_links"

    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")

    # The Link
    scene_id: UUID = Field(foreign_key="scenes.id", index=True)
    subplot_id: UUID = Field(foreign_key="subplots.id", index=True)

    # Role Classification
    role: ThreadRole = Field(
        default=ThreadRole.SECONDARY,
        description="How central is this subplot to the scene?"
    )

    # Contribution Tracking
    contribution: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How much this scene advances the subplot (0.0-1.0)"
    )

    # Purpose
    purpose: Optional[str] = Field(
        default=None,
        description="What this scene does for the subplot (e.g., 'setup', 'complication', 'payoff')"
    )

    # Metadata
    notes: Optional[str] = None
