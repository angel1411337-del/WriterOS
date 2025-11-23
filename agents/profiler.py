from typing import List, Optional, Dict, Any
from uuid import UUID
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger
from src.writeros.schema import EntityType, RelationType, Entity, Relationship
from sqlmodel import Session, select
from sqlalchemy import text
from utils.db import engine
from utils.embeddings import embedding_service

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
        logger.info(f"🕵️ Profiler (V2) extracting lore from: {title}...")

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
        logger.info(f"🌳 Building family tree for character: {character_id}")

    async def find_similar_entities(self, trait: str, limit: int = 5) -> str:
        """
        Finds entities that are semantically similar to the given trait or description.
        Example: "Honorable warrior" -> Returns characters with those traits.
        """
        logger.info(f"🕵️ Profiler searching for entities similar to: {trait}")
        
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
        logger.info(f"📊 Generating graph data for vault {vault_id}")
        
        with Session(engine) as session:
            # Optimized query: prioritize connected nodes
            query = text("""
                SELECT e.*, COUNT(r.id) as connection_count
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
            
            all_entities = []
            for row in result:
                entity = session.get(Entity, row.id)
                if entity:
                    # Apply entity type filter
                    if entity_types and entity.type not in entity_types:
                        continue
                    all_entities.append(entity)
                    if len(all_entities) >= max_nodes:
                        break
            
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
            
            relationships = []
            for row in rel_result:
                rel = session.get(Relationship, row.id)
                if rel:
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
                    'graph_type': graph_type
                }
            }
    
    def _format_nodes(self, entities: List[Entity]) -> List[Dict[str, Any]]:
        """Format entities for D3.js consumption"""
        return [
            {
                'id': str(e.id),
                'name': e.name,
                'type': str(e.type),
                'description': e.description or '',
                'tags': e.tags or [],
                'properties': e.properties or {},
                'canon': {
                    'layer': e.canon.get('layer', 'primary'),
                    'status': e.canon.get('status', 'active')
                }
            }
            for e in entities
        ]

    def _format_links(self, relationships: List) -> List[Dict[str, Any]]:
        """Format relationships for D3.js consumption"""
        return [
            {
                'source': str(r.from_entity_id),
                'target': str(r.to_entity_id),
                'type': str(r.rel_type),
                'description': r.description or '',
                'properties': r.properties or {},
                'effective_from': r.effective_from,
                'effective_until': r.effective_until
            }
            for r in relationships
        ]

    def generate_graph_html(
        self,
        graph_data: Dict[str, Any],
        output_path: str = None,
        vault_path: Path = None,
        graph_type: str = None,
        title: str = None
    ) -> str:
        """
        Generate standalone HTML file with embedded D3.js visualization.
        
        Args:
            graph_data: Graph data dictionary
            output_path: Explicit output path (overrides vault_path logic)
            vault_path: Vault root directory (for .writeros/graphs/ saving)
            graph_type: Graph type for filename
            title: Graph title
        """
        import json
        from pathlib import Path
        from datetime import datetime
        from utils.vault_config import ensure_graph_directory
        
        # Determine output path
        if output_path:
            output = Path(output_path)
        elif vault_path:
            # Save to .writeros/graphs/
            graph_dir = ensure_graph_directory(vault_path)
            graph_type = graph_type or graph_data.get('graph_type', 'force')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = graph_dir / f"{graph_type}_graph_{timestamp}.html"
        else:
            # Default fallback
            graph_type = graph_type or graph_data.get('graph_type', 'force')
            output = Path(f"{graph_type}_graph.html")
        
        # Set title
        if not title:
            graph_type_display = graph_type or graph_data.get('graph_type', 'Relationship')
            title = f"{graph_type_display.capitalize()} Graph"
        
        # Read template
        template_path = Path(__file__).parent.parent / "templates" / "d3_graph_template.html"
        
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        else:
            template = self._get_inline_template()
        
        # Embed data (handle both {{GRAPH_DATA}} and {{ GRAPH_DATA }})
        html = template.replace(
            '{{GRAPH_DATA}}',
            json.dumps(graph_data, indent=2)
        ).replace(
            '{{ GRAPH_DATA }}',
            json.dumps(graph_data, indent=2)
        ).replace(
            '{{TITLE}}',
            title
        ).replace(
            '{{ TITLE }}',
            title
        )
        
        # Write to file
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding='utf-8')
        
        logger.info(f"Graph HTML generated: {output.absolute()}")
        return str(output.absolute())
    
    def _get_inline_template(self) -> str:
        """Fallback inline HTML template"""
        return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{{TITLE}}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        #graph { width: 100vw; height: 100vh; }
        .controls { position: absolute; top: 10px; left: 10px; background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .node { cursor: pointer; }
        .link { stroke: #999; stroke-opacity: 0.6; }
        .node-label { font-size: 10px; pointer-events: none; }
    </style>
</head>
<body>
    <div class="controls">
        <h3>{{TITLE}}</h3>
        <div id="stats"></div>
    </div>
    <svg id="graph"></svg>
    <script>
        const data = {{GRAPH_DATA}};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("#graph")
            .attr("width", width)
            .attr("height", height);
        
        const g = svg.append("g");
        
        // Zoom behavior
        svg.call(d3.zoom()
            .scaleExtent([0.1, 10])
            .on("zoom", (event) => {
                g.attr("transform", event.transform);
            })
        );
        
        // Color scale
        const color = d3.scaleOrdinal()
            .domain(["character", "location", "faction", "item", "event"])
            .range(["#4A90E2", "#50C878", "#E74C3C", "#F39C12", "#9B59B6"]);
        
        // Force simulation
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
        
        // Links
        const link = g.append("g")
            .selectAll("line")
            .data(data.links)
            .join("line")
            .attr("class", "link")
            .attr("stroke-width", 2);
        
        // Nodes
        const node = g.append("g")
            .selectAll("circle")
            .data(data.nodes)
            .join("circle")
            .attr("class", "node")
            .attr("r", 8)
            .attr("fill", d => color(d.type))
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        // Labels
        const label = g.append("g")
            .selectAll("text")
            .data(data.nodes)
            .join("text")
            .attr("class", "node-label")
            .text(d => d.name)
            .attr("x", 12)
            .attr("y", 4);
        
        // Tooltips
        node.append("title")
            .text(d => `${d.name} (${d.type})\n${d.description}`);
        
        // Update positions
        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            label
                .attr("x", d => d.x + 12)
                .attr("y", d => d.y + 4);
        });
        
        // Drag functions
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        // Stats
        d3.select("#stats").html(`
            <p>Nodes: ${data.nodes.length}</p>
            <p>Links: ${data.links.length}</p>
            <p>Canon: ${data.stats.canon_layer}</p>
        `);
    </script>
</body>
</html>'''
