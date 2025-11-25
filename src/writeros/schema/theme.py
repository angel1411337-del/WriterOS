from typing import Optional
from uuid import UUID
from sqlmodel import Field

from .base import UUIDMixin, TimestampMixin

class Theme(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "themes"
    vault_id: UUID = Field(index=True)

    name: str  # e.g. "Redemption"
    description: str
    strength: float  # 0.0 to 1.0 relevance

class Symbol(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "symbols"
    vault_id: UUID = Field(index=True)

    name: str  # e.g. "The Blue Rose"
    meaning: str
    entity_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
