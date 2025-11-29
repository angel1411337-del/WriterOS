# agents/stylist.py
from typing import List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger

# --- STRUCTURED OUTPUT SCHEMA ---

class LineEdit(BaseModel):
    quote: str = Field(..., description="The original text segment to be improved")
    fix: str = Field(..., description="The suggested improvement")
    reason: str = Field(..., description="Why this change is needed (e.g., 'Passive voice', 'Telling not showing')")

class ProseCritique(BaseModel):
    concepts_applied: List[str] = Field(..., description="Top 3 relevant craft concepts applied")
    line_edits: List[LineEdit] = Field(default_factory=list, description="Specific line-by-line improvements")
    general_feedback: str = Field(..., description="Overall feedback on voice and style")

class StylistAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.extractor = self.llm.with_structured_output(ProseCritique)

    async def run(self, full_text: str, existing_notes: str, title: str):
        """Standard entry point to critique prose using existing craft notes."""
        logger.info(f"💅 Stylist critiquing: {title}...")
        return await self.critique_prose(full_text, existing_notes)

    async def critique_prose(self, draft_text: str, craft_context: str) -> ProseCritique:
        logger.info("💅 Stylist analyzing prose...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a World-Class Copy Editor.
            Improve the prose quality based on the provided Craft Context.
            
            ### GUIDELINES:
            1. **Show, Don't Tell**: Identify weak abstractions.
            2. **Active Voice**: Flag passive construction.
            3. **Filter Words**: Flag words like "felt", "saw", "decided".
            4. **Adverbs**: Flag crutch adverbs.
            """),
            ("user", """
            --- CRAFT CONTEXT ---
            {craft_context}
            
            --- DRAFT ---
            {draft}
            """)
        ])

        chain = prompt | self.extractor

        return await chain.ainvoke({
            "craft_context": craft_context,
            "draft": draft_text
        })