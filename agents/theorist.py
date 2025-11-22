from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Literal
from .base import BaseAgent, logger

# --- Schemas (Updated with Genre Context) ---

class WritingConcept(BaseModel):
    name: str = Field(..., description="The core writing principle (e.g., 'Hard Magic', 'Hyperspace')")
    genre_context: Literal["General", "Sci-Fi", "Fantasy"] = Field(..., description="Is this specific to SF/Fantasy or applicable to all writing?")
    definition: str = Field(..., description="A clear definition of the concept")
    why_it_matters: str = Field(..., description="Why a writer should care about this")
    examples_mentioned: List[str] = Field(default_factory=list, description="Stories used as examples")

class ActionableTechnique(BaseModel):
    name: str = Field(..., description="Name of the technique")
    genre_context: Literal["General", "Sci-Fi", "Fantasy"] = Field(..., description="Is this specific to SF/Fantasy or applicable to all writing?")
    steps: List[str] = Field(..., description="Step-by-step instructions")
    when_to_use: str = Field(..., description="Context on when to use this")

class WritingPitfall(BaseModel):
    name: str = Field(..., description="Common mistake")
    genre_context: Literal["General", "Sci-Fi", "Fantasy"] = Field(..., description="Is this specific to SF/Fantasy or applicable to all writing?")
    why_it_fails: str = Field(..., description="Why this ruins a story")
    fix_strategy: str = Field(..., description="How to fix or avoid it")

class CraftExtractionSchema(BaseModel):
    concepts: List[WritingConcept] = Field(default_factory=list)
    techniques: List[ActionableTechnique] = Field(default_factory=list)
    pitfalls: List[WritingPitfall] = Field(default_factory=list)

# --- The Agent ---

class TheoristAgent(BaseAgent):
    def __init__(self, model_name="gpt-4o"):
        super().__init__(model_name)
        # We map the schema here
        self.extractor = self.llm.with_structured_output(CraftExtractionSchema)

    async def run(self, full_text: str, existing_notes: str, title: str):
        logger.info(f"🧠 Theorist analyzing craft: {title}...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Master Speculative Fiction Writing Coach.
            Your goal is to extract writing advice and categorize it by Genre (Sci-Fi vs Fantasy vs General).
            
            CRITICAL INSTRUCTIONS:
            1. **Categorization is Key**: 
               - If advice applies to ANY story (e.g. "Pacing", "Dialogue"), label it "General".
               - If advice is specific to technology, aliens, or future society, label it "Sci-Fi".
               - If advice is specific to magic, myths, or medieval settings, label it "Fantasy".
            2. IGNORE specific plot details unless used as an EXAMPLE.
            3. EXTRACT the underlying PRINCIPLE.
            """),
            ("user", f"""
            Existing Vault Knowledge: {existing_notes}
            
            Content to Analyze:
            {full_text}
            """)
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({})