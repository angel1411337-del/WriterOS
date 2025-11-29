# Agent Execution Tracking System - Quick Reference

**Created:** 2025-11-26
**Author:** Dev1

## What Was Built

A comprehensive agent execution tracking and debugging system that provides complete visibility into the agent workflow.

## Files Created/Modified

### New Files

1. **`src/writeros/schema/agent_execution.py`** - Database schema for execution tracking
   - `AgentExecution` - Main execution records
   - `AgentExecutionLog` - Stage-by-stage logs
   - `AgentCallChain` - Agent call relationships
   - `AgentPerformanceMetrics` - Aggregated analytics
   - Enums: `ExecutionStatus`, `ExecutionStage`

2. **`src/writeros/utils/agent_tracker.py`** - Execution tracker implementation
   - `ExecutionTracker` - Context manager for tracking
   - `AgentTrackerFactory` - Factory for creating trackers
   - Automatic tracking of: timing, errors, LLM calls, stages

3. **`src/writeros/utils/execution_analytics.py`** - Query and analysis tools
   - `ExecutionAnalytics` - Static methods for querying execution data
   - Debug tools, performance analysis, failure investigation

4. **`AGENT_EXECUTION_TRACKING.md`** - Complete documentation
   - Usage guide with examples
   - Debugging workflows
   - Performance optimization tips
   - SQL query reference

5. **`examples/psychologist_tracking_example.py`** - Practical examples
   - Successful execution
   - Failed execution handling
   - Skipped execution (relevance)
   - Debugging workflows
   - Performance analysis
   - Call chain tracing

### Modified Files

1. **`src/writeros/agents/base.py`** - BaseAgent enhancements
   - Added `enable_tracking` parameter
   - Added `create_tracker()` method
   - Added `log_event()` method
   - Added `NoOpTracker` class

2. **`src/writeros/schema/__init__.py`** - Schema exports
   - Exported new execution tracking models and enums

3. **`AI_CONTEXT.md`** - Implementation documentation
   - Added section on execution tracking system
   - Design rationale and architecture
   - Integration points and performance considerations

## Quick Start

### 1. Basic Usage in Any Agent

```python
async def run(self, vault_id, query):
    # Create tracker
    tracker = self.create_tracker(vault_id=vault_id)

    # Track execution
    async with tracker.track_execution(method="run", input_data={"query": query}):
        # Do work
        result = await self._process(query)

        # Set output
        tracker.set_output(result)
        return result
```

### 2. Debug Why Agent Didn't Fire

```python
from writeros.utils.execution_analytics import ExecutionAnalytics

result = ExecutionAnalytics.debug_why_agent_didnt_fire(
    agent_name="PsychologistAgent",
    conversation_id=conv_id,
    vault_id=vault_id
)
print(result['status'])  # "never_invoked", "skipped", "failed", or "fired_successfully"
```

### 3. Find Failed Executions

```python
failed = ExecutionAnalytics.get_failed_executions(vault_id=vault_id, hours=24)

for ex in failed:
    print(f"{ex.agent_name}: {ex.error_type} - {ex.error_message}")
```

### 4. Analyze Performance

```python
metrics = ExecutionAnalytics.analyze_agent_performance(
    agent_name="PsychologistAgent",
    hours=24
)
print(f"Success Rate: {metrics['success_rate']*100}%")
print(f"Avg Duration: {metrics['avg_duration_ms']}ms")
```

### 5. View Execution Timeline

```python
timeline = ExecutionAnalytics.get_stage_timeline(execution_id)

for stage in timeline:
    print(f"{stage['stage']}: {stage['message']} ({stage['duration_ms']}ms)")
```

## NEW: LLM Response Quality Validation

### Automatic Response Validation
- **Empty Response Detection**: Catches blank or null responses
- **Error Pattern Detection**: Identifies LLM error messages
- **Refusal Detection**: Detects "I cannot" type responses
- **Length Validation**: Flags too short (<5 words) or too long (>5000 words) responses
- **JSON Validation**: Validates JSON parsing if response is JSON
- **Hallucination Detection**: Looks for self-correction phrases

### Quality Metrics Stored
- `response_valid`: Boolean indicating if response passed validation
- `response_quality_score`: 0.0-1.0 score (average of all checks)
- `response_validation_errors`: List of validation failures
- `response_warnings`: List of quality warnings
- `response_metrics`: Word count, JSON validity, etc.

### CLI Commands for Quality
```bash
# Find poor quality responses
writeros poor-responses --threshold 0.7

# Analyze overall quality
writeros tracking-stats  # Includes quality metrics

# View specific response
writeros view-execution <id>  # Shows quality score and errors
```

## Key Features

### ✅ Comprehensive Tracking
- Agent lifecycle (pending → running → success/failed)
- Stage-by-stage execution flow
- LLM request/response details
- Input/output data
- Timing and performance metrics

### ✅ Error Debugging
- Automatic error capture with stack traces
- Pinpoint exact failure stage
- Error pattern analysis
- Failed execution queries

### ✅ Performance Monitoring
- Execution duration tracking
- LLM latency measurement
- Slow execution detection
- Performance metrics over time

### ✅ Call Chain Tracing
- Track nested agent calls
- Parent-child relationships
- Data flow visualization
- Depth and sequence tracking

### ✅ Relevance Tracking
- Why agents skip (low relevance)
- Confidence scores
- Reasoning for decisions

## Database Tables

All tracking data is persisted in PostgreSQL:

- `agent_executions` - Main execution records
- `agent_execution_logs` - Granular stage logs
- `agent_call_chains` - Agent call relationships
- `agent_performance_metrics` - Aggregated analytics

Indexed on: `vault_id`, `agent_name`, `status`, `created_at`, `conversation_id`

## Execution Stages

| Stage | When It's Used |
|-------|----------------|
| `INIT` | Agent initialization |
| `SHOULD_RESPOND` | Checking if agent should respond |
| `PRE_PROCESS` | Input preprocessing (e.g., POV queries) |
| `LLM_PREPARE` | Preparing LLM prompts |
| `LLM_CALL` | Making LLM API call |
| `LLM_PARSE` | Parsing LLM response |
| `POST_PROCESS` | Output postprocessing |
| `COMPLETE` | Execution finished |

## Execution Statuses

| Status | Meaning |
|--------|---------|
| `PENDING` | Agent selected but not started |
| `RUNNING` | Currently executing |
| `LLM_REQUEST` | Sent request to LLM |
| `LLM_RESPONSE` | Received LLM response |
| `SUCCESS` | Completed successfully |
| `FAILED` | Execution failed |
| `TIMEOUT` | Execution timed out |
| `SKIPPED` | Agent decided not to respond |

## Common Debugging Scenarios

### Scenario 1: Agent Never Fires
```python
result = ExecutionAnalytics.debug_why_agent_didnt_fire(...)
# Check: Orchestrator routing, agent registration, query matching
```

### Scenario 2: Execution Fails
```python
failed = ExecutionAnalytics.get_failed_executions(hours=24)
# Check: error_type, error_message, error_traceback, current_stage
```

### Scenario 3: LLM Issues
```python
llm_data = ExecutionAnalytics.get_llm_interactions(execution_id)
# Check: request sent, response received, tokens, latency
```

### Scenario 4: Slow Performance
```python
slow = ExecutionAnalytics.find_slow_executions(threshold_ms=5000)
# Check: duration_ms, llm_latency_ms, overhead
```

### Scenario 5: Call Chain Issues
```python
chain = ExecutionAnalytics.get_execution_call_chain(execution_id)
# Check: parent-child relationships, data flow, status
```

## Integration Points

- **BaseAgent**: All agents inherit tracking capability
- **Structlog**: Real-time logs with execution_id
- **Database**: Persistent queryable records
- **API Routes**: Factory creates trackers with context
- **Orchestrator**: Passes parent_execution_id to children

## Performance

- **Zero overhead when disabled**: Use `enable_tracking=False`
- **Async I/O**: Non-blocking database writes
- **Indexed queries**: Fast lookups on common fields
- **NoOpTracker**: Zero-cost abstraction for tests

## CLI Commands Reference

### Tracking Enabled by Default
```bash
# Run chat with tracking (default)
writeros chat "Analyze Frodo's character arc"

# Disable tracking for performance testing
writeros chat "Test message" --no-enable-tracking
```

### View Tracking Statistics
```bash
writeros tracking-stats
writeros tracking-stats --hours 48
writeros tracking-stats --vault-id abc-123
```

### View Specific Execution
```bash
writeros view-execution <execution-id>
```

### Find Poor Quality Responses
```bash
writeros poor-responses
writeros poor-responses --threshold 0.6 --hours 48 --limit 20
```

### Debug Agent Issues
```bash
writeros debug-agent PsychologistAgent --conversation-id <id> --vault-id <id>
```

## Where Logs Are Stored

### 1. Real-Time Logs (Structlog)
- **Location**: stdout (terminal)
- **Format**: Colored in dev, JSON in production
- **Configuration**: `src/writeros/core/logging.py`
- **Environment**: `APP_ENV=development` or `production`

### 2. Database (PostgreSQL)
- **Location**: Database defined in `.env` (`DATABASE_URL`)
- **Tables**:
  - `agent_executions` - Main execution records with LLM responses
  - `agent_execution_logs` - Stage-by-stage logs
  - `agent_call_chains` - Nested agent calls
  - `agent_performance_metrics` - Aggregated analytics

### 3. LLM Responses Specifically
Stored in `agent_executions` table:
- `llm_request` (JSONB) - Messages sent to LLM
- `llm_response` (JSONB) - LLM response content
- `response_quality_score` (float) - Quality rating
- `response_validation_errors` (JSONB) - Validation failures
- `response_warnings` (JSONB) - Quality warnings

**Query LLM responses:**
```sql
SELECT
    agent_name,
    llm_model,
    llm_response->'content' as response,
    response_quality_score,
    response_validation_errors
FROM agent_executions
WHERE llm_response IS NOT NULL
ORDER BY created_at DESC;
```

## Next Steps

1. **Update database schema**: Run migration to create new tables
2. **Integrate into agents**: Add tracking to existing agent methods
3. **Test tracking**: Run examples to verify functionality
4. **Monitor production**: Use `writeros tracking-stats` to monitor
5. **Check quality**: Use `writeros poor-responses` to find issues
6. **Debug failures**: Use `writeros debug-agent` when things go wrong
7. **Build dashboard**: (Future) Visualize execution data

## Documentation

- **Full Guide**: `AGENT_EXECUTION_TRACKING.md`
- **Examples**: `examples/psychologist_tracking_example.py`
- **Implementation**: `AI_CONTEXT.md` (Agent Execution Tracking section)
- **Schema**: `src/writeros/schema/agent_execution.py`
- **Tracker**: `src/writeros/utils/agent_tracker.py`
- **Analytics**: `src/writeros/utils/execution_analytics.py`

---

**Questions?** See the full documentation in `AGENT_EXECUTION_TRACKING.md`
