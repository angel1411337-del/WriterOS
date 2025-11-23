from typing import Optional
from uuid import UUID
from sqlmodel import Field

from .base import UUIDMixin
from sqlmodel import SQLModel, Field
from .world import Entity # Links symbols to entities/objects
from .library import Scene # Links themes to specific scenes

class Theme(UUIDMixin, table=True):
    __tablename__ = "themes"
    name: str # e.g. "Redemption"
    description: str
    strength: float # 0.0 to 1.0 relevance

class Symbol(UUIDMixin, table=True):
    __tablename__ = "symbols"
    name: str # e.g. "The Blue Rose"
    meaning: str
    entity_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
