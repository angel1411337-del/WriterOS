from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger

# --- EXTRACTION SCHEMAS ---

class Rule(BaseModel):
    name: str = Field(..., description="Name of the rule (e.g. 'Conservation of Mana')")
    description: str = Field(..., description="How it works")
    consequence: Optional[str] = Field(None, description="What happens if broken?")
    hardness: Literal["Hard", "Soft", "Hybrid"] = "Hard"

class Ability(BaseModel):
    name: str = Field(..., description="Name of the specific power/tech (e.g. 'Fireball')")
    cost: str = Field(..., description="Cost to use (e.g. '5 body temp', '1 uranium pellet')")
    limitations: str = Field(..., description="Range, duration, cooldown")

    # ✅ RESTORED: The explicit instruction helps the AI map the graph correctly
    prerequisites: Optional[str] = Field(
        None,
        description="Exact name of an ability required to use this one. If text says 'Must master X first', put 'X' here."
    )

class SystemProfile(BaseModel):
    name: str = Field(..., description="Name of the System (e.g. 'Allomancy')")
    type: Literal["Magic", "Technology", "Biology", "Economy"]
    origin: str = Field(..., description="Source (e.g. 'The Sun', 'Ancient Tech')")
    rules: List[Rule] = Field(default_factory=list)
    abilities: List[Ability] = Field(default_factory=list)

class MechanicExtraction(BaseModel):
    systems: List[SystemProfile] = Field(default_factory=list)

# --- THE AGENT ---

class MechanicAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.extractor = self.llm.with_structured_output(MechanicExtraction)

    async def run(self, full_text: str, existing_notes: str, title: str):
        logger.info(f"⚙️ Mechanic extracting systems from: {title}...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Lead Systems Designer.
            Extract Hard Rules for Magic, Technology, or Economy.
            
            ### CRITICAL INSTRUCTION: TECH TREES
            You must identify **Dependencies**.
            - If the text says "To use A, you must know B", then Ability A has `prerequisites="B"`.
            - If the text says "Class 2 requires Class 1", then Class 2 has `prerequisites="Class 1"`.
            - **Exact Matching:** Ensure the prerequisite name matches the Ability name exactly.
            
            ### RULES:
            1. **Identify Costs:** Magic must have a cost. Tech must have limits.
            2. **Hardness:** Is this a Hard Rule (Physics) or Soft Rule (Vibes)?
            """),
            ("user", f"""
            Existing Systems: {existing_notes}
            
            Transcript:
            {full_text}
            """)
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({})