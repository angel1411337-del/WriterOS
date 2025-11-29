"""
Universe Manifest Schema
Defines the structure for complex multi-era corpus ingestion.

Used by ingest_universe.py to correctly import books with:
- Chronological ordering
- Era tagging
- Narrator reliability tracking
- Entity disambiguation hints
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class NarratorReliability(str, Enum):
    """Reliability levels for narrators."""
    OMNISCIENT = "omniscient"  # Objective truth (e.g., standard third-person)
    RELIABLE = "reliable"  # Trustworthy first-person
    UNRELIABLE = "unreliable"  # Biased or lying narrator
    CONFLICTING = "conflicting"  # Multiple contradictory sources


class CanonWork(BaseModel):
    """
    A single work (book/novella/chapter) to be ingested.

    Examples:
    - Fire & Blood (history book)
    - The Hedge Knight (novella)
    - A Game of Thrones (main series)
    """
    # Identity
    title: str = Field(description="Book title")
    source_path: str = Field(description="Path to file/folder relative to vault root")

    # Chronology
    ingestion_order: int = Field(
        description="Order to ingest (1=first). Critical for entity resolution."
    )
    story_time_range: Optional[Dict[str, int]] = Field(
        default=None,
        description="In-universe time span. E.g., {'start_year': 1, 'end_year': 300}"
    )

    # Era Tagging
    era_name: str = Field(description="Era this work belongs to (e.g., 'Targaryen Dynasty')")
    era_sequence: int = Field(description="Chronological order of era (1=earliest)")

    # Narrator System
    has_unreliable_narrators: bool = Field(
        default=False,
        description="Does this work have conflicting accounts?"
    )
    default_narrator: Optional[str] = Field(
        default=None,
        description="Primary narrator name (e.g., 'Archmaester Gyldayn')"
    )
    narrator_reliability: NarratorReliability = Field(
        default=NarratorReliability.RELIABLE,
        description="Default reliability level"
    )

    # Entity Resolution Hints
    expected_entities: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of major entities to expect. Helps disambiguation."
    )
    # Example:
    # [
    #   {
    #     "name": "Aegon II",
    #     "type": "character",
    #     "era_start_year": 120,
    #     "era_end_year": 131,
    #     "aliases": ["King Aegon", "The Usurper"]
    #   }
    # ]

    # Canon Layer
    canon_layer: str = Field(
        default="primary",
        description="Canon status: 'primary', 'alternate', 'supplemental', 'non_canon'"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (author, publication_date, genre, etc.)"
    )


class UniverseManifest(BaseModel):
    """
    Complete manifest for a multi-era universe.

    Defines import order and metadata for all canonical works.
    """
    # Identity
    universe_name: str = Field(description="Name of universe (e.g., 'A Song of Ice and Fire')")
    version: str = Field(default="1.0", description="Manifest version")

    # Works to ingest (in order)
    works: List[CanonWork] = Field(
        description="List of works in ingestion order (sorted by ingestion_order)"
    )

    # Era Definitions
    eras: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Era metadata (name, description, color, time_range)"
    )
    # Example:
    # [
    #   {
    #     "name": "Targaryen Dynasty",
    #     "description": "300 years of dragon rule",
    #     "time_range": {"start_year": 1, "end_year": 300},
    #     "color": "#8B0000",
    #     "icon": "🐉"
    #   }
    # ]

    # Entity Disambiguation Rules
    disambiguation_rules: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Global rules for entity resolution"
    )
    # Example:
    # {
    #   "name_patterns": {
    #     "Aegon": "Use era_start_year to distinguish between Aegons"
    #   },
    #   "title_aliases": {
    #     "The King": "context-dependent, resolve from scene"
    #   }
    # }

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Universe-level metadata"
    )

    def get_sorted_works(self) -> List[CanonWork]:
        """Return works sorted by ingestion_order."""
        return sorted(self.works, key=lambda w: w.ingestion_order)

    def get_works_by_era(self, era_name: str) -> List[CanonWork]:
        """Get all works in a specific era."""
        return [w for w in self.works if w.era_name == era_name]
