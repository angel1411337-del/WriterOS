from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger
from .schema import EntityType, RelationType

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
    def __init__(self, model_name="gpt-4o"):
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