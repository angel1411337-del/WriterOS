from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger
from writeros.schema import Fact, Relationship, Entity
from writeros.schema.enums import RelationType
from sqlmodel import Session, select
from writeros.utils.db import engine
from writeros.utils.embeddings import get_embedding_service
import networkx as nx

# --- V2 EXTRACTION SCHEMAS ---

class PsycheProfile(BaseModel):
    name: str = Field(..., description="Character Name")

    # Core Identity
    archetype: str = Field(..., description="Jungian Archetype")
    moral_alignment: str = Field(..., description="Alignment")

    # The Arc Engine (V2 Fields)
    lie_believed: Optional[str] = Field(None, description="The Lie")
    truth_to_learn: Optional[str] = Field(None, description="The Truth")

    # Emotional State
    core_desire: str = Field(..., description="Desire")
    core_fear: str = Field(..., description="Fear")
    active_wounds: List[str] = Field(default_factory=list, description="Traumas")

    # Behavioral Output
    decision_making_style: str = Field(..., description="Style")

class PsychologyExtraction(BaseModel):
    profiles: List[PsycheProfile] = Field(default_factory=list)

# --- The Agent ---

class PsychologistAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.extractor = self.llm.with_structured_output(PsychologyExtraction)

    async def run(self, full_text: str, existing_notes: str, title: str):
        self.log.info("analyzing_psyche", title=title)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an Expert Character Psychologist.
            Your job is to psychoanalyze characters to track their NARRATIVE ARC.
            
            ### ANALYSIS FRAMEWORK (V2):
            1. **The Lie vs. The Truth:** What false belief drives their mistakes?
            2. **Wounds:** What past trauma is triggered in this text?
            3. **Motivation:** Infer Core Desire and Fear.
            
            ### INSTRUCTIONS:
            - Be specific. If a character lashes out, look for the Wound.
            - If they hesitate, look for the Lie.
            """),
            ("user", """
            Existing Context: {existing_notes}
            
            Transcript/Chapter to Analyze:
            {full_text}
            """)
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({
            "existing_notes": existing_notes,
            "full_text": full_text
        })

    async def find_similar_states(self, query: str, limit: int = 5) -> str:
        """
        Finds psychological states (Facts) similar to the query.
        Example: "Fear of abandonment" -> Returns characters with similar fears/traumas.
        """
        self.log.info("searching_similar_states", query=query)
        
        embedding = get_embedding_service().embed_query(query)
        
        with Session(engine) as session:
            # Search Facts (could filter by fact_type if needed, but semantic search handles it well)
            results = session.exec(
                select(Fact)
                .order_by(Fact.embedding.cosine_distance(embedding))
                .limit(limit)
            ).all()
            
            if not results:
                return "No similar psychological states found."
                
            formatted_results = []
            for fact in results:
                formatted_results.append(f"FACT ({fact.fact_type}): {fact.content}")
                
            return "\n\n".join(formatted_results)

    async def trace_influence(self, entity_id: UUID, max_depth: int = 3) -> Dict[str, Any]:
        """
        Traces the network of social influence around a character.
        
        Args:
            entity_id: The character UUID.
            max_depth: How many degrees of separation to trace.
            
        Returns:
            Dict with 'network' (nodes/edges) and 'centrality' metrics.
        """
        self.log.info("tracing_influence", entity_id=str(entity_id), max_depth=max_depth)
        
        with Session(engine) as session:
            # 1. Fetch relevant relationships (social types)
            social_types = [
                RelationType.FRIEND, RelationType.ENEMY, RelationType.ALLY, 
                RelationType.RIVAL, RelationType.FAMILY, RelationType.SPOUSE,
                RelationType.MENTOR, RelationType.MENTEE, RelationType.LEADS,
                RelationType.MEMBER_OF, RelationType.ROMANTIC_INTEREST,
                RelationType.BETRAYED, RelationType.OWES_DEBT_TO
            ]
            
            statement = select(Relationship).where(Relationship.rel_type.in_(social_types))
            relationships = session.exec(statement).all()
            
            # 2. Build Graph
            G = nx.Graph() # Social networks often undirected for influence, or directed for specific types
            # For simplicity, we'll treat influence as potentially bidirectional or just connectivity
            
            entity_ids = set()
            for rel in relationships:
                entity_ids.add(rel.from_entity_id)
                entity_ids.add(rel.to_entity_id)
                
            if not entity_ids:
                return {"error": "No social relationships found."}
                
            entities = session.exec(select(Entity).where(Entity.id.in_(entity_ids))).all()
            entity_map = {str(e.id): e.name for e in entities}
            
            for rel in relationships:
                G.add_edge(str(rel.from_entity_id), str(rel.to_entity_id), type=rel.rel_type)
                
            # 3. Extract Ego Graph (Subnetwork around the character)
            if str(entity_id) not in G:
                return {"error": "Character not found in social graph."}
                
            ego_G = nx.ego_graph(G, str(entity_id), radius=max_depth)
            
            # 4. Calculate Metrics
            centrality = nx.degree_centrality(ego_G)
            
            nodes = []
            for node in ego_G.nodes():
                nodes.append({
                    "id": node,
                    "name": entity_map.get(node, "Unknown"),
                    "centrality": centrality.get(node, 0)
                })
                
            edges = []
            for u, v, data in ego_G.edges(data=True):
                edges.append({
                    "source": u,
                    "target": v,
                    "type": data.get("type", "unknown")
                })
                
            return {
                "focal_character": entity_map.get(str(entity_id), "Unknown"),
                "network_size": len(nodes),
                "nodes": sorted(nodes, key=lambda x: x['centrality'], reverse=True),
                "edges": edges
            }