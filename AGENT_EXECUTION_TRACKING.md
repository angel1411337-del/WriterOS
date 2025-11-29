# Agent Execution Tracking & Debugging Guide

**Date:** 2025-11-26
**Author:** Dev1

## Overview

WriterOS includes a comprehensive agent execution tracking system that enables detailed monitoring and debugging of the agent workflow. The system tracks:

- **Which agents fire** (or don't fire) and why
- **Data flow** through the agent pipeline
- **LLM request/response** details
- **Performance metrics** and bottlenecks
- **Error propagation** and failure points
- **Call chains** when agents invoke other agents

## Architecture

### Core Components

#### 1. Database Schema (`src/writeros/schema/agent_execution.py`)

**AgentExecution** - Main execution record
- Tracks individual agent invocations
- Records input/output data
- Stores LLM interactions
- Captures errors and stack traces
- Timing and performance metrics

**AgentExecutionLog** - Stage-by-stage logs
- Granular tracking of execution stages
- Enables pinpointing where issues occur
- Records data transformations

**AgentCallChain** - Call graph tracking
- Maps parent-child agent relationships
- Traces data flow through multiple agents
- Supports nested executions

**AgentPerformanceMetrics** - Aggregated analytics
- Performance statistics over time windows
- Success/failure rates
- Common error patterns

#### 2. Execution Tracker (`src/writeros/utils/agent_tracker.py`)

**ExecutionTracker** - Main tracking interface
- Context manager for automatic tracking
- Stage-by-stage logging
- LLM interaction tracking
- Error handling with stack traces

**AgentTrackerFactory** - Factory for creating trackers
- Centralizes context (vault_id, conversation_id, user_id)
- Simplifies tracker creation

#### 3. Analytics Utilities (`src/writeros/utils/execution_analytics.py`)

**ExecutionAnalytics** - Query and analysis tools
- Find failed executions
- Analyze performance
- Debug why agents didn't fire
- Trace call chains
- Identify performance bottlenecks

## Usage Guide

### Basic Usage in Agents

```python
from writeros.agents.base import BaseAgent
from writeros.schema import ExecutionStage

class MyAgent(BaseAgent):
    async def run(self, vault_id, query, **kwargs):
        # Create tracker
        tracker = self.create_tracker(
            vault_id=vault_id,
            conversation_id=kwargs.get('conversation_id')
        )

        # Track execution
        async with tracker.track_execution(
            method="run",
            input_data={"query": query}
        ):
            # Track relevance check
            should, conf, reason = await self.should_respond(query)
            await tracker.track_should_respond(should, conf, reason)

            if not should:
                return None

            # Track LLM preparation
            await tracker.track_stage(
                ExecutionStage.LLM_PREPARE,
                "Preparing LLM request"
            )

            # Make LLM call with tracking
            request_data = {
                "messages": [...],
                "temperature": 0.7
            }
            await tracker.track_llm_request("gpt-5.1", request_data)

            # Call LLM
            start_time = time.time()
            response = await self.llm.chat(request_data["messages"])
            latency_ms = (time.time() - start_time) * 1000

            # Track response
            await tracker.track_llm_response(
                response_data={"content": response},
                tokens_used=1234,  # Get from API response
                latency_ms=latency_ms
            )

            # Complete stage
            await tracker.complete_stage(ExecutionStage.LLM_CALL)

            # Process results
            await tracker.track_stage(
                ExecutionStage.POST_PROCESS,
                "Processing LLM response"
            )

            result = self._process_response(response)

            # Set output
            tracker.set_output(result)

            return result
```

### Using the Simplified log_event Method

```python
async def analyze_character(self, character_id, vault_id):
    tracker = self.create_tracker(vault_id=vault_id)

    async with tracker.track_execution(method="analyze_character", input_data={"character_id": str(character_id)}):
        # Log events during execution
        await self.log_event(
            "Querying POVBoundary table",
            level="debug",
            character_id=str(character_id)
        )

        pov_boundaries = await self._query_pov_boundaries(character_id)

        await self.log_event(
            f"Found {len(pov_boundaries)} POV boundary records",
            level="info",
            count=len(pov_boundaries)
        )

        # Continue processing...
        result = await self._process_data(pov_boundaries)
        tracker.set_output(result)

        return result
```

### Tracking Nested Agent Calls

```python
class OrchestratorAgent(BaseAgent):
    async def run(self, vault_id, query):
        tracker = self.create_tracker(vault_id=vault_id)

        async with tracker.track_execution(method="run", input_data={"query": query}):
            # Call child agent
            psychologist = PsychologistAgent()

            # Pass parent execution ID to child
            child_tracker = psychologist.create_tracker(
                vault_id=vault_id,
                parent_execution_id=tracker.execution_id
            )

            result = await psychologist.analyze_character(
                character_id=char_id,
                vault_id=vault_id
            )

            # Process child result
            tracker.set_output({"psychologist_result": result})

            return result
```

## Debugging Guide

### 1. Why Didn't an Agent Fire?

```python
from writeros.utils.execution_analytics import ExecutionAnalytics

# Debug why PsychologistAgent didn't fire
result = ExecutionAnalytics.debug_why_agent_didnt_fire(
    agent_name="PsychologistAgent",
    conversation_id=conversation_id,
    vault_id=vault_id
)

print(result)
# Output:
# {
#     "status": "skipped",
#     "message": "PsychologistAgent was invoked but skipped due to relevance check",
#     "executions": [
#         {
#             "execution_id": "...",
#             "relevance_score": 0.3,
#             "relevance_reasoning": "Query is about plot structure, not character psychology",
#             "input_data": {...}
#         }
#     ]
# }
```

### 2. View Execution Timeline

```python
# Get detailed stage-by-stage timeline
timeline = ExecutionAnalytics.get_stage_timeline(execution_id)

for stage in timeline:
    print(f"{stage['timestamp']} - {stage['stage']} - {stage['status']}")
    print(f"  Duration: {stage['duration_ms']}ms")
    print(f"  Message: {stage['message']}")
```

### 3. Find Failed Executions

```python
# Get all failed executions in last 24 hours
failed = ExecutionAnalytics.get_failed_executions(
    vault_id=vault_id,
    hours=24
)

for execution in failed:
    print(f"Agent: {execution.agent_name}")
    print(f"Error: {execution.error_type}: {execution.error_message}")
    print(f"Stage: {execution.current_stage}")
    print(f"Traceback:\n{execution.error_traceback}")
```

### 4. Analyze Agent Performance

```python
# Get performance metrics for an agent
metrics = ExecutionAnalytics.analyze_agent_performance(
    agent_name="PsychologistAgent",
    vault_id=vault_id,
    hours=24
)

print(f"Total Executions: {metrics['total_executions']}")
print(f"Success Rate: {metrics['success_rate']*100}%")
print(f"Avg Duration: {metrics['avg_duration_ms']}ms")
print(f"Common Errors: {metrics['common_errors']}")
```

### 5. Inspect LLM Interactions

```python
# Get detailed LLM request/response
llm_data = ExecutionAnalytics.get_llm_interactions(execution_id)

print(f"Model: {llm_data['model']}")
print(f"Request: {llm_data['request']}")
print(f"Response: {llm_data['response']}")
print(f"Tokens: {llm_data['tokens_used']}")
print(f"Latency: {llm_data['latency_ms']}ms")
```

### 6. Trace Call Chains

```python
# See which agents called which
chain = ExecutionAnalytics.get_execution_call_chain(execution_id)

for link in chain:
    indent = "  " * link['depth']
    print(f"{indent}{link['parent_agent']} -> {link['child_agent']}")
    print(f"{indent}Reason: {link['call_reason']}")
    print(f"{indent}Status: {link['status']}")
```

### 7. Find Performance Bottlenecks

```python
# Find slow executions (>5 seconds)
slow = ExecutionAnalytics.find_slow_executions(
    threshold_ms=5000,
    vault_id=vault_id,
    hours=24
)

for ex in slow:
    print(f"{ex['agent_name']}.{ex['method']}")
    print(f"  Total Duration: {ex['duration_ms']}ms")
    print(f"  LLM Latency: {ex['llm_latency_ms']}ms")
    print(f"  Overhead: {ex['duration_ms'] - (ex['llm_latency_ms'] or 0)}ms")
```

## Execution Stages

The system tracks these granular stages:

| Stage | Description |
|-------|-------------|
| `INIT` | Agent initialization |
| `SHOULD_RESPOND` | Checking relevance |
| `PRE_PROCESS` | Input preprocessing |
| `LLM_PREPARE` | Preparing LLM request |
| `LLM_CALL` | Making LLM call |
| `LLM_PARSE` | Parsing LLM response |
| `POST_PROCESS` | Output postprocessing |
| `COMPLETE` | Finished |

## Execution Statuses

| Status | Description |
|--------|-------------|
| `PENDING` | Agent selected but not started |
| `RUNNING` | Agent is executing |
| `LLM_REQUEST` | Sending request to LLM |
| `LLM_RESPONSE` | Received LLM response |
| `SUCCESS` | Completed successfully |
| `FAILED` | Execution failed |
| `TIMEOUT` | Execution timed out |
| `SKIPPED` | Agent decided not to respond |

## Common Debugging Scenarios

### Scenario 1: Agent Not Receiving Call

**Symptom:** Agent never fires even though it should

**Debug Steps:**
```python
result = ExecutionAnalytics.debug_why_agent_didnt_fire(
    agent_name="PsychologistAgent",
    conversation_id=conv_id,
    vault_id=vault_id
)

if result['status'] == 'never_invoked':
    # Check orchestrator routing logic
    # Check agent registration
    # Verify query matches agent domain
```

### Scenario 2: LLM Request Not Sent

**Symptom:** Agent starts but LLM never called

**Debug Steps:**
```python
execution = ExecutionAnalytics.get_execution_with_logs(execution_id)

# Check what stage it failed at
print(f"Current Stage: {execution['execution']['current_stage']}")

# Review stage logs
for log in execution['logs']:
    if log.stage == ExecutionStage.LLM_PREPARE:
        print(log.message)
        print(log.data)
```

### Scenario 3: Response Not Received

**Symptom:** LLM called but no response processed

**Debug Steps:**
```python
llm_data = ExecutionAnalytics.get_llm_interactions(execution_id)

# Check if request was sent
if llm_data['request']:
    print("Request sent:", llm_data['request'])

# Check if response received
if not llm_data['response']:
    # LLM timeout or network issue
    execution = ExecutionAnalytics.get_execution(execution_id)
    print(f"Status: {execution.status}")
    print(f"Error: {execution.error_message}")
```

## Performance Optimization

### Identify Slow Agents

```python
# Find agents taking >5s
slow = ExecutionAnalytics.find_slow_executions(threshold_ms=5000)

# Group by agent
from collections import defaultdict
by_agent = defaultdict(list)
for ex in slow:
    by_agent[ex['agent_name']].append(ex['duration_ms'])

# Find average
for agent, durations in by_agent.items():
    avg = sum(durations) / len(durations)
    print(f"{agent}: avg {avg}ms over {len(durations)} executions")
```

### Analyze LLM Usage

```python
metrics = ExecutionAnalytics.analyze_agent_performance(
    agent_name="PsychologistAgent"
)

llm_stats = metrics['llm_stats']
print(f"Total LLM Calls: {llm_stats['total_calls']}")
print(f"Total Tokens: {llm_stats['total_tokens']}")
print(f"Avg Tokens/Call: {llm_stats['avg_tokens_per_call']}")
print(f"Avg Latency: {llm_stats['avg_latency_ms']}ms")
```

## Database Queries

### Recent Executions
```sql
SELECT
    agent_name,
    status,
    duration_ms,
    created_at
FROM agent_executions
WHERE vault_id = '{vault_id}'
ORDER BY created_at DESC
LIMIT 50;
```

### Failed Executions by Error Type
```sql
SELECT
    error_type,
    COUNT(*) as count,
    agent_name
FROM agent_executions
WHERE status = 'failed'
    AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY error_type, agent_name
ORDER BY count DESC;
```

### Average Duration by Agent
```sql
SELECT
    agent_name,
    AVG(duration_ms) as avg_ms,
    COUNT(*) as executions
FROM agent_executions
WHERE status = 'success'
    AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_name
ORDER BY avg_ms DESC;
```

## Integration with Existing Logs

The execution tracking system integrates with the existing structlog setup:

- **Structlog** - Real-time console/JSON logs
- **Database** - Persistent execution records
- **Combined** - Correlate logs with execution records via execution_id

Example log correlation:
```python
# From structlog output
# {"timestamp": "2025-11-26T...", "execution_id": "abc-123", ...}

# Query database for full execution details
execution = ExecutionAnalytics.get_execution_with_logs("abc-123")
```

## Best Practices

1. **Always use trackers in production** - Set `enable_tracking=True` (default)
2. **Track all stages** - Call `track_stage()` before major operations
3. **Log events** - Use `log_event()` for debugging breadcrumbs
4. **Set output** - Always call `set_output()` before returning
5. **Handle errors gracefully** - Tracker automatically captures exceptions
6. **Review failed executions daily** - Use analytics to identify patterns
7. **Monitor performance** - Track slow executions and optimize
8. **Trace call chains** - Understand agent interaction patterns

## Disabling Tracking (Testing/Development)

For unit tests or when tracking overhead is unacceptable:

```python
agent = PsychologistAgent(enable_tracking=False)
# No database writes, no tracking overhead
```

Or use the NoOpTracker returned when tracking is disabled.

## Future Enhancements

- Real-time dashboard for monitoring agent executions
- Alerting on high failure rates or slow executions
- Automatic performance regression detection
- LLM cost tracking and budgeting
- Execution replay for debugging
- Visualization of call chains and data flow

---

**Questions or Issues?**
See `src/writeros/utils/execution_analytics.py` for all available query methods.
