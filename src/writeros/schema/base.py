from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
from sqlmodel import SQLModel, Field

class UUIDMixin(SQLModel):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)

class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CanonInfo(SQLModel):
    """Non-table model for consistent JSON structure"""
    layer: str = "primary"
    status: str = "active"
