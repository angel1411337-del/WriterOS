"""
Agent Execution Tracking Schema

Provides detailed logging and tracking for agent lifecycle:
- Which agents fire
- What inputs they receive
- LLM request/response details
- Execution success/failure
- Data flow through the system

This enables comprehensive debugging and monitoring of the agent system.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum
from sqlmodel import Field, Relationship
from sqlalchemy import Column, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import UUIDMixin, TimestampMixin


class ExecutionStatus(str, Enum):
    """Agent execution lifecycle states"""
    PENDING = "pending"           # Agent selected but not started
    RUNNING = "running"           # Agent is executing
    LLM_REQUEST = "llm_request"   # Sending request to LLM
    LLM_RESPONSE = "llm_response" # Received LLM response
    SUCCESS = "success"           # Completed successfully
    FAILED = "failed"             # Execution failed
    TIMEOUT = "timeout"           # Execution timed out
    SKIPPED = "skipped"           # Agent decided not to respond


class ExecutionStage(str, Enum):
    """Granular execution stages for debugging"""
    INIT = "init"                        # Agent initialization
    SHOULD_RESPOND = "should_respond"    # Checking relevance
    PRE_PROCESS = "pre_process"          # Input preprocessing
    LLM_PREPARE = "llm_prepare"          # Preparing LLM request
    LLM_CALL = "llm_call"                # Making LLM call
    LLM_PARSE = "llm_parse"              # Parsing LLM response
    POST_PROCESS = "post_process"        # Output postprocessing
    COMPLETE = "complete"                # Finished


class AgentExecution(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks individual agent execution instances.

    Records the complete lifecycle of an agent invocation from
    initial selection through final response delivery.
    """
    __tablename__ = "agent_executions"

    # Context
    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    conversation_id: Optional[UUID] = Field(default=None, foreign_key="conversations.id", index=True)
    user_id: Optional[str] = Field(default=None, index=True)

    # Agent Identity
    agent_name: str = Field(index=True)  # "PsychologistAgent", "ArchitectAgent", etc.
    agent_method: Optional[str] = None   # "run", "analyze_character", etc.

    # Execution Tracking
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING, index=True)
    current_stage: ExecutionStage = Field(default=ExecutionStage.INIT)

    # Input/Output
    input_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    output_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))

    # LLM Tracking
    llm_model: Optional[str] = None       # "gpt-5.1", "claude-sonnet-3.5", etc.
    llm_request: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    llm_response: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    llm_tokens_used: Optional[int] = None
    llm_latency_ms: Optional[float] = None

    # LLM Response Quality Validation
    response_valid: Optional[bool] = None  # Was response parseable/valid?
    response_quality_score: Optional[float] = None  # 0.0-1.0 quality score
    response_validation_errors: Optional[List[str]] = Field(default=None, sa_column=Column(JSONB))
    response_warnings: Optional[List[str]] = Field(default=None, sa_column=Column(JSONB))
    response_metrics: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    # Can include: hallucination_check, coherence_score, completeness, etc.

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

    # Error Handling
    error_type: Optional[str] = None      # Exception class name
    error_message: Optional[str] = None
    error_traceback: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Relevance (from should_respond)
    relevance_score: Optional[float] = None
    relevance_reasoning: Optional[str] = None

    # Execution Metadata (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    # Can include: retry_count, parent_execution_id, etc.


class AgentExecutionLog(UUIDMixin, table=True):
    """
    Granular stage-by-stage logs within an agent execution.

    Tracks each step of the agent lifecycle with timing and data flow.
    Enables pinpointing exactly where issues occur.
    """
    __tablename__ = "agent_execution_logs"

    execution_id: UUID = Field(foreign_key="agent_executions.id", index=True)

    # Stage Info
    stage: ExecutionStage = Field(index=True)
    stage_status: str = Field(default="started")  # "started", "completed", "failed"

    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    duration_ms: Optional[float] = None

    # Data
    log_level: str = Field(default="info")  # "debug", "info", "warning", "error"
    message: str
    data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Context
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


class AgentCallChain(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks chains of agent calls (when one agent calls another).

    Enables tracing data flow through multiple agents and understanding
    the execution graph for complex queries.
    """
    __tablename__ = "agent_call_chains"

    vault_id: UUID = Field(index=True, foreign_key="vaults.id")
    conversation_id: Optional[UUID] = Field(default=None, foreign_key="conversations.id")

    # Chain Structure
    root_execution_id: UUID = Field(foreign_key="agent_executions.id", index=True)
    parent_execution_id: Optional[UUID] = Field(default=None, foreign_key="agent_executions.id")
    child_execution_id: UUID = Field(foreign_key="agent_executions.id", index=True)

    # Call Info
    call_reason: Optional[str] = None  # Why was the child agent called?
    data_passed: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Timing
    depth: int = Field(default=0)  # How deep in the call chain
    sequence: int = Field(default=0)  # Order within siblings


class AgentPerformanceMetrics(UUIDMixin, TimestampMixin, table=True):
    """
    Aggregated performance metrics for agents.

    Used for monitoring, alerting, and optimization.
    Updated periodically (e.g., every hour or on-demand).
    """
    __tablename__ = "agent_performance_metrics"

    agent_name: str = Field(index=True)
    time_window_start: datetime = Field(index=True)
    time_window_end: datetime

    # Execution Stats
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    timeout_executions: int = 0
    skipped_executions: int = 0

    # Performance
    avg_duration_ms: Optional[float] = None
    p50_duration_ms: Optional[float] = None
    p95_duration_ms: Optional[float] = None
    p99_duration_ms: Optional[float] = None

    # LLM Usage
    total_llm_calls: int = 0
    total_tokens_used: int = 0
    avg_llm_latency_ms: Optional[float] = None

    # Error Patterns
    common_errors: List[str] = Field(default_factory=list, sa_column=Column(JSONB))
    error_rate: Optional[float] = None  # failed / total

    # Metadata
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))


class AgentCitation(UUIDMixin, TimestampMixin, table=True):
    """
    Tracks specific data chunks cited by an agent execution.
    Enables traceability of where information came from.
    """
    __tablename__ = "agent_citations"

    execution_id: UUID = Field(foreign_key="agent_executions.id", index=True)
    
    # The Source
    source_id: UUID = Field(index=True) # ID of Document, Fact, or Event
    source_type: str = Field(index=True) # "document", "fact", "event"
    
    # The Proof
    quote: str
    relevance_score: float = 1.0
    
    # Context
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
