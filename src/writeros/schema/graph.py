from pydantic import BaseModel
from typing import List, Optional

class GraphNode(BaseModel):
    id: str       # UUID string
    label: str    # Entity Name
    group: str    # EntityType (character, location, scene)
    radius: int   # Visual size based on importance (page rank)
    color: Optional[str] = None

class GraphLink(BaseModel):
    source: str   # UUID string of start node
    target: str   # UUID string of end node
    label: str    # Relationship type (friend, enemy)
    value: int    # Connection strength (1-10)

class GraphData(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]
