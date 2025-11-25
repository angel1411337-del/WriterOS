from uuid import UUID
from sqlmodel import Field

from .base import UUIDMixin, TimestampMixin

class TimelineEvent(UUIDMixin, TimestampMixin, table=True):
    """Chronologist Output"""
    __tablename__ = "timeline_events"
    vault_id: UUID = Field(index=True)

    date_str: str  # "Year 302, 4th Moon"
    absolute_timestamp: int  # Internal sorting
    scene_id: UUID = Field(foreign_key="scenes.id")

class TravelRoute(UUIDMixin, TimestampMixin, table=True):
    """Navigator Output"""
    __tablename__ = "travel_routes"
    vault_id: UUID = Field(index=True)

    origin_id: UUID = Field(foreign_key="entities.id")
    destination_id: UUID = Field(foreign_key="entities.id")
    distance_km: float
    travel_time_days: float
    method: str  # "Horseback", "Dragon", "Ship"
