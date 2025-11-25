from typing import List, Optional, Dict, Any
from uuid import UUID
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger
from writeros.schema import EntityType, RelationType, Entity, Relationship
from sqlmodel import Session, select
from sqlalchemy import text
from writeros.utils import db as db_utils
from writeros.utils.embeddings import get_embedding_service

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
        Builds a family tree visualization using NetworkX graph traversal.
        Traverses family relationships to find all family members and their generation levels.

        Uses NetworkX for graph analysis, enabling future features like:
        - Political influence pathfinding
        - Alliance mapping
        - Chemistry/relationship strength calculation

        Returns a hierarchical structure with:
        - All family members with their properties
        - Generation levels (negative = ancestors, positive = descendants, 0 = same generation)
        - Total member count and generation range

        Args:
            character_id: UUID of the character to build the tree from

        Returns:
            Dict containing:
                - total_members: int
                - generation_range: {"min": int, "max": int}
                - generations: {generation_level: [{"id": str, "name": str, "type": str, "properties": dict}]}
        """
        import networkx as nx
        from collections import deque

        self.log.info("building_family_tree", character_id=str(character_id))

        # Step 1: Fetch the root entity to get vault_id
        with Session(db_utils.engine) as session:
            root_entity = session.get(Entity, character_id)
            if not root_entity:
                self.log.error("entity_not_found", character_id=str(character_id))
                return {
                    "total_members": 0,
                    "generation_range": {"min": 0, "max": 0},
                    "generations": {}
                }

            vault_id = root_entity.vault_id

            # Step 2: Fetch all entities and relationships for this vault (single query)
            # This is more efficient than recursive queries
            all_entities = session.exec(
                select(Entity).where(Entity.vault_id == vault_id)
            ).all()

            all_relationships = session.exec(
                select(Relationship).where(
                    Relationship.vault_id == vault_id,
                    Relationship.rel_type.in_([
                        RelationType.PARENT,
                        RelationType.CHILD,
                        RelationType.SIBLING,
                        RelationType.FAMILY
                    ])
                )
            ).all()

            # Convert to dicts for easier access
            entity_map = {str(e.id): e for e in all_entities}

        # Step 3: Build NetworkX graph
        G = nx.DiGraph()

        # Add all entities as nodes with their properties
        for entity_id, entity in entity_map.items():
            G.add_node(entity_id, entity=entity)

        # Add edges with relationship type metadata
        for rel in all_relationships:
            from_id = str(rel.from_entity_id)
            to_id = str(rel.to_entity_id)

            # Add edge with relationship type
            G.add_edge(from_id, to_id, rel_type=rel.rel_type)

            # Add reverse edges to make graph symmetric
            if rel.rel_type == RelationType.PARENT:
                # Parent -[PARENT]-> Child, so add Child -[CHILD]-> Parent
                G.add_edge(to_id, from_id, rel_type=RelationType.CHILD)
            elif rel.rel_type == RelationType.CHILD:
                # Child -[CHILD]-> Parent, so add Parent -[PARENT]-> Child
                G.add_edge(to_id, from_id, rel_type=RelationType.PARENT)
            elif rel.rel_type in [RelationType.SIBLING, RelationType.FAMILY]:
                # For SIBLING and FAMILY, add reverse edge (bidirectional, same type)
                G.add_edge(to_id, from_id, rel_type=rel.rel_type)

        # Step 4: Calculate generations using BFS
        target_id = str(character_id)

        if target_id not in G:
            self.log.error("entity_not_in_graph", character_id=target_id)
            return {
                "total_members": 0,
                "generation_range": {"min": 0, "max": 0},
                "generations": {}
            }

        # BFS to find all reachable family members and their generations
        visited = {target_id: 0}  # {entity_id: generation}
        queue = deque([(target_id, 0)])  # (entity_id, generation)
        max_depth = 15  # Limit to prevent infinite loops

        while queue:
            current_id, current_gen = queue.popleft()

            # Check depth limit
            if abs(current_gen) > max_depth:
                self.log.warning("max_depth_reached", entity_id=current_id, generation=current_gen)
                continue

            # Get all neighbors (both outgoing AND incoming edges)
            # Outgoing edges: relationships where current is the source
            for neighbor_id in G.neighbors(current_id):
                if neighbor_id in visited:
                    continue

                edge_data = G[current_id][neighbor_id]
                rel_type = edge_data.get('rel_type')

                if rel_type == RelationType.PARENT:
                    # Current → PARENT → Neighbor means neighbor is current's child
                    neighbor_gen = current_gen + 1
                elif rel_type == RelationType.CHILD:
                    # Current → CHILD → Neighbor means neighbor is current's parent
                    neighbor_gen = current_gen - 1
                elif rel_type in [RelationType.SIBLING, RelationType.FAMILY]:
                    # Same generation
                    neighbor_gen = current_gen
                else:
                    neighbor_gen = current_gen

                visited[neighbor_id] = neighbor_gen
                queue.append((neighbor_id, neighbor_gen))

            # Incoming edges: relationships where current is the target
            for predecessor_id in G.predecessors(current_id):
                if predecessor_id in visited:
                    continue

                edge_data = G[predecessor_id][current_id]
                rel_type = edge_data.get('rel_type')

                if rel_type == RelationType.PARENT:
                    # Predecessor -[PARENT]→ Current means predecessor is current's parent
                    predecessor_gen = current_gen - 1
                elif rel_type == RelationType.CHILD:
                    # Predecessor -[CHILD]→ Current means predecessor is current's child
                    predecessor_gen = current_gen + 1
                elif rel_type in [RelationType.SIBLING, RelationType.FAMILY]:
                    # Same generation
                    predecessor_gen = current_gen
                else:
                    predecessor_gen = current_gen

                visited[predecessor_id] = predecessor_gen
                queue.append((predecessor_id, predecessor_gen))

        # Step 5: Group by generation and build result
        generations = {}
        for entity_id, generation in visited.items():
            if generation not in generations:
                generations[generation] = []

            entity = entity_map.get(entity_id)
            if entity:
                generations[generation].append({
                    "id": str(entity.id),
                    "name": entity.name,
                    "type": entity.type,
                    "properties": entity.properties
                })

        # Sort members within each generation by name
        for gen in generations:
            generations[gen] = sorted(generations[gen], key=lambda x: x['name'])

        # Calculate statistics
        total_members = len(visited)
        gen_values = list(generations.keys())
        gen_min = min(gen_values) if gen_values else 0
        gen_max = max(gen_values) if gen_values else 0

        self.log.info(
            "family_tree_built",
            character_id=target_id,
            total_members=total_members,
            generation_range={"min": gen_min, "max": gen_max}
        )

        return {
            "total_members": total_members,
            "generation_range": {"min": gen_min, "max": gen_max},
            "generations": generations
        }

    async def find_similar_entities(self, trait: str, limit: int = 5) -> str:
        """
        Finds entities that are semantically similar to the given trait or description.
        Example: "Honorable warrior" -> Returns characters with those traits.
        """
        self.log.info("searching_similar_entities", trait=trait)

        embedding = get_embedding_service().embed_query(trait)

        with Session(db_utils.engine) as session:
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

    async def resolve_entity_by_era(
        self,
        name: str,
        vault_id: UUID,
        current_story_time: Optional[Dict[str, int]] = None,
        current_scene_id: Optional[UUID] = None
    ) -> Optional[Entity]:
        """
        Resolve entity by name with temporal disambiguation.

        This is critical for Phase 2.5 (Citadel Pipeline) to prevent creating
        duplicate entities when the same name appears in different eras.

        Logic:
        1. Find all entities with matching name in this vault
        2. If current_story_time is provided:
           - Check metadata for era_start_year and era_end_year
           - Return entity whose era contains current_story_time
        3. If multiple matches or no temporal context:
           - Return most recently created entity (assume it's current)

        Args:
            name: Entity name (e.g., "Aegon")
            vault_id: Vault to search in
            current_story_time: Current in-universe time (e.g., {"year": 130})
            current_scene_id: Optional scene context

        Returns:
            Resolved Entity or None if no match
        """
        self.log.info(
            "resolving_entity_by_era",
            name=name,
            story_time=current_story_time
        )

        with Session(db_utils.engine) as session:
            # Find all entities with matching name
            matches = session.exec(
                select(Entity).where(
                    Entity.vault_id == vault_id,
                    Entity.name == name
                )
            ).all()

            if not matches:
                self.log.info("no_entity_match", name=name)
                return None

            if len(matches) == 1:
                # Single match - easy case
                return matches[0]

            # Multiple matches - disambiguate by era
            if current_story_time and "year" in current_story_time:
                current_year = current_story_time["year"]

                for entity in matches:
                    # Check if metadata contains era info
                    metadata = entity.metadata_ or {}
                    era_start = metadata.get("era_start_year")
                    era_end = metadata.get("era_end_year")

                    if era_start is not None and era_end is not None:
                        if era_start <= current_year <= era_end:
                            self.log.info(
                                "entity_resolved_by_era",
                                name=name,
                                entity_id=str(entity.id),
                                era_range=f"{era_start}-{era_end}",
                                current_year=current_year
                            )
                            return entity

            # Fallback: Return most recently created entity
            # Sort by created_at descending
            matches_sorted = sorted(matches, key=lambda e: e.created_at, reverse=True)
            fallback = matches_sorted[0]

            self.log.warning(
                "entity_disambiguation_fallback",
                name=name,
                matched_count=len(matches),
                selected_id=str(fallback.id)
            )

            return fallback

    async def find_or_create_entity(
        self,
        name: str,
        entity_type: EntityType,
        vault_id: UUID,
        description: Optional[str] = None,
        override_metadata: Optional[Dict[str, Any]] = None,
        current_story_time: Optional[Dict[str, int]] = None
    ) -> Entity:
        """
        Find existing entity by name and era, or create a new one.

        This is the MAIN method used during universe ingestion to prevent duplicates.

        Workflow:
        1. Try to resolve entity by name + era
        2. If found, return existing entity
        3. If not found, create new entity with metadata

        Args:
            name: Entity name
            entity_type: Type (CHARACTER, LOCATION, etc.)
            vault_id: Vault ID
            description: Optional description
            override_metadata: Metadata from manifest (contains era info)
            current_story_time: Current in-universe time

        Returns:
            Existing or newly created Entity
        """
        # Step 1: Try to resolve existing entity
        existing = await self.resolve_entity_by_era(
            name=name,
            vault_id=vault_id,
            current_story_time=current_story_time
        )

        if existing:
            self.log.info(
                "entity_found_reusing",
                name=name,
                entity_id=str(existing.id)
            )
            return existing

        # Step 2: Create new entity
        self.log.info(
            "entity_not_found_creating",
            name=name,
            type=entity_type
        )

        # Merge metadata
        metadata = override_metadata or {}

        # Generate embedding
        embedding_text = f"{name}\n{description or ''}"
        embedding = get_embedding_service().embed_query(embedding_text)

        # Create entity
        with Session(db_utils.engine) as session:
            entity = Entity(
                vault_id=vault_id,
                name=name,
                type=entity_type,
                description=description or f"Auto-created: {name}",
                embedding=embedding,
                metadata_=metadata
            )

            session.add(entity)
            session.commit()
            session.refresh(entity)

            self.log.info(
                "entity_created",
                name=name,
                entity_id=str(entity.id),
                type=entity_type
            )

            return entity
    
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
        
        with Session(db_utils.engine) as session:
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
        """
        Formats links with visual attributes based on RelationType.
        """
        formatted = []
        
        # Visual Schema Definition
        VISUAL_STYLES = {
            # 🔴 HOSTILE (Red)
            "enemy":    {"color": "#FF4444", "width": 2, "dash": "5,5"},
            "rival":    {"color": "#FF8800", "width": 1.5, "dash": "3,3"},
            "betrayed": {"color": "#CC0000", "width": 3, "dash": "2,2"},
            "killed":   {"color": "#000000", "width": 1, "dash": "1,1"},
            
            # 🟢 ALLIED (Green)
            "ally":     {"color": "#44FF44", "width": 2, "dash": None},
            "friend":   {"color": "#88FF88", "width": 1.5, "dash": None},
            "spouse":   {"color": "#00CC00", "width": 3, "dash": None},
            "leads":    {"color": "#00FFCC", "width": 2, "dash": None},
            
            # 🔵 FAMILY (Blue)
            "parent":   {"color": "#4444FF", "width": 2, "dash": None},
            "child":    {"color": "#4444FF", "width": 2, "dash": None},
            "sibling":  {"color": "#8888FF", "width": 1.5, "dash": None},
            "family":   {"color": "#AAAAFF", "width": 1, "dash": None},
            
            # 🟣 MENTORSHIP (Purple)
            "mentor":   {"color": "#AA00FF", "width": 2, "dash": "5,1"},
            "mentee":   {"color": "#AA00FF", "width": 1, "dash": "5,1"},
            
            # ⚪ DEFAULT (Grey)
            "default":  {"color": "#999999", "width": 1, "dash": None}
        }

        for r in relationships:
            # Normalize type string (handle Enum or str)
            r_type = str(r.rel_type).lower() if r.rel_type else "default"
            
            # Lookup style (fallback to default if new enum not mapped)
            style = VISUAL_STYLES.get(r_type, VISUAL_STYLES["default"])
            
            formatted.append({
                "source": str(r.from_entity_id),
                "target": str(r.to_entity_id),
                "type": r_type,
                # Injected Visual Attributes
                "color": style["color"],
                "strokeWidth": style["width"],
                "strokeDasharray": style["dash"],
                "label": r.description or r_type.title() # Tooltip text
            })
            
        return formatted

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
