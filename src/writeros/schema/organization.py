"""
Organization Schema
Structured tracking for institutions with formal membership and hierarchy.

Design Philosophy:
- Formal Structure: Organizations have charters, rules, and governance
- Hierarchical: Organizations can have parent organizations
- Dynamic Membership: Track formal members with rights/responsibilities
- Territory: Link to controlled locations and headquarters
- Allegiances: Track relationships with other organizations
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin

class Organization(UUIDMixin, TimestampMixin, table=True):
    """
    Represents a structured institution with formal membership.
    
    Examples:
    - House Stark (noble house)
    - The Night's Watch (military order)
    - The Maesters (scholarly institution)
    - The Iron Bank (financial institution)
    """
    __tablename__ = "organizations"
    
    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    # Link to Entity (organization still exists as an Entity for relationships)
    entity_id: UUID = Field(foreign_key="entities.id", index=True, unique=True)
    
    # ============================================
    # IDENTITY
    # ============================================
    organization_type: str = Field(index=True)
    # Examples: "noble_house", "guild", "religion", "military", "merchant", "government"
    
    motto: Optional[str] = None
    sigil_description: Optional[str] = None
    colors: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    
    # ============================================
    # LEADERSHIP
    # ============================================
    leader_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    leadership_type: str = Field(default="undefined")
    # Examples: "monarchy", "council", "elected", "dictatorship", "collective", "theocracy"
    
    council_member_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # List of Entity UUIDs for council/leadership members
    
    succession_rules: Optional[str] = None
    # "primogeniture", "elective", "merit-based", "divine right", etc.
    
    # ============================================
    # MEMBERSHIP
    # ============================================
    member_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # List of Entity UUIDs for all members
    
    member_count: int = Field(default=0)
    # Cached count for quick access
    
    recruitment_policy: Optional[str] = None
    # "hereditary", "invitation", "open", "merit", "bloodline"
    
    # ============================================
    # HIERARCHY
    # ============================================
    parent_organization_id: Optional[UUID] = Field(default=None, foreign_key="organizations.id")
    # For sub-organizations (e.g., House Bolton -> House Stark -> The North)
    
    vassal_organization_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Child organizations under this one
    
    # ============================================
    # TERRITORY & INFLUENCE
    # ============================================
    controlled_location_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Entity IDs of locations controlled by this faction
    
    headquarters_location_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    
    influence_level: int = Field(default=50, ge=0, le=100)
    # 0-100 scale of political/military/economic power
    
    # ============================================
    # RESOURCES & WEALTH
    # ============================================
    wealth_level: int = Field(default=50, ge=0, le=100)
    # 0-100 scale of economic power
    
    military_strength: int = Field(default=50, ge=0, le=100)
    # 0-100 scale of military capability
    
    resources: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    # Custom resources: {"gold_mines": 3, "warships": 50, "trained_soldiers": 10000}
    
    # ============================================
    # STATUS & TIMELINE
    # ============================================
    status: str = Field(default="active", index=True)
    # "active", "dormant", "disbanded", "destroyed", "merged", "exiled"
    
    founded_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # Story time: {"year": 300, "age": "First Age"}
    
    dissolved_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    
    # ============================================
    # METADATA
    # ============================================
    goals: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # ["Reclaim the Iron Throne", "Protect the realm"]
    
    values: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # ["honor", "loyalty", "vengeance"]
    
    customs: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    # Custom traditions, rituals, laws
    
    notes: Optional[str] = None
