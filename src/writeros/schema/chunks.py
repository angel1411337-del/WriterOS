from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlmodel import Field
from sqlalchemy import Column, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector

from .base import UUIDMixin, TimestampMixin

class Chunk(UUIDMixin, TimestampMixin, table=True):
    """
    Atomic unit of content - the bridge between raw text and knowledge graph.
    
    Design Philosophy:
    - Chunks are the SOURCE OF TRUTH for the graph
    - Every graph fact traces back to one or more chunks
    - Chunks know what entities/relationships they contain (forward index)
    - Entities/relationships know what chunks sourced them (backward index)
    """
    __tablename__ = "chunks"
    
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    
    # ============================================
    # CONTENT
    # ============================================
    content: str
    content_hash: str = Field(index=True)  # xxhash for change detection
    token_count: int = Field(default=0)
    
    # ============================================
    # SOURCE LOCATION (Lineage to file)
    # ============================================
    file_path: str = Field(index=True)
    file_hash: str  # detect if source file changed
    
    # Position in file
    line_start: int
    line_end: int
    char_start: int
    char_end: int
    
    # Document structure
    heading_hierarchy: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    # ["Part 1", "Chapter 3", "The Red Wedding"]
    
    chapter_marker: Optional[str] = Field(default=None, index=True)
    # Extracted chapter identifier: "Chapter 3", "III", etc.

    scene_id: Optional[str] = Field(default=None, index=True)
    # Scene identifier from NarrativeChunker (format: "file_path:scene_index")
    # Used by POV Boundary system to filter knowledge by scene

    section_type: Optional[str] = None
    # "narrative", "dialogue", "description", "flashback", "letter", "prophecy"
    # Auto-detected by NarrativeChunker based on content patterns
    
    # ============================================
    # EMBEDDING (RAG)
    # ============================================
    embedding: List[float] = Field(default=None, sa_column=Column(Vector(1536)))
    embedding_model: str = Field(default="text-embedding-3-small")
    
    # ============================================
    # TEMPORAL POSITION (Temporal Firewall)
    # ============================================
    narrative_sequence: Optional[int] = Field(default=None, index=True)
    # Ordinal position in story timeline (not in-universe time)
    # Chapter 1 = 1, Chapter 2 = 2, etc. Flashbacks get sequence of containing chapter.
    
    world_time: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    # In-universe timestamp: {"year": 298, "month": 3, "day": 15, "era": "AC"}
    
    is_flashback: bool = Field(default=False)
    flashback_to_sequence: Optional[int] = None  # what narrative_sequence it depicts
    
    # ============================================
    # GRAPH INTEGRATION (Forward Index)
    # ============================================
    # Entities mentioned in this chunk (extracted)
    mentioned_entity_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    
    # Relationships evidenced in this chunk
    mentioned_relationship_ids: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    
    # Co-occurrence pairs (for relationship inference)
    entity_co_occurrences: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))
    # [{"entity_a": "uuid", "entity_b": "uuid", "proximity": 0.8, "context": "dialogue"}]
    
    # POV character (if determinable)
    pov_entity_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    
    # Primary location of this chunk's events
    location_entity_id: Optional[UUID] = Field(default=None, foreign_key="entities.id")
    
    # ============================================
    # EXTRACTION STATUS
    # ============================================
    extraction_status: str = Field(default="pending", index=True)
    # "pending", "in_progress", "completed", "failed", "needs_review"
    
    entities_extracted: bool = Field(default=False)
    relationships_extracted: bool = Field(default=False)
    attributes_extracted: bool = Field(default=False)
    
    extraction_version: int = Field(default=1)
    # Increment when re-extracting with new prompts/models
    
    last_extraction_at: Optional[datetime] = None
    
    # ============================================
    # QUALITY SIGNALS
    # ============================================
    entity_density: float = Field(default=0.0)
    # entities_mentioned / token_count - higher = more information-dense
    
    is_high_value: bool = Field(default=False)
    # Marked by usage patterns or user feedback
    
    usage_count: int = Field(default=0)
    # How often this chunk has been retrieved
    
    avg_retrieval_rank: Optional[float] = None
    # Average position when retrieved (lower = more relevant)
    
    # ============================================
    # STATUS
    # ============================================
    status: str = Field(default="active", index=True)
    # "active", "stale", "deleted", "superseded"
    
    superseded_by_id: Optional[UUID] = Field(default=None, foreign_key="chunks.id")
    # If content was re-chunked
    
    # ============================================
    # INDEXING METADATA
    # ============================================
    chunk_index: int  # position in document
    chunk_method: str = Field(default="semantic")
    # "semantic", "fixed_size", "sentence", "paragraph", "scene_break"
    
    indexed_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True

# Composite indexes for common queries
Index("idx_chunk_vault_sequence", Chunk.vault_id, Chunk.narrative_sequence)
Index("idx_chunk_vault_file", Chunk.vault_id, Chunk.file_path)
Index("idx_chunk_vault_extraction", Chunk.vault_id, Chunk.extraction_status)
