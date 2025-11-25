from typing import List
from uuid import UUID
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin

class StyleReport(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "style_reports"
    vault_id: UUID = Field(index=True)

    # Linking to Scene or Chapter. Prompt said Chunk, but Chunk isn't in library.py.
    # Assuming Scene is the atomic unit for style analysis for now.
    scene_id: UUID = Field(foreign_key="scenes.id")

    readability_score: float
    passive_voice_count: int
    adverb_count: int
    suggestions: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
