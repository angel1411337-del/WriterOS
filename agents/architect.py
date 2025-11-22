# agents/architect.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .base import BaseAgent, logger

class ArchitectAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)

    async def critique_draft(self, draft_text: str, context: str) -> str:
        """
        Analyzes a draft chapter for structure, pacing, and continuity.
        """
        logger.info("📐 Architect analyzing draft structure...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Lead Editor of a high-end publishing house.
            Your goal is to critique the user's draft based on narrative structure and established Story Bible context.

            ### YOUR FOCUS:
            1. **Continuity**: Does this contradict the provided "WORLD CONTEXT"?
            2. **Pacing**: Is the scene moving too fast or too slow?
            3. **Structure**: Does the scene have a beginning, middle, and end?
            4. **Show, Don't Tell**: Flag exposition dumps.

            ### OUTPUT FORMAT:
            Use Markdown. Be concise. Group issues by category.
            If the draft is good, say so, but still offer one area for refinement.
            """),
            ("user", """
            --- WORLD CONTEXT (The Truth) ---
            {context}
            
            --- USER DRAFT ---
            {draft}
            """)
        ])

        chain = prompt | self.llm | StrOutputParser()

        return await chain.ainvoke({
            "context": context,
            "draft": draft_text
        })