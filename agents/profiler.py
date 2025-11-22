from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger
from .schema import EntityType, RelationType, Entity
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
        
        # SQL query with recursive CTE to traverse family relationships
        query = text("""
            WITH RECURSIVE family_tree AS (
                -- Base case: Start with target character
                SELECT 
                    e.id,
                    e.name,
                    e.type,
                    0 as generation,
                    ARRAY[e.id] as path,
                    '' as relationship_to_root
                FROM entities e
                WHERE e.id = :character_id
                
                UNION ALL
                
                -- Recursive case: Get blood relatives
                SELECT 
                    e.id,
                    e.name,
                    e.type,
                    ft.generation + COALESCE((r.relationship_metadata->>'generation_level')::int, 0),
                    ft.path || e.id,
                    COALESCE(r.rel_type::text, 'related')
                FROM family_tree ft
                JOIN relationships r ON (
                    r.from_entity_id = ft.id OR r.to_entity_id = ft.id
                )
                JOIN entities e ON (
                    e.id = CASE 
                        WHEN r.from_entity_id = ft.id THEN r.to_entity_id
                        ELSE r.from_entity_id
                    END
                )
                WHERE 
                    e.id != ALL(ft.path)  -- Prevent cycles
                    AND COALESCE((r.relationship_metadata->>'is_blood_relative')::boolean, false) = true
            )
            SELECT DISTINCT ON (id)
                id, name, type, generation, relationship_to_root
            FROM family_tree
            ORDER BY id, generation, name;
        """)
        
        with Session(engine) as session:
            # Execute query
            result = session.execute(
                query,
                {"character_id": str(character_id)}
            )
            rows = result.fetchall()
            
            if not rows:
                return {
                    "root_character_id": str(character_id),
                    "family_members": [],
                    "total_members": 0,
                    "message": "No family members found or character does not exist"
                }
            
            # Build hierarchical structure
            family_members = []
            generations = {}
            
            for row in rows:
                member = {
                    "id": str(row.id),
                    "name": row.name,
                    "type": row.type,
                    "generation": row.generation,
                    "relationship": row.relationship_to_root
                }
                family_members.append(member)
                
                # Group by generation for easier visualization
                gen = row.generation
                if gen not in generations:
                    generations[gen] = []
                generations[gen].append(member)
            
            return {
                "root_character_id": str(character_id),
                "family_members": family_members,
                "generations": generations,
                "total_members": len(family_members),
                "generation_range": {
                    "min": min(generations.keys()) if generations else 0,
                    "max": max(generations.keys()) if generations else 0
                }
            }

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