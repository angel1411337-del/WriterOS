"""
Agent Execution Tracker

Provides comprehensive tracking and logging for agent executions.
Enables debugging of:
- Which agents fire (or don't fire)
- Why agents were selected/skipped
- LLM request/response flow
- Data transformations through the pipeline
- Performance bottlenecks
- Error propagation

Usage:
    from writeros.utils.agent_tracker import ExecutionTracker

    # In agent code:
    async def run(self, *args, **kwargs):
        tracker = ExecutionTracker(
            agent_name=self.agent_name,
            vault_id=vault_id
        )

        async with tracker.track_execution(method="run", input_data={"args": args}):
            # Agent logic here
            result = await self._do_work()
            tracker.set_output(result)
            return result
"""
import time
import traceback
import asyncio
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from contextlib import asynccontextmanager
from sqlmodel import Session, select

from writeros.utils.db import engine
from writeros.core.logging import get_logger
from writeros.schema.agent_execution import (
    AgentExecution,
    AgentExecutionLog,
    AgentCallChain,
    ExecutionStatus,
    ExecutionStage
)

logger = get_logger(__name__)


class ExecutionTracker:
    """
    Tracks a single agent execution with detailed logging.

    Automatically records:
    - Execution lifecycle (pending -> running -> success/failed)
    - Stage-by-stage progress
    - LLM interactions
    - Timing and performance
    - Errors and stack traces
    """

    def __init__(
        self,
        agent_name: str,
        vault_id: UUID,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[str] = None,
        parent_execution_id: Optional[UUID] = None
    ):
        self.agent_name = agent_name
        self.vault_id = vault_id
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.parent_execution_id = parent_execution_id

        # self.execution removed to avoid detached session issues
        self.execution_id: Optional[UUID] = None
        self.start_time: Optional[float] = None
        self.stage_timers: Dict[ExecutionStage, float] = {}
        
        # Local state cache to avoid accessing detached objects
        self._current_stage: ExecutionStage = ExecutionStage.INIT
        self._input_data: Dict[str, Any] = {}

        self.logger = logger.bind(
            agent=agent_name,
            vault_id=str(vault_id)
        )

    @asynccontextmanager
    async def track_execution(
        self,
        method: str = "run",
        input_data: Optional[Dict[str, Any]] = None
    ):
        """
        Context manager for tracking an agent execution.

        Usage:
            async with tracker.track_execution(method="analyze_character", input_data={...}):
                # Do work
                result = await self.process()
                tracker.set_output(result)
                return result
        """
        # Create execution record
        await self._create_execution(method, input_data or {})

        try:
            # Start tracking
            self.start_time = time.time()
            await self._update_status(ExecutionStatus.RUNNING, ExecutionStage.INIT)
            await self._log_stage(ExecutionStage.INIT, "started", "Agent execution started")

            self.logger.info(
                "agent_execution_started",
                execution_id=str(self.execution_id),
                method=method
            )

            yield self

            # Success
            await self._update_status(ExecutionStatus.SUCCESS, ExecutionStage.COMPLETE)
            await self._log_stage(ExecutionStage.COMPLETE, "completed", "Agent execution completed successfully")

            self.logger.info(
                "agent_execution_completed",
                execution_id=str(self.execution_id),
                duration_ms=self._get_duration_ms()
            )

        except asyncio.TimeoutError as e:
            # Timeout
            await self._handle_error(e, ExecutionStatus.TIMEOUT)
            self.logger.error(
                "agent_execution_timeout",
                execution_id=str(self.execution_id),
                error=str(e)
            )
            raise

        except Exception as e:
            # Failure
            await self._handle_error(e, ExecutionStatus.FAILED)
            self.logger.error(
                "agent_execution_failed",
                execution_id=str(self.execution_id),
                error=str(e),
                error_type=type(e).__name__
            )
            raise

        finally:
            # Finalize execution record
            await self._finalize_execution()

    async def track_stage(self, stage: ExecutionStage, message: str = ""):
        """
        Track entry into a new execution stage.

        Usage:
            await tracker.track_stage(ExecutionStage.LLM_PREPARE, "Preparing LLM request")
        """
        self.stage_timers[stage] = time.time()

        await self._update_stage(stage)
        await self._log_stage(stage, "started", message or f"Entering {stage.value}")

        self.logger.debug(
            "agent_stage_started",
            execution_id=str(self.execution_id),
            stage=stage.value,
            message=message
        )

    async def complete_stage(self, stage: ExecutionStage, data: Optional[Dict[str, Any]] = None):
        """
        Mark a stage as completed.

        Usage:
            await tracker.complete_stage(ExecutionStage.LLM_CALL, {"tokens": 1234})
        """
        duration_ms = None
        if stage in self.stage_timers:
            duration_ms = (time.time() - self.stage_timers[stage]) * 1000

        await self._log_stage(
            stage,
            "completed",
            f"Completed {stage.value}",
            duration_ms=duration_ms,
            data=data or {}
        )

        self.logger.debug(
            "agent_stage_completed",
            execution_id=str(self.execution_id),
            stage=stage.value,
            duration_ms=duration_ms
        )

    async def track_llm_request(
        self,
        model: str,
        request_data: Dict[str, Any]
    ):
        """
        Track LLM request.

        Usage:
            await tracker.track_llm_request(
                model="gpt-5.1",
                request_data={"messages": [...], "temperature": 0.7}
            )
        """
        await self.track_stage(ExecutionStage.LLM_CALL, f"Calling LLM: {model}")

        if self.execution_id:
            with Session(engine) as session:
                execution = session.get(AgentExecution, self.execution_id)
                if execution:
                    execution.llm_model = model
                    execution.llm_request = request_data
                    execution.status = ExecutionStatus.LLM_REQUEST
                    session.add(execution)
                    session.commit()

        self.logger.info(
            "llm_request_sent",
            execution_id=str(self.execution_id),
            model=model,
            message_count=len(request_data.get("messages", []))
        )

    async def track_llm_response(
        self,
        response_data: Dict[str, Any],
        tokens_used: Optional[int] = None,
        latency_ms: Optional[float] = None,
        validate: bool = True
    ):
        """
        Track LLM response with optional quality validation.

        Usage:
            await tracker.track_llm_response(
                response_data={"content": "..."},
                tokens_used=1500,
                latency_ms=2300,
                validate=True  # Enable response validation
            )
        """
        await self.complete_stage(ExecutionStage.LLM_CALL, {
            "tokens": tokens_used,
            "latency_ms": latency_ms
        })

        # Validate response quality if requested
        validation_result = None
        if validate:
            validation_result = await self._validate_llm_response(response_data)

        if self.execution_id:
            with Session(engine) as session:
                execution = session.get(AgentExecution, self.execution_id)
                if execution:
                    execution.llm_response = response_data
                    execution.llm_tokens_used = tokens_used
                    execution.llm_latency_ms = latency_ms
                    execution.status = ExecutionStatus.LLM_RESPONSE

                    # Store validation results
                    if validation_result:
                        execution.response_valid = validation_result['is_valid']
                        execution.response_quality_score = validation_result['quality_score']
                        execution.response_validation_errors = validation_result['errors']
                        execution.response_warnings = validation_result['warnings']
                        execution.response_metrics = validation_result['metrics']

                    session.add(execution)
                    session.commit()

        log_data = {
            "tokens_used": tokens_used,
            "latency_ms": latency_ms
        }

        if validation_result:
            log_data.update({
                "valid": validation_result['is_valid'],
                "quality_score": validation_result['quality_score'],
                "errors": validation_result['errors'],
                "warnings": validation_result['warnings']
            })

        self.logger.info(
            "llm_response_received",
            execution_id=str(self.execution_id),
            **log_data
        )

        # Log validation warnings
        if validation_result and validation_result['warnings']:
            for warning in validation_result['warnings']:
                self.logger.warning(
                    "llm_response_warning",
                    execution_id=str(self.execution_id),
                    warning=warning
                )

        # Log validation errors
        if validation_result and validation_result['errors']:
            for error in validation_result['errors']:
                self.logger.error(
                    "llm_response_validation_error",
                    execution_id=str(self.execution_id),
                    error=error
                )

    async def _validate_llm_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate LLM response quality.

        Checks:
        - Response is not empty
        - Response is parseable (if structured)
        - Response coherence
        - Response completeness

        Returns:
            {
                "is_valid": bool,
                "quality_score": float (0.0-1.0),
                "errors": List[str],
                "warnings": List[str],
                "metrics": Dict[str, Any]
            }
        """
        errors = []
        warnings = []
        metrics = {}
        quality_scores = []

        # Check 1: Response not empty
        content = response_data.get("content", "")
        if not content or (isinstance(content, str) and not content.strip()):
            errors.append("Response is empty")
            quality_scores.append(0.0)
        else:
            quality_scores.append(1.0)
            metrics["content_length"] = len(content) if isinstance(content, str) else 0

        # Check 2: Structured output validation (if applicable)
        if isinstance(response_data, dict):
            # Check for common error patterns
            if "error" in response_data:
                errors.append(f"LLM returned error: {response_data['error']}")
                quality_scores.append(0.0)

            # Check for refusals
            if isinstance(content, str):
                refusal_phrases = [
                    "I cannot", "I can't", "I'm unable to", "I don't have access",
                    "I apologize, but", "Unfortunately, I cannot"
                ]
                if any(phrase.lower() in content.lower() for phrase in refusal_phrases):
                    warnings.append("Response contains refusal language")
                    quality_scores.append(0.5)

        # Check 3: Content length validation
        if isinstance(content, str):
            word_count = len(content.split())
            metrics["word_count"] = word_count

            if word_count < 5:
                warnings.append("Response is very short (< 5 words)")
                quality_scores.append(0.6)
            elif word_count > 5000:
                warnings.append("Response is very long (> 5000 words)")
                quality_scores.append(0.8)
            else:
                quality_scores.append(1.0)

        # Check 4: JSON parsing validation (if response should be JSON)
        if isinstance(content, str) and (content.strip().startswith("{") or content.strip().startswith("[")):
            try:
                import json
                json.loads(content)
                quality_scores.append(1.0)
                metrics["json_valid"] = True
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON response: {str(e)}")
                quality_scores.append(0.0)
                metrics["json_valid"] = False

        # Check 5: Hallucination indicators
        if isinstance(content, str):
            hallucination_phrases = [
                "I don't actually have", "I made that up", "I apologize for the confusion",
                "that was incorrect", "I was mistaken"
            ]
            if any(phrase.lower() in content.lower() for phrase in hallucination_phrases):
                warnings.append("Response contains possible hallucination indicators")
                quality_scores.append(0.7)

        # Calculate overall quality score
        quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        # Determine if response is valid
        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "quality_score": quality_score,
            "errors": errors,
            "warnings": warnings,
            "metrics": metrics
        }

    async def track_should_respond(
        self,
        should_respond: bool,
        confidence: float,
        reasoning: str
    ):
        """
        Track should_respond decision.

        Usage:
            should, conf, reason = await self.should_respond(query)
            await tracker.track_should_respond(should, conf, reason)
        """
        await self.track_stage(ExecutionStage.SHOULD_RESPOND, "Checking relevance")

        if self.execution_id:
            with Session(engine) as session:
                execution = session.get(AgentExecution, self.execution_id)
                if execution:
                    execution.relevance_score = confidence
                    execution.relevance_reasoning = reasoning

                    if not should_respond:
                        execution.status = ExecutionStatus.SKIPPED

                    session.add(execution)
                    session.commit()

        await self.complete_stage(ExecutionStage.SHOULD_RESPOND, {
            "should_respond": should_respond,
            "confidence": confidence,
            "reasoning": reasoning
        })

        self.logger.info(
            "agent_relevance_check",
            execution_id=str(self.execution_id),
            should_respond=should_respond,
            confidence=confidence,
            reasoning=reasoning
        )

    def set_output(self, output_data: Any):
        """
        Set the final output data.

        Usage:
            result = {"analysis": "..."}
            tracker.set_output(result)
        """
        # Convert output to dict if it's a Pydantic model
        if hasattr(output_data, "model_dump"):
            output_data = output_data.model_dump()
        elif not isinstance(output_data, dict):
            output_data = {"result": str(output_data)}

        if self.execution_id:
             with Session(engine) as session:
                execution = session.get(AgentExecution, self.execution_id)
                if execution:
                    execution.output_data = output_data
                    session.add(execution)
                    session.commit()

    async def log_event(
        self,
        message: str,
        level: str = "info",
        data: Optional[Dict[str, Any]] = None
    ):
        """
        Log a custom event during execution.

        Usage:
            await tracker.log_event("Found 15 matching facts", level="debug", data={"count": 15})
        """
        await self._log_stage(
            self._current_stage,
            "event",
            message,
            log_level=level,
            data=data or {}
        )

        log_method = getattr(self.logger, level, self.logger.info)
        log_method(
            "agent_event",
            execution_id=str(self.execution_id),
            message=message,
            **(data or {})
        )

    # ========================================
    # Internal Methods
    # ========================================

    async def _create_execution(self, method: str, input_data: Dict[str, Any]):
        """Create initial execution record in database"""
        self._input_data = input_data
        with Session(engine) as session:
            execution = AgentExecution(
                vault_id=self.vault_id,
                conversation_id=self.conversation_id,
                user_id=self.user_id,
                agent_name=self.agent_name,
                agent_method=method,
                status=ExecutionStatus.PENDING,
                current_stage=ExecutionStage.INIT,
                input_data=input_data,
                started_at=datetime.utcnow()
            )
            session.add(execution)
            session.commit()
            session.refresh(execution)

            self.execution_id = execution.id
            self._current_stage = ExecutionStage.INIT

            # Create call chain link if this is a child execution
            if self.parent_execution_id:
                await self._create_call_chain_link()

    async def _create_call_chain_link(self):
        """Create call chain link for nested agent calls"""
        with Session(engine) as session:
            # Find root execution
            root_id = self.parent_execution_id
            depth = 1

            parent_chain = session.exec(
                select(AgentCallChain)
                .where(AgentCallChain.child_execution_id == self.parent_execution_id)
            ).first()

            if parent_chain:
                root_id = parent_chain.root_execution_id
                depth = parent_chain.depth + 1

            chain_link = AgentCallChain(
                vault_id=self.vault_id,
                conversation_id=self.conversation_id,
                root_execution_id=root_id,
                parent_execution_id=self.parent_execution_id,
                child_execution_id=self.execution_id,
                depth=depth,
                data_passed=self._input_data
            )
            session.add(chain_link)
            session.commit()

    async def _update_status(self, status: ExecutionStatus, stage: Optional[ExecutionStage] = None):
        """Update execution status and optionally stage"""
        if not self.execution_id:
            return
            
        with Session(engine) as session:
            execution = session.get(AgentExecution, self.execution_id)
            if execution:
                execution.status = status
                if stage:
                    execution.current_stage = stage
                    self._current_stage = stage
                session.add(execution)
                session.commit()

    async def _update_stage(self, stage: ExecutionStage):
        """Update current execution stage"""
        self._current_stage = stage
        if not self.execution_id:
            return
            
        with Session(engine) as session:
            execution = session.get(AgentExecution, self.execution_id)
            if execution:
                execution.current_stage = stage
                session.add(execution)
                session.commit()

    async def _log_stage(
        self,
        stage: ExecutionStage,
        stage_status: str,
        message: str,
        log_level: str = "info",
        duration_ms: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        """Create a stage log entry"""
        if not self.execution_id:
            return

        with Session(engine) as session:
            log_entry = AgentExecutionLog(
                execution_id=self.execution_id,
                stage=stage,
                stage_status=stage_status,
                log_level=log_level,
                message=message,
                duration_ms=duration_ms,
                data=data or {}
            )
            session.add(log_entry)
            session.commit()

    async def _handle_error(self, error: Exception, status: ExecutionStatus):
        """Handle execution error"""
        if not self.execution_id:
            return
            
        with Session(engine) as session:
            execution = session.get(AgentExecution, self.execution_id)
            if execution:
                execution.status = status
                execution.error_type = type(error).__name__
                execution.error_message = str(error)
                execution.error_traceback = traceback.format_exc()
                session.add(execution)
                session.commit()

        await self._log_stage(
            self._current_stage,
            "failed",
            f"Error: {str(error)}",
            log_level="error",
            data={
                "error_type": type(error).__name__,
                "error_message": str(error)
            }
        )

    async def _finalize_execution(self):
        """Finalize execution record with timing"""
        if not self.execution_id:
            return

        with Session(engine) as session:
            execution = session.get(AgentExecution, self.execution_id)
            if execution:
                execution.completed_at = datetime.utcnow()
                execution.duration_ms = self._get_duration_ms()
                session.add(execution)
                session.commit()

    def _get_duration_ms(self) -> Optional[float]:
        """Calculate execution duration in milliseconds"""
        if self.start_time:
            return (time.time() - self.start_time) * 1000
        return None


class AgentTrackerFactory:
    """
    Factory for creating execution trackers with shared context.

    Usage in orchestrator or API routes:
        factory = AgentTrackerFactory(vault_id=vault_id, conversation_id=conv_id)
        tracker = factory.create_tracker(agent_name="PsychologistAgent")
    """

    def __init__(
        self,
        vault_id: UUID,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[str] = None
    ):
        self.vault_id = vault_id
        self.conversation_id = conversation_id
        self.user_id = user_id

    def create_tracker(
        self,
        agent_name: str,
        parent_execution_id: Optional[UUID] = None
    ) -> ExecutionTracker:
        """Create a new execution tracker"""
        return ExecutionTracker(
            agent_name=agent_name,
            vault_id=self.vault_id,
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            parent_execution_id=parent_execution_id
        )
