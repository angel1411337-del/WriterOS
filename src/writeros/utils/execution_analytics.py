"""
Execution Analytics Utilities

Provides tools for querying and analyzing agent execution data.
Helps debug issues like:
- Which agents didn't fire and why
- Where execution failed
- Performance bottlenecks
- LLM request/response details
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlmodel import Session, select, func, and_, or_
from sqlalchemy import desc

from writeros.utils.db import engine
from writeros.schema.agent_execution import (
    AgentExecution,
    AgentExecutionLog,
    AgentCallChain,
    AgentPerformanceMetrics,
    AgentCitation,
    ExecutionStatus,
    ExecutionStage
)
from writeros.core.logging import get_logger

logger = get_logger(__name__)


class ExecutionAnalytics:
    """Query and analyze agent execution data"""

    @staticmethod
    def get_execution(execution_id: UUID) -> Optional[AgentExecution]:
        """Get a single execution by ID"""
        with Session(engine) as session:
            return session.get(AgentExecution, execution_id)

    @staticmethod
    def get_execution_with_logs(execution_id: UUID) -> Dict[str, Any]:
        """
        Get execution with all associated logs.

        Returns:
            {
                "execution": AgentExecution,
                "logs": List[AgentExecutionLog],
                "call_chain": Optional[AgentCallChain]
            }
        """
        with Session(engine) as session:
            execution = session.get(AgentExecution, execution_id)
            if not execution:
                return {"error": "Execution not found"}

            logs = session.exec(
                select(AgentExecutionLog)
                .where(AgentExecutionLog.execution_id == execution_id)
                .order_by(AgentExecutionLog.timestamp)
            ).all()

            call_chain = session.exec(
                select(AgentCallChain)
                .where(AgentCallChain.child_execution_id == execution_id)
            ).first()

            return {
                "execution": execution,
                "logs": list(logs),
                "call_chain": call_chain
            }

    @staticmethod
    def get_recent_executions(
        vault_id: Optional[UUID] = None,
        agent_name: Optional[str] = None,
        status: Optional[ExecutionStatus] = None,
        limit: int = 50
    ) -> List[AgentExecution]:
        """
        Get recent executions with optional filtering.

        Args:
            vault_id: Filter by vault
            agent_name: Filter by agent (e.g., "PsychologistAgent")
            status: Filter by status
            limit: Max results

        Returns:
            List of executions, newest first
        """
        with Session(engine) as session:
            query = select(AgentExecution)

            filters = []
            if vault_id:
                filters.append(AgentExecution.vault_id == vault_id)
            if agent_name:
                filters.append(AgentExecution.agent_name == agent_name)
            if status:
                filters.append(AgentExecution.status == status)

            if filters:
                query = query.where(and_(*filters))

            query = query.order_by(desc(AgentExecution.created_at)).limit(limit)

            return list(session.exec(query).all())

    @staticmethod
    def get_failed_executions(
        vault_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[AgentExecution]:
        """
        Get failed executions in the last N hours.

        Useful for debugging recent issues.
        """
        with Session(engine) as session:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = select(AgentExecution).where(
                and_(
                    AgentExecution.status == ExecutionStatus.FAILED,
                    AgentExecution.created_at >= cutoff
                )
            )

            if vault_id:
                query = query.where(AgentExecution.vault_id == vault_id)

            query = query.order_by(desc(AgentExecution.created_at)).limit(limit)

            return list(session.exec(query).all())

    @staticmethod
    def get_skipped_executions(
        vault_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get skipped executions (agents that decided not to respond).

        Returns executions with relevance reasoning.
        """
        with Session(engine) as session:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = select(AgentExecution).where(
                and_(
                    AgentExecution.status == ExecutionStatus.SKIPPED,
                    AgentExecution.created_at >= cutoff
                )
            )

            if vault_id:
                query = query.where(AgentExecution.vault_id == vault_id)

            query = query.order_by(desc(AgentExecution.created_at)).limit(limit)

            executions = session.exec(query).all()

            return [
                {
                    "execution_id": str(ex.id),
                    "agent_name": ex.agent_name,
                    "relevance_score": ex.relevance_score,
                    "relevance_reasoning": ex.relevance_reasoning,
                    "input_data": ex.input_data,
                    "created_at": ex.created_at
                }
                for ex in executions
            ]

    @staticmethod
    def get_execution_call_chain(execution_id: UUID) -> List[Dict[str, Any]]:
        """
        Get the full call chain for an execution.

        Shows parent and child agent calls.
        """
        with Session(engine) as session:
            # Find root
            chain_link = session.exec(
                select(AgentCallChain)
                .where(AgentCallChain.child_execution_id == execution_id)
            ).first()

            if not chain_link:
                # This is a root execution, find children
                root_id = execution_id
            else:
                root_id = chain_link.root_execution_id

            # Get all links in this chain
            all_links = session.exec(
                select(AgentCallChain)
                .where(AgentCallChain.root_execution_id == root_id)
                .order_by(AgentCallChain.depth, AgentCallChain.sequence)
            ).all()

            # Build chain structure
            chain = []
            for link in all_links:
                parent_exec = session.get(AgentExecution, link.parent_execution_id) if link.parent_execution_id else None
                child_exec = session.get(AgentExecution, link.child_execution_id)

                chain.append({
                    "depth": link.depth,
                    "sequence": link.sequence,
                    "parent_agent": parent_exec.agent_name if parent_exec else None,
                    "child_agent": child_exec.agent_name if child_exec else None,
                    "child_execution_id": str(child_exec.id) if child_exec else None,
                    "call_reason": link.call_reason,
                    "status": child_exec.status if child_exec else None
                })

            return chain

    @staticmethod
    def get_llm_interactions(
        execution_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed LLM request/response for debugging.

        Returns:
            {
                "model": "gpt-5.1",
                "request": {...},
                "response": {...},
                "tokens_used": 1234,
                "latency_ms": 2300
            }
        """
        with Session(engine) as session:
            execution = session.get(AgentExecution, execution_id)
            if not execution:
                return None

            return {
                "model": execution.llm_model,
                "request": execution.llm_request,
                "response": execution.llm_response,
                "tokens_used": execution.llm_tokens_used,
                "latency_ms": execution.llm_latency_ms
            }

    @staticmethod
    def analyze_agent_performance(
        agent_name: str,
        vault_id: Optional[UUID] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze performance metrics for a specific agent.

        Returns:
            {
                "total_executions": 100,
                "success_rate": 0.95,
                "avg_duration_ms": 2300,
                "common_errors": ["ValueError", "TimeoutError"],
                "llm_stats": {...}
            }
        """
        with Session(engine) as session:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = select(AgentExecution).where(
                and_(
                    AgentExecution.agent_name == agent_name,
                    AgentExecution.created_at >= cutoff
                )
            )

            if vault_id:
                query = query.where(AgentExecution.vault_id == vault_id)

            executions = session.exec(query).all()

            if not executions:
                return {"error": "No executions found"}

            total = len(executions)
            successful = sum(1 for ex in executions if ex.status == ExecutionStatus.SUCCESS)
            failed = sum(1 for ex in executions if ex.status == ExecutionStatus.FAILED)
            skipped = sum(1 for ex in executions if ex.status == ExecutionStatus.SKIPPED)

            durations = [ex.duration_ms for ex in executions if ex.duration_ms is not None]
            avg_duration = sum(durations) / len(durations) if durations else None

            # Error analysis
            error_types = [ex.error_type for ex in executions if ex.error_type]
            from collections import Counter
            error_counts = Counter(error_types)

            # LLM stats
            llm_calls = [ex for ex in executions if ex.llm_request is not None]
            total_tokens = sum(ex.llm_tokens_used or 0 for ex in llm_calls)
            avg_llm_latency = sum(ex.llm_latency_ms or 0 for ex in llm_calls) / len(llm_calls) if llm_calls else None

            return {
                "agent_name": agent_name,
                "time_window_hours": hours,
                "total_executions": total,
                "successful": successful,
                "failed": failed,
                "skipped": skipped,
                "success_rate": successful / total if total > 0 else 0,
                "avg_duration_ms": avg_duration,
                "llm_stats": {
                    "total_calls": len(llm_calls),
                    "total_tokens": total_tokens,
                    "avg_tokens_per_call": total_tokens / len(llm_calls) if llm_calls else 0,
                    "avg_latency_ms": avg_llm_latency
                },
                "common_errors": [
                    {"error_type": error, "count": count}
                    for error, count in error_counts.most_common(5)
                ]
            }

    @staticmethod
    def get_stage_timeline(execution_id: UUID) -> List[Dict[str, Any]]:
        """
        Get timeline of stages for an execution.

        Useful for visualizing execution flow and finding bottlenecks.
        """
        with Session(engine) as session:
            logs = session.exec(
                select(AgentExecutionLog)
                .where(AgentExecutionLog.execution_id == execution_id)
                .order_by(AgentExecutionLog.timestamp)
            ).all()

            timeline = []
            for log in logs:
                timeline.append({
                    "timestamp": log.timestamp.isoformat(),
                    "stage": log.stage.value,
                    "status": log.stage_status,
                    "duration_ms": log.duration_ms,
                    "message": log.message,
                    "level": log.log_level,
                    "data": log.data
                })

            return timeline

    @staticmethod
    def find_slow_executions(
        threshold_ms: float = 5000,
        vault_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find executions that took longer than threshold.

        Useful for performance optimization.
        """
        with Session(engine) as session:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = select(AgentExecution).where(
                and_(
                    AgentExecution.duration_ms >= threshold_ms,
                    AgentExecution.created_at >= cutoff
                )
            )

            if vault_id:
                query = query.where(AgentExecution.vault_id == vault_id)

            query = query.order_by(desc(AgentExecution.duration_ms)).limit(limit)

            executions = session.exec(query).all()

            return [
                {
                    "execution_id": str(ex.id),
                    "agent_name": ex.agent_name,
                    "method": ex.agent_method,
                    "duration_ms": ex.duration_ms,
                    "llm_latency_ms": ex.llm_latency_ms,
                    "status": ex.status.value,
                    "created_at": ex.created_at
                }
                for ex in executions
            ]

    @staticmethod
    def debug_why_agent_didnt_fire(
        agent_name: str,
        conversation_id: UUID,
        vault_id: UUID
    ) -> Dict[str, Any]:
        """
        Debug why a specific agent didn't fire in a conversation.

        Checks:
        - Was the agent invoked at all?
        - Did it skip due to relevance?
        - Did it fail during initialization?
        """
        with Session(engine) as session:
            # Check for any executions
            executions = session.exec(
                select(AgentExecution).where(
                    and_(
                        AgentExecution.agent_name == agent_name,
                        AgentExecution.conversation_id == conversation_id,
                        AgentExecution.vault_id == vault_id
                    )
                )
            ).all()

            if not executions:
                return {
                    "status": "never_invoked",
                    "message": f"{agent_name} was never invoked for this conversation",
                    "possible_reasons": [
                        "Orchestrator didn't route to this agent",
                        "Agent not registered in routing logic",
                        "Query didn't match agent's domain"
                    ]
                }

            # Check for skipped
            skipped = [ex for ex in executions if ex.status == ExecutionStatus.SKIPPED]
            if skipped:
                return {
                    "status": "skipped",
                    "message": f"{agent_name} was invoked but skipped due to relevance check",
                    "executions": [
                        {
                            "execution_id": str(ex.id),
                            "relevance_score": ex.relevance_score,
                            "relevance_reasoning": ex.relevance_reasoning,
                            "input_data": ex.input_data
                        }
                        for ex in skipped
                    ]
                }

            # Check for failures
            failed = [ex for ex in executions if ex.status == ExecutionStatus.FAILED]
            if failed:
                return {
                    "status": "failed",
                    "message": f"{agent_name} was invoked but failed",
                    "executions": [
                        {
                            "execution_id": str(ex.id),
                            "error_type": ex.error_type,
                            "error_message": ex.error_message,
                            "current_stage": ex.current_stage.value
                        }
                        for ex in failed
                    ]
                }

            # Agent did fire successfully
            successful = [ex for ex in executions if ex.status == ExecutionStatus.SUCCESS]
            return {
                "status": "fired_successfully",
                "message": f"{agent_name} executed successfully",
                "execution_count": len(successful),
                "executions": [
                    {
                        "execution_id": str(ex.id),
                        "duration_ms": ex.duration_ms,
                        "output_preview": str(ex.output_data)[:200] if ex.output_data else None
                    }
                    for ex in successful
                ]
            }

    @staticmethod
    def get_poor_quality_responses(
        vault_id: Optional[UUID] = None,
        quality_threshold: float = 0.7,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find LLM responses with quality issues.

        Args:
            vault_id: Filter by vault
            quality_threshold: Quality score below this is considered poor (0.0-1.0)
            hours: Time window
            limit: Max results

        Returns:
            List of executions with poor quality responses
        """
        with Session(engine) as session:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = select(AgentExecution).where(
                and_(
                    AgentExecution.response_quality_score.is_not(None),
                    AgentExecution.response_quality_score < quality_threshold,
                    AgentExecution.created_at >= cutoff
                )
            )

            if vault_id:
                query = query.where(AgentExecution.vault_id == vault_id)

            query = query.order_by(AgentExecution.response_quality_score).limit(limit)

            executions = session.exec(query).all()

            return [
                {
                    "execution_id": str(ex.id),
                    "agent_name": ex.agent_name,
                    "quality_score": ex.response_quality_score,
                    "validation_errors": ex.response_validation_errors,
                    "warnings": ex.response_warnings,
                    "metrics": ex.response_metrics,
                    "llm_model": ex.llm_model,
                    "created_at": ex.created_at
                }
                for ex in executions
            ]

    @staticmethod
    def get_invalid_responses(
        vault_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find executions with invalid LLM responses.

        Returns:
            List of executions with response_valid=False
        """
        with Session(engine) as session:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = select(AgentExecution).where(
                and_(
                    AgentExecution.response_valid == False,  # noqa
                    AgentExecution.created_at >= cutoff
                )
            )

            if vault_id:
                query = query.where(AgentExecution.vault_id == vault_id)

            query = query.order_by(desc(AgentExecution.created_at)).limit(limit)

            executions = session.exec(query).all()

            return [
                {
                    "execution_id": str(ex.id),
                    "agent_name": ex.agent_name,
                    "llm_model": ex.llm_model,
                    "validation_errors": ex.response_validation_errors,
                    "warnings": ex.response_warnings,
                    "llm_request": ex.llm_request,
                    "llm_response": ex.llm_response,
                    "created_at": ex.created_at
                }
                for ex in executions
            ]

    @staticmethod
    def analyze_response_quality(
        agent_name: Optional[str] = None,
        vault_id: Optional[UUID] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze LLM response quality across executions.

        Returns:
            {
                "total_responses": int,
                "valid_responses": int,
                "invalid_responses": int,
                "avg_quality_score": float,
                "quality_distribution": {...},
                "common_errors": [...],
                "common_warnings": [...]
            }
        """
        with Session(engine) as session:
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            query = select(AgentExecution).where(
                and_(
                    AgentExecution.llm_response.is_not(None),
                    AgentExecution.created_at >= cutoff
                )
            )

            if agent_name:
                query = query.where(AgentExecution.agent_name == agent_name)

            if vault_id:
                query = query.where(AgentExecution.vault_id == vault_id)

            executions = session.exec(query).all()

            if not executions:
                return {"error": "No executions found with LLM responses"}

            total = len(executions)
            valid = sum(1 for ex in executions if ex.response_valid is True)
            invalid = sum(1 for ex in executions if ex.response_valid is False)

            # Quality scores
            quality_scores = [
                ex.response_quality_score
                for ex in executions
                if ex.response_quality_score is not None
            ]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None

            # Quality distribution
            quality_dist = {
                "excellent (>0.9)": sum(1 for s in quality_scores if s > 0.9),
                "good (0.7-0.9)": sum(1 for s in quality_scores if 0.7 <= s <= 0.9),
                "fair (0.5-0.7)": sum(1 for s in quality_scores if 0.5 <= s < 0.7),
                "poor (<0.5)": sum(1 for s in quality_scores if s < 0.5)
            }

            # Error/warning analysis
            from collections import Counter
            all_errors = []
            all_warnings = []

            for ex in executions:
                if ex.response_validation_errors:
                    all_errors.extend(ex.response_validation_errors)
                if ex.response_warnings:
                    all_warnings.extend(ex.response_warnings)

            error_counts = Counter(all_errors)
            warning_counts = Counter(all_warnings)

            return {
                "total_responses": total,
                "valid_responses": valid,
                "invalid_responses": invalid,
                "validity_rate": valid / total if total > 0 else 0,
                "avg_quality_score": avg_quality,
                "quality_distribution": quality_dist,
                "common_errors": [
                    {"error": error, "count": count}
                    for error, count in error_counts.most_common(10)
                ],
                "common_warnings": [
                    {"warning": warning, "count": count}
                    for warning, count in warning_counts.most_common(10)
                ]
            }

    @staticmethod
    def get_citations_for_execution(execution_id: UUID) -> List[Dict[str, Any]]:
        """
        Get citations for a specific execution.
        """
        with Session(engine) as session:
            citations = session.exec(
                select(AgentCitation)
                .where(AgentCitation.execution_id == execution_id)
            ).all()
            
            return [
                {
                    "source_id": str(c.source_id),
                    "source_type": c.source_type,
                    "quote": c.quote,
                    "relevance_score": c.relevance_score
                }
                for c in citations
            ]

