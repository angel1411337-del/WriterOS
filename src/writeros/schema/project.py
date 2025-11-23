from datetime import datetime
from .base import UUIDMixin

class Sprint(UUIDMixin, table=True):
    __tablename__ = "sprints"
    name: str
    start_date: datetime
    end_date: datetime
    goal_word_count: int
    current_word_count: int
    status: str # "Active", "Completed"
