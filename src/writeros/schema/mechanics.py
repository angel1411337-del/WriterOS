from typing import Optional
from uuid import UUID
from sqlmodel import Field

from .base import UUIDMixin, TimestampMixin

class SystemRule(UUIDMixin, TimestampMixin, table=True):
    """
    A hard rule for a magic or tech system.
    e.g. "Energy cannot be created, only drawn from heat."
    """
    __tablename__ = "system_rules"
    
    name: str
    description: str
    system_entity_id: UUID = Field(foreign_key="entities.id") # Links to the Magic System Entity
    
    # Consequences of breaking/using
    consequences: str
    
    # Cost to user
    cost_description: Optional[str] = None
    cost_value: int = 0  # Normalized 1-100 scale of "expensiveness"

class LimitBreach(UUIDMixin, TimestampMixin, table=True):
    """
    Instances where rules are broken or pushed to the limit.
    """
    __tablename__ = "limit_breaches"
    
    rule_id: UUID = Field(foreign_key="system_rules.id")
    scene_id: UUID = Field(foreign_key="scenes.id")
    character_id: UUID = Field(foreign_key="entities.id")
    
    consequence_manifested: str # What actually happened?
