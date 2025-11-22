from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger


class TimelineEvent(BaseModel):
    order: int = Field(..., description="Sequential order within the narrative")
    timestamp: Optional[str] = Field(None, description="Explicit time or date if stated")
    title: str = Field(..., description="Short name for the beat or event")
    summary: str = Field(..., description="One sentence describing what happens")
    impact: Optional[str] = Field(None, description="How this event changes stakes or characters")


class TimelineExtraction(BaseModel):
    events: List[TimelineEvent] = Field(default_factory=list)
    continuity_notes: Optional[str] = Field(
        None,
        description="Any detected continuity risks (sequence conflicts, missing transitions)",
    )


class ChronologistAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.extractor = self.llm.with_structured_output(TimelineExtraction)

    async def run(self, full_text: str, existing_notes: str, title: str):
        """Extract a concise chronology to feed the larger swarm."""
        logger.info(f"⏳ Chronologist sequencing events in: {title}...")

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are the Chronicle Keeper.
Identify the chronological sequence of events so other agents can maintain continuity.

Rules:
1) List events in narrative order (not importance).
2) Capture explicit time markers when they exist.
3) Flag continuity risks (time jumps, missing transitions, conflicting timestamps).
""",
            ),
            (
                "user",
                """
Existing timeline notes:
{existing_notes}

Text to analyze:
{full_text}
""",
            ),
        ])

        chain = prompt | self.extractor
        return await chain.ainvoke({})
