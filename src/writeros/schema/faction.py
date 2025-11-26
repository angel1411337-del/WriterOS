"""
Faction Schema (Political/Military Alliances)
Tracks coalitions and alliances between organizations.

Design Philosophy:
- Alliance-Centric: Factions are coalitions of multiple organizations
- Temporal: Alliances form and dissolve over time
- Purpose-Driven: Alliances have specific goals (military, political, economic)
- Dynamic Membership: Organizations can join/leave alliances
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin

class Faction(UUIDMixin, TimestampMixin, table=True):
    """
    Represents a political or military alliance between organizations.
    
    Examples:
    - Targaryen Loyalists (alliance of houses supporting Targaryens)
    - The Northern Alliance (coalition of northern houses)
    - The Faith Militant (religious-political alliance)
    - The Rebel Coalition (military alliance against the throne)
    """
    __tablename__ = "factions"
    
    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    # Link to Entity (faction exists as an Entity for relationships)
    entity_id: UUID = Field(foreign_key="entities.id", index=True, unique=True)
    
    # ============================================
    # IDENTITY
    # ============================================
    name: str = Field(index=True)
    description: Optional[str] = None
    
    alliance_type: str = Field(index=True)
    # Examples: "military", "political", "economic", "religious", "defensive", "offensive"
    
    # ============================================
    # MEMBERSHIP
    # ============================================
    member_organization_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # List of Organization UUIDs in this alliance
    
    leader_organization_id: Optional[UUID] = Field(default=None, foreign_key="organizations.id")
    # Primary organization leading the alliance (if any)
    
    # ============================================
    # ALLIANCE TERMS
    # ============================================
    treaty_terms: Optional[str] = None
    # Written agreement or verbal understanding
    
    mutual_defense: bool = Field(default=False)
    # Are members obligated to defend each other?
    
    resource_sharing: bool = Field(default=False)
    # Do members share resources?
    
    # ============================================
    # GOALS & PURPOSE
    # ============================================
    primary_goal: Optional[str] = None
    # "Overthrow the current king", "Defend against invasion", "Economic dominance"
    
    goals: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Multiple objectives
    
    # ============================================
    # STATUS & TIMELINE
    # ============================================
    status: str = Field(default="active", index=True)
    # "forming", "active", "weakened", "dissolved", "achieved_goal"
    
    formed_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # Story time when alliance was created
    
    dissolved_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # Story time when alliance ended (if applicable)
    
    dissolution_reason: Optional[str] = None
    # "goal_achieved", "betrayal", "external_defeat", "internal_conflict"
    
    # ============================================
    # STRENGTH & INFLUENCE
    # ============================================
    combined_military_strength: int = Field(default=0, ge=0, le=100)
    # Aggregate strength of all members
    
    political_influence: int = Field(default=0, ge=0, le=100)
    # How much power does this alliance wield?
    
    # ============================================
    # METADATA
    # ============================================
    notes: Optional[str] = None
