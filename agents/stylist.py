# agents/stylist.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .base import BaseAgent, logger

class StylistAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)

    async def run(self, full_text: str, existing_notes: str, title: str):
        """Standard entry point to critique prose using existing craft notes."""
        logger.info(f"💅 Stylist critiquing: {title}...")
        return await self.critique_prose(full_text, existing_notes)

    async def critique_prose(self, draft_text: str, craft_context: str) -> str:
        logger.info("💅 Stylist analyzing prose...")

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a World-Class Copy Editor.
            Improve the prose quality based on the provided Craft Context.
            
            ### GUIDELINES:
            1. **Show, Don't Tell**: Identify weak abstractions.
            2. **Active Voice**: Flag passive construction.
            3. **Filter Words**: Flag words like "felt", "saw", "decided".
            4. **Adverbs**: Flag crutch adverbs.

            ### OUTPUT FORMAT (Markdown):
            
            **Concepts Applied:** [List only the top 3 most relevant concepts from the context that apply to this specific text. If none apply, say "Standard Style Rules".]
            
            **Line-by-Line Suggestions:**
            [Quote the bad line] -> [Suggest the fix]
            
            **General Feedback:**
            [Short paragraph on voice]
            """),
            ("user", """
            --- CRAFT CONTEXT ---
            {craft_context}
            
            --- DRAFT ---
            {draft}
            """)
        ])

        chain = prompt | self.llm | StrOutputParser()

        return await chain.ainvoke({
            "craft_context": craft_context,
            "draft": draft_text
        })