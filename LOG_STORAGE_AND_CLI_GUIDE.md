# Log Storage & CLI Guide

**Date:** 2025-11-26
**Author:** Dev1

## Where Are Logs and Responses Stored?

WriterOS uses a multi-layered logging and storage system:

### 1. Real-Time Console Logs (Structlog)

**Location:** `stdout` (terminal output)

**Format:**
- **Development**: Colored console output with timestamps
- **Production**: JSON structured logs

**Configuration:** `src/writeros/core/logging.py`

**Environment Variable:** `APP_ENV` controls format
- `development` → Human-readable colored output
- `production` → JSON logs (Docker/Cloud friendly)

**Example Output (Development):**
```
2025-11-26T10:30:45.123 [INFO] agent_execution_started agent=PsychologistAgent execution_id=abc-123
2025-11-26T10:30:47.456 [INFO] llm_response_received tokens_used=1234 latency_ms=2300
```

**Example Output (Production):**
```json
{
  "timestamp": "2025-11-26T10:30:45.123Z",
  "level": "info",
  "event": "agent_execution_started",
  "agent": "PsychologistAgent",
  "execution_id": "abc-123"
}
```

### 2. Database Persistence (PostgreSQL)

**Location:** PostgreSQL database (connection defined in `.env`)

**Connection String:** `DATABASE_URL=postgresql://user:password@host:port/database`

**Tables:**

#### `agent_executions` - Main Execution Records
**Stores:**
- Agent name, method, status
- Input/output data (JSONB)
- LLM request/response (JSONB)
- Timing metrics
- Error details with stack traces
- **LLM response quality validation** (NEW)
  - `response_valid`: Boolean
  - `response_quality_score`: 0.0-1.0
  - `response_validation_errors`: List of errors
  - `response_warnings`: List of warnings
  - `response_metrics`: Quality metrics dict

**Indexes:**
- `vault_id`, `agent_name`, `status`, `created_at`, `conversation_id`

**Query Example:**
```sql
SELECT
    agent_name,
    status,
    response_quality_score,
    llm_response,
    created_at
FROM agent_executions
WHERE vault_id = '...'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

#### `agent_execution_logs` - Stage-by-Stage Logs
**Stores:**
- Execution stage (INIT, LLM_CALL, etc.)
- Stage status (started, completed, failed)
- Log level (debug, info, warning, error)
- Message and data (JSONB)
- Duration per stage

**Query Example:**
```sql
SELECT
    stage,
    stage_status,
    message,
    duration_ms,
    timestamp
FROM agent_execution_logs
WHERE execution_id = '...'
ORDER BY timestamp;
```

#### `agent_call_chains` - Nested Agent Calls
**Stores:**
- Parent/child execution relationships
- Call depth and sequence
- Data passed between agents

**Query Example:**
```sql
SELECT
    parent_execution_id,
    child_execution_id,
    depth,
    call_reason
FROM agent_call_chains
WHERE root_execution_id = '...'
ORDER BY depth, sequence;
```

#### `agent_performance_metrics` - Aggregated Analytics
**Stores:**
- Success/failure rates
- Average durations
- Token usage
- Common errors

**Updated Periodically** (hourly or on-demand)

### 3. LLM Response Storage Details

**Where LLM Responses Are Stored:**

1. **Database - `agent_executions.llm_response` column**
   - Type: JSONB
   - Contains: Full LLM response including content, metadata
   - Queryable: Yes, can search within JSON

2. **Database - `agent_executions.llm_request` column**
   - Type: JSONB
   - Contains: Messages sent to LLM, temperature, etc.
   - Useful for debugging prompt issues

3. **Database - Response Quality Fields** (NEW)
   - `response_valid`: Was response parseable?
   - `response_quality_score`: Quality score (0.0-1.0)
   - `response_validation_errors`: Validation errors
   - `response_warnings`: Quality warnings
   - `response_metrics`: Word count, JSON validity, etc.

**Example Query - Find All LLM Responses for an Agent:**
```sql
SELECT
    id as execution_id,
    llm_model,
    llm_request->'messages' as messages_sent,
    llm_response->'content' as response_content,
    response_quality_score,
    response_validation_errors,
    llm_tokens_used,
    llm_latency_ms
FROM agent_executions
WHERE agent_name = 'PsychologistAgent'
  AND llm_response IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

**Example Query - Find Poor Quality Responses:**
```sql
SELECT
    id,
    agent_name,
    llm_model,
    response_quality_score,
    response_validation_errors,
    response_warnings,
    llm_response->'content' as content
FROM agent_executions
WHERE response_quality_score < 0.7
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY response_quality_score ASC;
```

### 4. Log Rotation & Retention

**Structlog (Console):**
- No rotation (ephemeral)
- Captured by Docker/systemd if running in containers

**Database:**
- No automatic retention policy
- Recommended: Implement periodic cleanup for old executions
- Consider: Archive executions older than 30 days

**Recommended Cleanup Script:**
```sql
-- Archive old executions (optional)
-- Delete executions older than 90 days
DELETE FROM agent_execution_logs
WHERE execution_id IN (
    SELECT id FROM agent_executions
    WHERE created_at < NOW() - INTERVAL '90 days'
);

DELETE FROM agent_executions
WHERE created_at < NOW() - INTERVAL '90 days';
```

## CLI Commands

WriterOS CLI (`python -m writeros.cli.main` or `writeros` if installed) now includes tracking commands:

### Basic Commands

```bash
# Run chat with tracking enabled (default)
writeros chat "Analyze Frodo's character arc"

# Run chat without tracking (for testing/performance)
writeros chat "Analyze Frodo's character arc" --no-enable-tracking

# Show database stats
writeros stats
```

### Tracking Commands (NEW)

#### 1. View Tracking Statistics

```bash
writeros tracking-stats

# With options
writeros tracking-stats --hours 48
writeros tracking-stats --vault-id abc-123-def
```

**Output:**
```
============================================================
Agent Execution Statistics (Last 24 hours)
============================================================

Recent Executions: 10
  ✓ PsychologistAgent - success (2300ms)
  ✓ ArchitectAgent - success (1800ms)
  ✗ NavigatorAgent - failed (500ms)
  ⊘ PsychologistAgent - skipped (100ms)

Failed Executions: 2
  ✗ NavigatorAgent: ValueError
  ✗ MechanicAgent: TimeoutError

LLM Response Quality:
  Total Responses: 8
  Valid: 7 (87.5%)
  Avg Quality Score: 0.85
  Distribution:
    excellent (>0.9): 4
    good (0.7-0.9): 3
    fair (0.5-0.7): 1
    poor (<0.5): 0

============================================================
```

#### 2. View Specific Execution

```bash
writeros view-execution abc-123-def-456
```

**Output:**
```
============================================================
Execution Details: abc-123-def-456
============================================================

Agent: PsychologistAgent
Method: analyze_character
Status: success
Duration: 2300ms

Relevance:
  Score: 0.95
  Reasoning: Query directly matches character psychology domain

LLM:
  Model: gpt-5.1
  Tokens: 1234
  Latency: 2100ms

Response Quality:
  Valid: True
  Score: 0.92
  Warnings: Response is very long (> 5000 words)

Stage Timeline:
  [init] Agent execution started (0ms)
  [should_respond] Checking relevance (50ms)
  [pre_process] Querying POVBoundary table (150ms)
  [llm_prepare] Preparing LLM request (100ms)
  [llm_call] Calling LLM: gpt-5.1 (2100ms)
  [complete] Execution completed successfully (0ms)

============================================================
```

#### 3. Find Poor Quality Responses

```bash
writeros poor-responses

# With options
writeros poor-responses --threshold 0.6 --hours 48 --limit 20
```

**Output:**
```
============================================================
Poor Quality LLM Responses (Score < 0.7)
============================================================

Execution: abc-123
  Agent: PsychologistAgent
  Model: gpt-5.1
  Quality Score: 0.65
  Warnings: Response is very short (< 5 words), Response contains refusal language

Execution: def-456
  Agent: ArchitectAgent
  Model: gpt-5.1
  Quality Score: 0.50
  Errors: Invalid JSON response: Expecting value: line 1 column 1 (char 0)

============================================================
```

#### 4. Debug Why Agent Didn't Fire

```bash
writeros debug-agent PsychologistAgent --conversation-id abc-123 --vault-id def-456
```

**Output:**
```
============================================================
Debug: PsychologistAgent
============================================================

Status: skipped
Message: PsychologistAgent was invoked but skipped due to relevance check

Execution Details:
  Execution ID: xyz-789
    Relevance: 0.3
    Reasoning: Query is about plot structure, not character psychology

============================================================
```

### Complete CLI Reference

```bash
# Core Commands
writeros serve                    # Start API server
writeros ingest --vault-path ./   # Ingest vault
writeros stats                    # Database stats
writeros chat "message"           # Chat with agent

# Tracking Commands
writeros tracking-stats           # Show tracking overview
writeros view-execution <id>      # View execution details
writeros poor-responses           # Find quality issues
writeros debug-agent <name>       # Debug agent not firing

# Options
--vault-id <uuid>                 # Specify vault
--vault-path <path>               # Specify vault path
--hours <int>                     # Time window
--enable-tracking / --no-enable-tracking  # Toggle tracking
--threshold <float>               # Quality threshold
--conversation-id <uuid>          # Conversation context
```

## Accessing Logs Programmatically

### Python API

```python
from writeros.utils.execution_analytics import ExecutionAnalytics
from uuid import UUID

# Get recent executions
recent = ExecutionAnalytics.get_recent_executions(
    vault_id=vault_id,
    agent_name="PsychologistAgent",
    limit=50
)

# Get failed executions
failed = ExecutionAnalytics.get_failed_executions(hours=24)

# Analyze response quality
quality = ExecutionAnalytics.analyze_response_quality(
    agent_name="PsychologistAgent",
    hours=24
)

# Find poor quality responses
poor = ExecutionAnalytics.get_poor_quality_responses(
    quality_threshold=0.7,
    hours=24
)

# View specific execution
details = ExecutionAnalytics.get_execution_with_logs(execution_id)

# Debug agent
result = ExecutionAnalytics.debug_why_agent_didnt_fire(
    agent_name="PsychologistAgent",
    conversation_id=conv_id,
    vault_id=vault_id
)
```

### Direct SQL Access

```python
from writeros.utils.db import engine
from sqlmodel import Session, select
from writeros.schema import AgentExecution

with Session(engine) as session:
    # Custom query
    executions = session.exec(
        select(AgentExecution)
        .where(AgentExecution.agent_name == "PsychologistAgent")
        .where(AgentExecution.response_quality_score < 0.7)
        .order_by(AgentExecution.created_at.desc())
    ).all()

    for ex in executions:
        print(f"{ex.agent_name}: {ex.response_quality_score}")
        print(f"Errors: {ex.response_validation_errors}")
        print(f"Response: {ex.llm_response}")
```

## LLM Response Quality Validation

### How It Works

When `validate=True` (default) in `track_llm_response()`:

1. **Empty Check**: Response not empty
2. **Error Detection**: Checks for error fields
3. **Refusal Detection**: Looks for "I cannot", "I'm unable to"
4. **Length Validation**: Too short (<5 words) or too long (>5000 words)
5. **JSON Validation**: If response looks like JSON, validates parsing
6. **Hallucination Detection**: Looks for phrases like "I made that up"

**Quality Score Calculation:**
- Average of all validation checks (0.0-1.0)
- Each check contributes a score
- Overall score stored in `response_quality_score`

### Customizing Validation

Extend `ExecutionTracker._validate_llm_response()` to add custom checks:

```python
# In src/writeros/utils/agent_tracker.py

async def _validate_llm_response(self, response_data: Dict[str, Any]):
    # ... existing checks ...

    # Custom Check 6: Domain-specific validation
    if isinstance(content, str):
        if "[[PLACEHOLDER]]" in content:
            errors.append("Response contains placeholder text")
            quality_scores.append(0.0)

    # Custom Check 7: Sentiment check
    if self.agent_name == "PsychologistAgent":
        if "happy" in content.lower() and "sad" in content.lower():
            warnings.append("Response contains contradictory emotions")
            quality_scores.append(0.7)

    return {
        "is_valid": len(errors) == 0,
        "quality_score": sum(quality_scores) / len(quality_scores),
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics
    }
```

## Best Practices

### 1. Enable Tracking in Production
```bash
writeros chat "message"  # Tracking enabled by default
```

### 2. Disable for Performance Testing
```bash
writeros chat "message" --no-enable-tracking
```

### 3. Regular Monitoring
```bash
# Daily checks
writeros tracking-stats
writeros poor-responses --hours 24
```

### 4. Investigate Failures
```bash
# When something fails
writeros debug-agent PsychologistAgent --conversation-id <id>
writeros view-execution <execution-id>
```

### 5. Quality Alerts
```python
# Setup automated alerts
quality = ExecutionAnalytics.analyze_response_quality(hours=1)
if quality['validity_rate'] < 0.8:
    send_alert(f"LLM validity rate dropped to {quality['validity_rate']}")
```

## Troubleshooting

### Logs Not Appearing

**Check Structlog Configuration:**
```python
# In src/writeros/core/logging.py
from writeros.config import settings
print(settings.APP_ENV)  # Should be "development" or "production"
print(settings.LOG_LEVEL)  # Should be "INFO" or "DEBUG"
```

### Database Not Recording

**Check Database Connection:**
```bash
writeros stats  # Should show vault info

# Or directly
python -c "from writeros.utils.db import engine; print(engine.url)"
```

**Verify Tables Exist:**
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'agent_%';
```

### Tracking Not Working

**Check Agent Configuration:**
```python
agent = PsychologistAgent(enable_tracking=True)  # Ensure True
tracker = agent.create_tracker(vault_id=vault_id)  # Must create tracker
```

**Verify Tracker Usage:**
```python
async with tracker.track_execution(...):  # Must use context manager
    # Agent work
    tracker.set_output(result)  # Must set output
```

---

**Next Steps:**
1. Run `writeros tracking-stats` to see current state
2. Try `writeros chat "test message"` and check logs
3. Query database to verify storage
4. Review `AGENT_EXECUTION_TRACKING.md` for detailed usage
