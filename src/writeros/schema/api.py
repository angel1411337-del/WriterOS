from pydantic import BaseModel
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlmodel import Field
from .enums import AgentType

class ChatRequest(BaseModel):
    message: str
    agent: AgentType
    vault_id: UUID
    context_files: List[str] = [] # List of file paths or Entity IDs
    stream: bool = True

class ChatResponse(BaseModel):
    content: str
    agent_used: str
    sources: List[Dict[str, Any]] = [] # Citations used
    processing_time: float

class ValidationReport(BaseModel):
    """Response format for /analyze endpoints"""
    agent: str
    score: int
    issues: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
