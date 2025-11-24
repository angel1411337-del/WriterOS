from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from sqlmodel import Field, Relationship
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from .base import UUIDMixin, TimestampMixin
from .enums import PacingType, DraftStatus, UserRating

# ============================================
# 1. SOURCE MODEL (The Training Moat)
# ============================================
class Source(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks external wisdom (Youtube, Books, Blogs).
    Enables Archivist's source-aware consolidation.
    """
    __tablename__ = "sources"

    # Identity
    author: str  # "Brandon Sanderson"
    title: Optional[str] = None
    platform: str  # "YouTube", "Blog", "Book"
    url: Optional[str] = None

    # Credibility Signals (Auto-collected)
    view_count: Optional[int] = None
    subscriber_count: Optional[int] = None
    publish_date: Optional[datetime] = None

    # User Signals (Training Data Gold)
    user_rating: Optional[UserRating] = None
    times_cited_by_user: int = 0
    times_cited_by_archivist: int = 0
    times_rejected_by_user: int = 0

    # Calculated Score (0.0 to 1.0)
    credibility_score: float = 0.5
    
    # Content Metadata
    topics: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    genre_focus: Optional[str] = None
    
    # Relationships
    documents: List["Document"] = Relationship(back_populates="source")

    def update_credibility(self):
        """Recalculate score based on signals"""
        score = 0.5
        # Logic matches your requirements
        if self.user_rating == UserRating.HIGH: score += 0.3
        if self.user_rating == UserRating.LOW: score -= 0.3
        
        total_cites = self.times_cited_by_archivist + self.times_rejected_by_user
        if total_cites > 0:
            success_rate = self.times_cited_by_archivist / total_cites
            score += (success_rate - 0.5) * 0.2
            
        self.credibility_score = max(0.0, min(1.0, score))


# ============================================
# 2. CHAPTER MODEL (The Container)
# ============================================
class Chapter(UUIDMixin, TimestampMixin, table=True):
    """
    Manuscript container. Tracks revision status.
    """
    __tablename__ = "chapters"
    vault_id: UUID = Field(index=True)

    chapter_number: int = Field(index=True)
    title: str
    
    # Status
    status: DraftStatus = Field(default=DraftStatus.DRAFT)
    revision_number: int = 1
    
    # Metrics
    word_count: int = 0
    health_score: int = 100 # Decreases with validation issues

    # Relationships
    scenes: List["Scene"] = Relationship(back_populates="chapter")


# ============================================
# 3. SCENE MODEL (The Dramatist's Playground)
# ============================================
class Scene(UUIDMixin, TimestampMixin, table=True):
    """
    The atomic unit of story. 
    Enables tension arcs and pacing analysis.
    """
    __tablename__ = "scenes"
    __table_args__ = (
        Index("ix_scenes_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
    vault_id: UUID = Field(index=True)
    
    # Hierarchy
    chapter_id: Optional[UUID] = Field(default=None, foreign_key="chapters.id")
    chapter: Optional[Chapter] = Relationship(back_populates="scenes")
    
    scene_number: int = Field(index=True)
    title: Optional[str] = None

    # Content
    content: str
    word_count: int = 0

    # ⭐ DRAMATIST FIELDS (The Moat)
    tension_level: int = Field(ge=1, le=10, default=5)
    dominant_emotion: str = "neutral"
    pacing: PacingType = Field(default=PacingType.MEDIUM)
    
    # Metadata
    pov_character_id: Optional[UUID] = Field(default=None) # Link to Entity
    location_id: Optional[UUID] = Field(default=None)      # Link to Entity
    
    # Vector Search
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))

    def calculate_word_count(self):
        self.word_count = len(self.content.split())


# ============================================
# 4. DOCUMENT MODEL (Generic / Craft Advice)
# ============================================
class Document(UUIDMixin, TimestampMixin, table=True):
    """
    Generic storage for Notes, Craft Advice, or loose drafts.
    """
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_embedding", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
    vault_id: UUID = Field(index=True)

    title: str
    content: str
    doc_type: str # "note", "craft_advice", "character_sheet"

    metadata_: Dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSONB))

    # Link to Source (for Craft Advice)
    source_id: Optional[UUID] = Field(default=None, foreign_key="sources.id")
    source: Optional[Source] = Relationship(back_populates="documents")

    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536)))
