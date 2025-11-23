from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin

class Conversation(UUIDMixin, TimestampMixin, table=True):
    __tablename__ = "conversations"
    vault_id: UUID = Field(index=True)
    title: str

class Message(UUIDMixin, table=True):
    __tablename__ = "messages"
    conversation_id: UUID = Field(index=True, foreign_key="conversations.id")
    
    role: str  # user, assistant, system
    content: str
    agent: Optional[str] = None  # which agent responded
    
    context_used: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

class InteractionEvent(UUIDMixin, table=True):
    __tablename__ = "interactions"
    user_id: str = Field(index=True)
    vault_id: str = Field(index=True)

    event_type: str = Field(index=True)
    event_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    context: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    timestamp: datetime = Field(default_factory=datetime.utcnow)
