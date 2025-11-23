from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger

# --- EXTRACTOR SCHEMAS ---

class Connection(BaseModel):
    target_location: str = Field(..., description="Name of the connected place")
    travel_time: str = Field(..., description="Time to travel (e.g., '3 days', '2 weeks')")
    distance: Optional[str] = Field(None, description="Physical distance if mentioned (e.g., '500 miles')")
    travel_method: str = Field(..., description="How to get there (Horse, Ship, Walking, Portal)")

    # ✅ NEW: Captured for Drift/Strategic Context
    context: Optional[str] = Field(
        None,
        description="Why this route exists or its nature (e.g. 'Trade route', 'Smugglers path', 'Dangerous military road')"
    )

class LocationExtraction(BaseModel):
    name: str = Field(..., description="Name of the location (City, Region, Planet)")
    region: str = Field(..., description="Broader region it belongs to (e.g. 'The North', 'Outer Rim')")
    description: str = Field(..., description="Visual/Atmospheric description")
    connections: List[Connection] = Field(default_factory=list, description="Routes to other places")

class NavigationSchema(BaseModel):
    locations: List[LocationExtraction] = Field(default_factory=list)

# --- THE AGENT ---

class NavigatorAgent(BaseAgent):
    # ✅ UPDATED: Use gpt-5.1 for superior spatial reasoning
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.extractor = self.llm.with_structured_output(NavigationSchema)

    async def run(self, full_text: str, existing_notes: str, title: str):
        logger.info(f"🗺️ Navigator mapping geography in: {title}...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Royal Cartographer.
            Your job is to extract geographical data to build a Master Map.
            
            ### RULES:
            1. **Identify Locations:** Extract cities, landmarks, and regions.
            2. **Map Connections:** Extract travel times and methods.
            3. **Context (Critical):** If a route is dangerous, secret, or heavily traveled, note that in the context.
            4. **Ignore:** Temporary locations like "a random tavern" unless named.
            """),
            ("user", f"""
            Existing Map Context: {existing_notes}
            
            Transcript to Analyze:
            {full_text}
            """)
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({})