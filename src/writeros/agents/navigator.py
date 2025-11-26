from typing import List, Optional, Literal, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import networkx as nx

from .base import BaseAgent, BaseAgentOutput, logger
from writeros.rag.retriever import retriever
from sqlmodel import Session, select
from writeros.utils.db import engine
from writeros.schema import Relationship, Entity
from writeros.schema.enums import RelationType, EntityType

# --- EXTRACTOR SCHEMAS ---

class TravelRequest(BaseModel):
    """Schema for extracting travel details from the user query."""
    origin: Optional[str] = Field(None, description="Starting location")
    destination: Optional[str] = Field(None, description="Ending location")
    travel_method: Optional[str] = Field(None, description="Method of travel (raven, horse, ship, foot)")

class ProvenanceData(BaseModel):
    """Provenance metadata for the analysis."""
    expert: str = "Navigator Agent"
    question: str
    goal: str = "Assess feasibility of travel scenario"
    plan: str
    assumptions: List[str] = Field(default_factory=list)

class NavigationOutput(BaseAgentOutput):
    """Concrete output for travel analysis with provenance."""
    route_analyzed: bool = False
    origin: Optional[str] = None
    destination: Optional[str] = None
    travel_method: Optional[str] = None
    
    canonical_data_available: bool = False
    data_source: str = "No canonical data"
    
    distance_miles: Optional[int] = None
    travel_time_days: Optional[float] = None
    travel_time_range: Optional[str] = None
    
    rag_queries_attempted: List[str] = Field(default_factory=list)
    assumptions_made: List[str] = Field(default_factory=list)
    canonical_evidence: List[str] = Field(default_factory=list)
    
    recommendation: Optional[str] = None
    caveats: List[str] = Field(default_factory=list)
    
    provenance: Optional[ProvenanceData] = None

# --- THE AGENT ---

class NavigatorAgent(BaseAgent):
    def __init__(self, model_name="gpt-4o"):
        super().__init__(model_name)
        
        # Extractors
        self.travel_extractor = self.llm.with_structured_output(TravelRequest)
        
        # Load distances on init
        self.distances_data = self.load_data("distances.json")
        
        # Retriever
        self.retriever = retriever

    async def should_respond(self, query: str, context: str = "") -> tuple[bool, float, str]:
        """
        Navigator responds to travel/logistics queries.
        """
        travel_keywords = [
            "travel", "journey", "ride", "sail", "fly",
            "distance", "miles", "leagues", "arrive", "depart",
            "route", "path", "days", "weeks", "months",
            "horse", "ship", "raven", "walk", "march",
            "from", "to", "reach", "get to", "how long"
        ]
        
        query_lower = query.lower()
        matches = sum(1 for kw in travel_keywords if kw in query_lower)
        
        if matches >= 3:
            return (True, 0.9, f"High travel relevance ({matches} keywords)")
        elif matches >= 2:
            return (True, 0.7, f"Moderate travel relevance ({matches} keywords)")
        elif matches == 1:
            return (True, 0.5, "Possible travel query (1 keyword)")
        else:
            return (False, 0.2, "No travel-related content")

    def calculate_travel(self, origin: str, destination: str, method: str) -> Dict[str, Any]:
        """
        Calculates travel time using hardcoded graph data.
        Returns dict with distance, time, and success status.
        """
        if not self.distances_data:
            return {"success": False, "reason": "Distance data file missing"}

        origin_norm = origin.lower().strip()
        dest_norm = destination.lower().strip()
        
        # Find edge
        edges = self.distances_data.get("edges", [])
        found_edge = None
        
        # ... (existing logic) ...
        return {"success": False, "reason": "Not implemented in snippet"}

    async def find_route(self, origin_id: UUID, destination_id: UUID, max_depth: int = 10) -> Dict[str, Any]:
        """
        Finds the shortest path between two locations using the graph of connected entities.
        
        Args:
            origin_id: Starting location UUID.
            destination_id: Destination location UUID.
            max_depth: Maximum hops.
            
        Returns:
            Dict with 'path' (list of location names) and 'distance' (hops).
        """
        self.log.info("finding_route", origin=str(origin_id), dest=str(destination_id))
        
        with Session(engine) as session:
            # 1. Fetch all location connections
            # Optimization: In a huge graph, we'd use a graph DB or recursive CTE.
            # Here, we fetch all CONNECTED_TO relationships.
            statement = select(Relationship).where(
                Relationship.rel_type == RelationType.CONNECTED_TO
            )
            connections = session.exec(statement).all()
            
            # 2. Build Graph
            G = nx.Graph() # Undirected for travel usually, or DiGraph if one-way
            
            # We also need entity names for the path
            entity_ids = set()
            for conn in connections:
                entity_ids.add(conn.from_entity_id)
                entity_ids.add(conn.to_entity_id)
                
            if not entity_ids:
                 return {"error": "No location connections found in database."}

            entities = session.exec(select(Entity).where(Entity.id.in_(entity_ids))).all()
            entity_map = {e.id: e.name for e in entities}
            
            for conn in connections:
                G.add_edge(str(conn.from_entity_id), str(conn.to_entity_id), weight=1)
                
            # 3. Find Path
            try:
                path_ids = nx.shortest_path(G, source=str(origin_id), target=str(destination_id))
                path_names = [entity_map.get(UUID(pid), "Unknown") for pid in path_ids]
                
                return {
                    "found": True,
                    "path": path_names,
                    "hops": len(path_ids) - 1
                }
            except nx.NetworkXNoPath:
                return {
                    "found": False,
                    "reason": "No path exists between these locations."
                }
            except nx.NodeNotFound:
                 return {
                    "found": False,
                    "reason": "One or both locations not found in the connectivity graph."
                }
        
        for edge in edges:
            s = edge["source"].lower().strip()
            t = edge["target"].lower().strip()
            if (s == origin_norm and t == dest_norm) or (s == dest_norm and t == origin_norm):
                found_edge = edge
                break
        
        if not found_edge:
            return {"success": False, "reason": "No direct route found in DB"}

        # Get speed
        speeds = self.distances_data.get("speeds", {})
        method_norm = method.lower().strip()
        
        if not method_norm or method_norm not in speeds:
            method_norm = "horse" if not method_norm else method_norm
            if method_norm not in speeds:
                 return {"success": False, "reason": f"Unknown method: {method}"}
                
        speed = speeds[method_norm]
        distance = found_edge["miles"]
        time_days = distance / speed
        
        return {
            "success": True,
            "distance": distance,
            "time": time_days,
            "method": method_norm
        }

    async def agentic_rag_traversal(self, query: str, origin: Optional[str], destination: Optional[str]) -> Dict[str, Any]:
        """
        Iteratively queries RAG to gather scattered travel info.
        """
        rag_log = []
        findings = []
        
        # Define queries based on what we know
        queries_to_run = []
        
        if origin:
            queries_to_run.append(f"What do we know about {origin} location?")
        if destination:
            queries_to_run.append(f"What do we know about {destination} location?")
        if origin and destination:
            queries_to_run.append(f"Travel between {origin} and {destination}")
            queries_to_run.append(f"Distance from {origin} to {destination}")
        
        queries_to_run.append("Raven speed and travel times")
        queries_to_run.append("Horse travel speed long distance")
        
        # Execute queries (limited to 4 to save time/tokens)
        for q in queries_to_run[:4]:
            rag_log.append(q)
            try:
                result = await self.retriever.retrieve(query=q, limit=2)
                text_result = self.retriever.format_results(result, max_content_length=300)
                if "No relevant information" not in text_result:
                    findings.append(f"Query: '{q}' -> Found: {text_result[:200]}...")
            except Exception as e:
                self.log.warning("rag_query_failed", query=q, error=str(e))
                
        return {
            "queries": rag_log,
            "findings": findings,
            "context_str": "\n\n".join(findings)
        }

    async def should_respond(self, query: str, context: str = "") -> tuple[bool, float, str]:
        """
        Navigator responds to travel, location, and geography queries.
        """
        nav_keywords = [
            "where", "location", "travel", "distance", "map", "route",
            "journey", "arrive", "depart", "north", "south", "east", "west"
        ]
        
        query_lower = query.lower()
        if any(kw in query_lower for kw in nav_keywords):
            return (True, 0.9, "Query involves travel/location")
        else:
            return (False, 0.2, "No travel context detected")

    async def run(self, full_text: str, existing_notes: str, title: str):
        logger.info(f"🗺️ Navigator analyzing travel in: {title}...")

        # 1. Initial Extraction (Fast Pass)
        extract_prompt = ChatPromptTemplate.from_messages([
            ("system", "Extract origin, destination, and travel method. Return nulls if unsure."),
            ("user", "{full_text}")
        ])
        request: TravelRequest = await (extract_prompt | self.extractor).ainvoke({"full_text": full_text})
        
        origin = request.origin
        destination = request.destination
        method = request.travel_method or "horse"

        # 2. Agentic RAG Traversal
        rag_data = await self.agentic_rag_traversal(full_text, origin, destination)
        
        # 3. Check Canonical Data
        calc_result = {"success": False}
        if origin and destination:
            calc_result = self.calculate_travel(origin, destination, method)

        # 4. Final Analysis with RISEN Prompt
        system_prompt = """
# ROLE
You are the Navigator Agent, a specialist in travel logistics.
Your role is to assess the plausibility of travel scenarios using Socratic reasoning and available data.

# INPUT
User Query: {query}
Extracted Origin: {origin}
Extracted Destination: {destination}
Extracted Method: {method}

# CONTEXT
Canonical Calculation: {calc_result}
RAG Findings:
{rag_context}

# STEPS
1. **Extract**: Confirm origin/destination/method from query and context.
2. **Check Canon**: Use the calculation result if successful.
3. **Synthesize**: If canon fails, use RAG findings to estimate.
4. **Assess**: Determine feasibility.
5. **Construct**: Build the JSON response.

# OUTPUT SCHEMA
Return a JSON object matching `NavigationOutput`.
Include `provenance` object with:
- expert: "Navigator Agent"
- question: {query}
- goal: "Assess feasibility"
- plan: "Extracted -> RAG Traversal -> Calculation/Estimation -> Verdict"
- assumptions: List any assumptions made.
"""
        
        final_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Analyze this travel scenario.")
        ])
        
        # We need a structured output parser for the final result
        # Since we have a complex schema, we'll use the LLM's structured output capability again
        analyzer = self.llm.with_structured_output(NavigationOutput)
        
        result: NavigationOutput = await (final_prompt | analyzer).ainvoke({
            "query": full_text,
            "origin": origin,
            "destination": destination,
            "method": method,
            "calc_result": str(calc_result),
            "rag_context": rag_data["context_str"]
        })
        
        # Fill in missing fields from our side if LLM missed them
        if not result.rag_queries_attempted:
            result.rag_queries_attempted = rag_data["queries"]
            
        return result