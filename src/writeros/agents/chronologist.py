from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .base import BaseAgent, logger
from sqlmodel import Session, select
from writeros.utils.db import engine
from writeros.schema import Event


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
        return await chain.ainvoke({
            "existing_notes": existing_notes,
            "full_text": full_text
        })

    async def get_event_sequence(self, vault_id: UUID, max_depth: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieves events in chronological order based on sequence_order or story_time.
        
        Args:
            vault_id: The vault to query.
            max_depth: Limit the number of events returned (acts as a 'page size' for the graph).
            
        Returns:
            List of events sorted chronologically.
        """
        self.log.info("getting_event_sequence", vault_id=str(vault_id), limit=max_depth)
        
        with Session(engine) as session:
            # Fetch events sorted by sequence_order
            # In a real graph traversal, we might follow 'next_event_id' pointers,
            # but here we use the indexed sequence_order field which represents the linear graph.
            statement = select(Event).where(
                Event.vault_id == vault_id
            ).order_by(
                Event.sequence_order.asc().nulls_last(),
                Event.story_time.asc().nulls_last()  # Fallback to story time
            ).limit(max_depth)
            
            events = session.exec(statement).all()
            
            return [
                {
                    "id": str(e.id),
                    "name": e.name,
                    "sequence": e.sequence_order,
                    "story_time": e.story_time,
                    "description": e.description[:100] + "..." if e.description else ""
                }
                for e in events
            ]
