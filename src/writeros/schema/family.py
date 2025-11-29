"""
Family Schema (Bloodline Tracking)
Tracks genealogy, inheritance, and legitimacy.

Design Philosophy:
- Bloodline-Centric: Families are about biological/adoptive lineage
- Legitimacy Tracking: Distinguish between trueborn and bastards
- Inheritance Rules: Track succession and claims
- Genealogy: Build family trees with parent/child relationships
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin

class Family(UUIDMixin, TimestampMixin, table=True):
    """
    Represents a bloodline or family unit.
    
    Examples:
    - Baratheon Bloodline (all Baratheons, legitimate and bastards)
    - Stark Family Tree (genealogy of House Stark)
    - Targaryen Dynasty (royal bloodline)
    """
    __tablename__ = "families"
    
    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    # Link to Entity (family can exist as an Entity for relationship tracking)
    entity_id: Optional[UUID] = Field(default=None, foreign_key="entities.id", index=True)
    
    # ============================================
    # IDENTITY
    # ============================================
    family_name: str = Field(index=True)
    # "Baratheon", "Stark", "Targaryen"
    
    description: Optional[str] = None
    
    family_type: str = Field(default="bloodline")
    # "bloodline", "adoptive", "chosen_family", "clan"
    
    # ============================================
    # LEADERSHIP (Family Head)
    # ============================================
    patriarch_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    matriarch_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    
    current_head_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    # The person currently leading the family
    
    # ============================================
    # MEMBERSHIP
    # ============================================
    legitimate_member_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Trueborn members with full inheritance rights
    
    bastard_member_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Illegitimate children (e.g., Gendry Baratheon)
    
    adopted_member_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Adopted members (legal status varies by world)
    
    all_member_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # All members regardless of legitimacy (computed field)
    
    # ============================================
    # INHERITANCE & SUCCESSION
    # ============================================
    inheritance_rules: str = Field(default="primogeniture")
    # "primogeniture" (eldest child), "ultimogeniture" (youngest),
    # "cognatic" (gender-neutral), "agnatic" (male-only),
    # "gavelkind" (divided among children), "elective"
    
    legitimization_policy: Optional[str] = None
    # Can bastards be legitimized? Under what conditions?
    
    current_heir_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    # Who is next in line?
    
    line_of_succession: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Ordered list of Entity UUIDs in succession order
    
    # ============================================
    # BLOODLINE TRAITS
    # ============================================
    bloodline_traits: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    # Physical or magical traits that run in the family
    # Examples: {"hair_color": "black", "eye_color": "blue", "magical_affinity": "fire"}
    
    genetic_markers: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Notable heritable features (Targaryen silver hair, Baratheon black hair)
    
    # ============================================
    # TIMELINE
    # ============================================
    founded_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # When the family was established
    
    extinct_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # If the bloodline died out
    
    status: str = Field(default="active", index=True)
    # "active", "extinct", "exiled", "dormant"
    
    # ============================================
    # METADATA
    # ============================================
    notes: Optional[str] = None


class FamilyMember(UUIDMixin, TimestampMixin, table=True):
    """
    Junction table linking characters to families with legitimacy tracking.
    """
    __tablename__ = "family_members"
    
    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    family_id: UUID = Field(foreign_key="families.id", index=True)
    character_id: UUID = Field(foreign_key="entities.id", index=True)
    
    # ============================================
    # LEGITIMACY
    # ============================================
    is_legitimate: bool = Field(default=True)
    # Trueborn vs bastard
    
    is_adopted: bool = Field(default=False)
    
    legitimized_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # If a bastard was later legitimized
    
    # ============================================
    # PARENTAGE
    # ============================================
    parent_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    # Primary parent linking them to this family
    
    other_parent_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    # Other biological parent (may be from different family)
    
    # ============================================
    # INHERITANCE
    # ============================================
    can_inherit: bool = Field(default=True)
    # Can this person inherit family titles/lands?
    
    inheritance_priority: Optional[int] = None
    # Position in line of succession (1 = first)
    
    # ============================================
    # METADATA
    # ============================================
    notes: Optional[str] = None
