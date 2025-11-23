from uuid import UUID
from sqlmodel import Field

from .base import UUIDMixin
from .world import Entity # Locations are Entities
from .library import Scene

class TimelineEvent(UUIDMixin, table=True):
    """Chronologist Output"""
    __tablename__ = "timeline_events"
    date_str: str # "Year 302, 4th Moon"
    absolute_timestamp: int # Internal sorting
    scene_id: UUID = Field(foreign_key="scenes.id")

class TravelRoute(UUIDMixin, table=True):
    """Navigator Output"""
    __tablename__ = "travel_routes"
    origin_id: UUID = Field(foreign_key="entities.id")
    destination_id: UUID = Field(foreign_key="entities.id")
    distance_km: float
    travel_time_days: float
    method: str # "Horseback", "Dragon", "Ship"
