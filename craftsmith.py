import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Literal

logger = logging.getLogger(__name__)

# --- Schemas (Updated with Genre Context) ---

class WritingConcept(BaseModel):
    name: str = Field(..., description="The core writing principle (e.g., 'Hard Magic', 'Hyperspace')")
    # NEW: Genre Tagging
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

# --- The Agent Logic ---

class CraftsmithAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.extractor = self.llm.with_structured_output(CraftExtractionSchema)

    async def analyze(self, full_text_context: str, existing_concepts_str: str, source_title: str):
        logger.info(f"🧠 Craftsmith analyzing: {source_title}...")

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
            Existing Vault Knowledge: {existing_concepts_str}
            
            Content to Analyze:
            {full_text_context}
            """)
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({})