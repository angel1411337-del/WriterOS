"""
Group Schema (Social Categories)
Tracks vague social groupings without formal membership.

Design Philosophy:
- Vague Boundaries: Groups don't have precise membership lists
- Contextual Membership: Membership is determined by context (birth, profession, location)
- Social Hierarchy: Track social classes and occupations
- Cultural Categories: Track cultural/ethnic/species groupings
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin

class Group(UUIDMixin, TimestampMixin, table=True):
    """
    Represents a vague social category or grouping.
    
    Examples:
    - Smallfolk (social class)
    - Nobles (social class)
    - Wildlings (cultural/geographic group)
    - The Drowned (religious/cultural group)
    - Merchants (occupation-based group)
    """
    __tablename__ = "groups"
    
    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    # Link to Entity (group can exist as an Entity for relationships)
    entity_id: Optional[UUID] = Field(default=None, foreign_key="entities.id", index=True)
    
    # ============================================
    # IDENTITY
    # ============================================
    name: str = Field(index=True)
    # "Smallfolk", "Nobles", "Wildlings", "Merchants"
    
    description: Optional[str] = None
    
    category_type: str = Field(index=True)
    # "social_class", "occupation", "culture", "species", "religion", "geography"
    
    # ============================================
    # MEMBERSHIP CRITERIA
    # ============================================
    membership_criteria: Optional[str] = None
    # How does one become part of this group?
    # "born into it", "chosen profession", "geographic location", "religious belief"
    
    is_formal: bool = Field(default=False)
    # Is there any formal membership structure? (usually False for groups)
    
    # ============================================
    # SIZE & SCOPE
    # ============================================
    approximate_size: Optional[int] = None
    # Rough estimate of group size (if known)
    
    size_description: Optional[str] = None
    # "thousands", "majority of population", "small minority"
    
    geographic_scope: Optional[str] = None
    # "Westeros-wide", "The North only", "King's Landing"
    
    # ============================================
    # SOCIAL POSITION
    # ============================================
    social_hierarchy_level: Optional[int] = Field(default=None, ge=1, le=10)
    # Where does this group sit in society? (1=lowest, 10=highest)
    
    political_power: int = Field(default=0, ge=0, le=100)
    # How much political influence does this group have collectively?
    
    economic_power: int = Field(default=0, ge=0, le=100)
    # Economic strength of the group
    
    # ============================================
    # CHARACTERISTICS
    # ============================================
    common_traits: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Common characteristics of group members
    # Examples: ["poor", "hardworking", "uneducated"] for smallfolk
    
    typical_occupations: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Jobs commonly held by this group
    
    cultural_practices: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    # Shared customs, traditions, beliefs
    
    # ============================================
    # RELATIONSHIPS
    # ============================================
    allied_group_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Groups that work together or share interests
    
    rival_group_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # Groups in conflict or competition
    
    # ============================================
    # METADATA
    # ============================================
    notes: Optional[str] = None


class GroupMember(UUIDMixin, TimestampMixin, table=True):
    """
    Optional junction table for tracking specific group memberships.
    Only use when group membership is story-relevant.
    """
    __tablename__ = "group_members"
    
    # 🔒 SECURITY: Must link to Vault
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    group_id: UUID = Field(foreign_key="groups.id", index=True)
    entity_id: UUID = Field(foreign_key="entities.id", index=True)
    
    # ============================================
    # MEMBERSHIP DETAILS
    # ============================================
    joined_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # When they became part of this group
    
    left_at: Optional[Dict[str, int]] = Field(default=None, sa_column=Column(JSONB))
    # If they left the group
    
    membership_type: str = Field(default="default")
    # "born_into", "joined", "forced", "temporary"
    
    is_active: bool = Field(default=True)
    # Are they currently part of this group?
    
    # ============================================
    # METADATA
    # ============================================
    notes: Optional[str] = None
