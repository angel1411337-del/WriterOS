print("--- LOADING NEW PSYCHOLOGIST V2 AGENT ---") # <--- Verifies file load

from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger

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
        logger.info(f"🧠 Psychologist (V2) analyzing psyche in: {title}...")

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
            ("user", f"""
            Existing Context: {existing_notes}
            
            Transcript/Chapter to Analyze:
            {full_text}
            """)
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({})