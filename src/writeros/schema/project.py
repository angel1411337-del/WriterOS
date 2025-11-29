from datetime import datetime
from uuid import UUID
from sqlmodel import Field
from .base import UUIDMixin, TimestampMixin

class Sprint(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "sprints"
    vault_id: UUID = Field(index=True)

    name: str
    start_date: datetime
    end_date: datetime
    goal_word_count: int
    current_word_count: int
    status: str  # "Active", "Completed"
