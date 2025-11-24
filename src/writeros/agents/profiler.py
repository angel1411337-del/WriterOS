from typing import List, Optional, Dict, Any
from uuid import UUID
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger
from writeros.schema import EntityType, RelationType, Entity, Relationship
from sqlmodel import Session, select
from sqlalchemy import text
from writeros.utils.db import engine
from writeros.utils.embeddings import embedding_service

# --- V2 INTERFACE SCHEMAS ---

class VisualTrait(BaseModel):
    feature: str = Field(..., description="Body part or item (e.g. 'Eyes', 'Weapon', 'Clothing')")
    description: str = Field(..., description="Visual detail (e.g. 'Glowing red', 'Rusty iron', 'Velvet cloak')")

class RelationshipExtraction(BaseModel):
    target: str = Field(..., description="Name of the other person/group")
    rel_type: str = Field(..., description="Specific type: Sibling, Parent, Child, Spouse, Enemy, Rival, Ally, Mentor")
    # Drift Optimized: Captures the causal link for relationship stability analysis
    details: Optional[str] = Field(None, description="The 'Why' or 'Leverage'. (e.g. 'Blackmailing him over debt', 'Bound by blood oath')")

class CharacterProfile(BaseModel):
    name: str = Field(..., description="Name of the character")
    role: str = Field(..., description="Role in the story (e.g. Protagonist, Antagonist, Merchant)")
    visual_traits: List[VisualTrait] = Field(default_factory=list)
    # ✅ V2: Strict schema allows drawing specific arrow types (Family vs Enemy)
    relationships: List[RelationshipExtraction] = Field(default_factory=list)

class OrganizationProfile(BaseModel):
    name: str = Field(..., description="Name of the faction/group")
    org_type: str = Field(..., description="Type (e.g. Guild, Empire, Cult)")
    leader: Optional[str] = Field(None, description="Who is in charge?")
    ideology: str = Field(..., description="What do they believe/want?")
    key_assets: List[str] = Field(default_factory=list, description="Resources (e.g. 'The Black Fleet', 'Infinite Mana')")
    rivals: List[str] = Field(default_factory=list, description="Enemy factions")

class LocationProfile(BaseModel):
    name: str = Field(..., description="Name of the place")
    geography: str = Field(..., description="Physical terrain description")
    visual_signature: str = Field(..., description="Key visual aesthetics (e.g. 'Neon rain', 'Gothic spires')")

class WorldExtractionSchema(BaseModel):
    characters: List[CharacterProfile] = Field(default_factory=list)
    organizations: List[OrganizationProfile] = Field(default_factory=list)
    locations: List[LocationProfile] = Field(default_factory=list)

# --- The Agent ---

class ProfilerAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.extractor = self.llm.with_structured_output(WorldExtractionSchema)

    async def run(self, full_text: str, existing_notes: str, title: str):
        self.log.info("extracting_lore", title=title)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Worldbuilding Archivist.
            Extract structured data about People, Places, and Factions.
            
            ### RULES:
            1. **Relationships:** Be specific. Use 'Parent', 'Sibling', 'Spouse' for family. Use 'Enemy', 'Rival' for conflicts. This defines the Graph Topology.
            2. **Visuals:** Capture colors, textures, and specific items.
            3. **Ignore:** Real-world people (authors, narrators) unless they are characters in the story.
            4. **Locations:** Extract key locations mentioned to help the Navigator Agent.
            5. **Drift Context:** For relationships, capture the *leverage* or *cause*. Don't just say "Allies". Say "Allies because they share a common enemy."
            """),
            ("user", f"""
            Existing Context: {existing_notes}
            
            Transcript:
            {full_text}
            """)
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({})

    async def build_family_tree(self, character_id: UUID) -> Dict[str, Any]:
        """
        Builds a family tree visualization using recursive SQL queries.
        Traverses blood relationships to find all family members and their generation levels.
        
        Returns a hierarchical structure with:
        - All family members
        - Generation levels (negative = ancestors, positive = descendants, 0 = same generation)
        - Relationship paths
        """
        self.log.info("building_family_tree", character_id=str(character_id))
        # Implementation placeholder
        return {}

    async def find_similar_entities(self, trait: str, limit: int = 5) -> str:
        """
        Finds entities that are semantically similar to the given trait or description.
        Example: "Honorable warrior" -> Returns characters with those traits.
        """
        self.log.info("searching_similar_entities", trait=trait)
        
        embedding = embedding_service.embed_query(trait)
        
        with Session(engine) as session:
            results = session.exec(
                select(Entity)
                .order_by(Entity.embedding.cosine_distance(embedding))
                .limit(limit)
            ).all()
            
            if not results:
                return "No similar entities found."
                
            formatted_results = []
            for entity in results:
                formatted_results.append(f"ENTITY: {entity.name} ({entity.type})\n{entity.description}")
                
            return "\n\n".join(formatted_results)
    
    async def generate_graph_data(
        self,
        vault_id: UUID,
        graph_type: str = "force",
        max_nodes: int = 100,
        canon_layer: str = "primary",
        entity_types: List[str] = None,
        relationship_types: List[str] = None,
        max_hops: int = 2,
        current_story_time: int = None
    ) -> Dict[str, Any]:
        """
        Generate graph data optimized for D3.js visualization.
        Prioritizes connected nodes and applies clustering for overflow.
        
        Args:
            graph_type: Type of graph ('force', 'family', 'faction', 'location')
            max_nodes: Maximum number of nodes to include
            canon_layer: Canon layer filter
            entity_types: Optional entity type filter
            relationship_types: Optional relationship type filter
            max_hops: Maximum relationship hops (unused currently)
            current_story_time: Optional temporal filter
        """
        # Graph type relationship filters
        GRAPH_TYPE_FILTERS = {
            "family": ["PARENT", "CHILD", "SIBLING", "FAMILY"],
            "faction": ["MEMBER_OF", "LEADS", "ALLY", "ENEMY"],
            "location": ["LOCATED_IN", "CONNECTED_TO"],
            "force": None  # All relationships
        }
        
        type_filters = GRAPH_TYPE_FILTERS.get(graph_type)
        self.log.info("generating_graph_data", vault_id=str(vault_id), graph_type=graph_type)
        
        with Session(engine) as session:
            # ✅ FIXED N+1 QUERY: Use raw SQL to get IDs, then load entities in single query
            # Before: session.get(Entity, row.id) called N times (N+1 problem)
            # After: Load all entities at once with WHERE IN
            query = text("""
                SELECT e.id, COUNT(r.id) as connection_count
                FROM entities e
                LEFT JOIN relationships r ON (r.from_entity_id = e.id OR r.to_entity_id = e.id)
                WHERE e.vault_id = :vault_id
                  AND (:canon_layer = 'all' OR e.canon->>'layer' = :canon_layer)
                  AND e.canon->>'status' = 'active'
                GROUP BY e.id
                ORDER BY connection_count DESC
                LIMIT :max_nodes
            """)

            result = session.execute(query, {
                'vault_id': str(vault_id),
                'canon_layer': canon_layer,
                'max_nodes': max_nodes * 2  # Fetch extra for filtering
            })

            # Extract IDs from result
            entity_ids = [row.id for row in result]

            if not entity_ids:
                return {
                    'nodes': [],
                    'links': [],
                    'clusters': {},
                    'total_hidden': 0
                }

            # ✅ Load ALL entities in ONE query (no loop!)
            all_entities = session.exec(
                select(Entity).where(Entity.id.in_(entity_ids))
            ).all()

            # Apply entity type filter
            if entity_types:
                all_entities = [e for e in all_entities if e.type in entity_types]

            # Limit to max_nodes
            all_entities = all_entities[:max_nodes]
            
            if not all_entities:
                return {
                    'nodes': [],
                    'links': [],
                    'clusters': {},
                    'total_hidden': 0
                }
            
            # Get visible entity IDs
            visible_ids = [str(e.id) for e in all_entities]
            
            # Get relationships only for visible entities
            if type_filters:
                # Apply graph type specific filtering
                rel_query = text("""
                    SELECT r.*
                    FROM relationships r
                    WHERE r.vault_id = :vault_id
                      AND r.from_entity_id::text = ANY(:visible_ids)
                      AND r.to_entity_id::text = ANY(:visible_ids)
                      AND r.rel_type::text = ANY(:type_filters)
                      AND (:canon_layer = 'all' OR r.canon->>'layer' = :canon_layer)
                      AND r.canon->>'status' = 'active'
                """)
                
                rel_result = session.execute(rel_query, {
                    'vault_id': str(vault_id),
                    'visible_ids': visible_ids,
                    'type_filters': type_filters,
                    'canon_layer': canon_layer
                })
            else:
                # No type filtering (force-directed shows all)
                rel_query = text("""
                    SELECT r.*
                    FROM relationships r
                    WHERE r.vault_id = :vault_id
                      AND r.from_entity_id::text = ANY(:visible_ids)
                      AND r.to_entity_id::text = ANY(:visible_ids)
                      AND (:canon_layer = 'all' OR r.canon->>'layer' = :canon_layer)
                      AND r.canon->>'status' = 'active'
                """)
                
                rel_result = session.execute(rel_query, {
                    'vault_id': str(vault_id),
                    'visible_ids': visible_ids,
                    'canon_layer': canon_layer
                })
            
            # ✅ FIXED N+1 QUERY: Extract IDs, then load all relationships in one query
            # Before: session.get(Relationship, row.id) called M times (M+1 problem)
            # After: Load all relationships at once with WHERE IN
            rel_ids = [row.id for row in rel_result]

            relationships = []
            if rel_ids:
                # Load ALL relationships in ONE query
                all_rels = session.exec(
                    select(Relationship).where(Relationship.id.in_(rel_ids))
                ).all()

                for rel in all_rels:
                    # Apply additional relationship type filter if specified
                    if relationship_types and str(rel.rel_type) not in relationship_types:
                        continue

                    # Apply temporal filter
                    if current_story_time is not None:
                        start = rel.effective_from.get("sequence", 0) if rel.effective_from else 0
                        end = rel.effective_until.get("sequence", 999999) if rel.effective_until else 999999
                        if not (start <= current_story_time <= end):
                            continue

                    relationships.append(rel)
            
            # Format for D3.js
            return {
                'nodes': self._format_nodes(all_entities),
                'links': self._format_links(relationships),
                'graph_type': graph_type,
                'clusters': {},
                'total_hidden': 0,
                'stats': {
                    'node_count': len(all_entities),
                    'link_count': len(relationships),
                    'canon_layer': canon_layer,
                }
            }

    def _format_nodes(self, entities: List[Entity]) -> List[Dict[str, Any]]:
        return [{"id": str(e.id), "name": e.name, "type": e.type, "properties": e.properties} for e in entities]

    def _format_links(self, relationships: List[Relationship]) -> List[Dict[str, Any]]:
        return [{"source": str(r.from_entity_id), "target": str(r.to_entity_id), "type": r.rel_type} for r in relationships]

    def generate_graph_html(
        self,
        graph_data: Dict[str, Any],
        vault_path: Path,
        graph_type: str = "force"
    ) -> str:
        """
        Generates a standalone HTML file for the graph visualization.
        Injects the graph data into the D3.js template.
        """
        import json
        
        self.log.info("generating_graph_html", graph_type=graph_type)
        
        # Ensure output directory exists
        output_dir = vault_path / ".writeros" / "graphs"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load template
        # Assuming template is in project_root/templates/
        # We need a robust way to find the template. 
        # For now, we'll try relative to the package or CWD.
        template_path = Path("templates/d3_graph_template.html")
        if not template_path.exists():
            # Try finding it relative to this file
            template_path = Path(__file__).parents[3] / "templates" / "d3_graph_template.html"
            
        if not template_path.exists():
            self.log.error("template_not_found", path=str(template_path))
            raise FileNotFoundError(f"Graph template not found at {template_path}")
            
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()
            
        # Serialize data
        json_data = json.dumps(graph_data, default=str)
        
        # Inject data
        html_content = template_content.replace("{{ GRAPH_DATA }}", json_data)
        html_content = html_content.replace("{{TITLE}}", f"WriterOS Graph - {graph_type.title()}")
        
        # Save output
        output_filename = f"{graph_type}_graph.html"
        output_path = output_dir / output_filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            
        self.log.info("graph_html_saved", path=str(output_path))
        return str(output_path)
