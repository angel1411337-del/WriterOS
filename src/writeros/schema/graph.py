from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from .enums import NodeSignificance





class GraphNode(BaseModel):
    """Node for visualization and analysis."""
    id: str
    label: str
    group: str  # EntityType
    
    # Visual properties
    radius: int = Field(default=10, ge=1, le=100)
    color: Optional[str] = None
    significance: NodeSignificance = NodeSignificance.MINOR
    
    # Status (affects rendering - e.g., gray out dead characters)
    status: Optional[str] = None  # "alive", "dead", etc.
    is_active: bool = True
    
    # Centrality metrics (computed)
    pagerank: float = Field(default=0.0, ge=0.0, le=1.0)
    degree: int = Field(default=0, ge=0)  # Number of connections
    betweenness: float = Field(default=0.0, ge=0.0)  # Bridge importance
    
    # Clustering
    cluster_id: Optional[int] = None  # Community detection result
    
    # Temporal (for timeline filtering)
    first_appearance_sequence: Optional[int] = None
    last_appearance_sequence: Optional[int] = None
    
    # Tooltip/detail data
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphLink(BaseModel):
    """Edge for visualization and analysis."""
    id: Optional[str] = None  # Relationship UUID
    source: str
    target: str
    label: str  # RelationType
    
    # Visual properties
    value: int = Field(default=1, ge=1, le=10)  # Line thickness
    color: Optional[str] = None
    dashed: bool = False  # For inactive/historical relationships
    
    # Relationship properties
    bidirectional: bool = False
    sentiment: Optional[str] = None  # "positive", "negative", "neutral", "complex"
    is_active: bool = True
    
    # Temporal (for timeline filtering)
    established_at_sequence: Optional[int] = None
    ended_at_sequence: Optional[int] = None
    
    # Canon filtering
    canon_layer: str = "primary"
    
    # Tooltip data
    notes: Optional[str] = None


class GraphMetrics(BaseModel):
    """Aggregate metrics for the graph."""
    node_count: int = 0
    edge_count: int = 0
    density: float = 0.0  # edges / possible edges
    avg_degree: float = 0.0
    cluster_count: int = 0
    
    # Top entities by centrality
    most_connected: List[str] = Field(default_factory=list)  # Node IDs
    most_central: List[str] = Field(default_factory=list)  # By PageRank
    bridge_characters: List[str] = Field(default_factory=list)  # High betweenness


class GraphFilter(BaseModel):
    """Current filter state for the graph view."""
    entity_types: List[str] = Field(default_factory=list)  # Empty = all
    relationship_types: List[str] = Field(default_factory=list)
    canon_layers: List[str] = Field(default_factory=lambda: ["primary"])
    
    # Temporal filtering
    sequence_min: Optional[int] = None
    sequence_max: Optional[int] = None
    
    # Status filtering
    include_inactive: bool = False
    include_dead: bool = True
    
    # Significance filtering
    min_significance: Optional[NodeSignificance] = None
    min_degree: int = 0


class GraphData(BaseModel):
    """Complete graph payload for frontend."""
    nodes: List[GraphNode]
    links: List[GraphLink]
    
    # Metadata
    metrics: Optional[GraphMetrics] = None
    applied_filter: Optional[GraphFilter] = None
    
    # For incremental updates
    snapshot_sequence: Optional[int] = None  # Story position this represents
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Lookup node by ID."""
        return next((n for n in self.nodes if n.id == node_id), None)
    
    def get_neighbors(self, node_id: str) -> List[str]:
        """Get all connected node IDs."""
        neighbors = set()
        for link in self.links:
            if link.source == node_id:
                neighbors.add(link.target)
            elif link.target == node_id or link.bidirectional:
                neighbors.add(link.source)
        return list(neighbors)
    
    def subgraph(self, node_ids: List[str]) -> "GraphData":
        """Extract subgraph containing only specified nodes."""
        node_set = set(node_ids)
        return GraphData(
            nodes=[n for n in self.nodes if n.id in node_set],
            links=[l for l in self.links if l.source in node_set and l.target in node_set],
        )
