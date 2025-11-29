# Testing Guide: Dual-Mode Output System

**Date:** 2025-11-26
**Author:** Dev1

---

## Quick Start (5 Minutes)

### Prerequisites Check

```bash
# 1. Check if database is running
psql $DATABASE_URL -c "SELECT COUNT(*) FROM vaults;"

# 2. Check if you have a vault ingested
writeros stats

# 3. Check Python environment
python --version  # Should be 3.11+
which writeros    # Should show installed CLI
```

If any of these fail, see "Setup from Scratch" below.

### Simplest Test (No Vault Required)

If you just want to test that the code works without setting up a full vault:

```bash
# Start Python interactive shell
python

# Run this test code:
```

```python
import asyncio
from writeros.agents.orchestrator import OrchestratorAgent
from uuid import uuid4

async def test_basic():
    """Test that orchestrator can build structured summary."""
    orchestrator = OrchestratorAgent(enable_tracking=False)

    # Simulate agent results (what agents would return)
    mock_results = {
        "chronologist": type('TimelineExtraction', (), {
            'model_dump': lambda: {
                'events': [
                    {'title': 'Event 1', 'order': 1, 'summary': 'First event'},
                    {'title': 'Event 2', 'order': 2, 'summary': 'Second event'}
                ],
                'continuity_notes': 'Timeline conflict detected'
            }
        })(),
        "psychologist": type('PsychologyExtraction', (), {
            'model_dump': lambda: {
                'profiles': [
                    {
                        'name': 'Test Character',
                        'archetype': 'Hero',
                        'core_desire': 'Justice',
                        'core_fear': 'Failure'
                    }
                ]
            }
        })()
    }

    # Test structured summary builder
    summary = orchestrator._build_structured_summary(mock_results)

    print("=== STRUCTURED SUMMARY OUTPUT ===")
    print(summary)
    print("\n=== TEST RESULTS ===")

    # Assertions
    assert "📊 SYSTEMATIC ANALYSIS" in summary
    assert "⏱️ TIMELINE ANALYSIS" in summary
    assert "🧠 PSYCHOLOGICAL ANALYSIS" in summary
    assert "Event 1" in summary
    assert "Test Character" in summary
    assert "Timeline conflict detected" in summary

    print("✅ All assertions passed!")
    print("✅ Structured summary generation works!")

# Run the test
asyncio.run(test_basic())
```

Expected output:
```
=== STRUCTURED SUMMARY OUTPUT ===
## 📊 SYSTEMATIC ANALYSIS

### ⏱️ TIMELINE ANALYSIS
**Events Identified:** 2
1. **Event 1** (Order: 1)
   First event
2. **Event 2** (Order: 2)
   Second event

**⚠️ Continuity Notes:** Timeline conflict detected

### 🧠 PSYCHOLOGICAL ANALYSIS
**Characters Analyzed:** 1

**Test Character**
- Archetype: Hero
- Core Desire: Justice
- Core Fear: Failure

=== TEST RESULTS ===
✅ All assertions passed!
✅ Structured summary generation works!
```

---

## Full Integration Test (With Real Vault)

### Option 1: Use Existing Vault

If you already have a vault ingested:

```bash
# 1. Find your vault ID
writeros stats

# Output will show:
# Vault: My Vault (abc-123-def-456)
# Copy the UUID

# 2. Run a simple test query
writeros chat "Tell me about the main character" --vault-id abc-123-def-456

# 3. Check if structured output appears
# You should see:
# ## 📊 SYSTEMATIC ANALYSIS
# (agent-specific sections)
# ## 💬 NARRATIVE SUMMARY
# (prose response)

# 4. Verify execution tracking
writeros tracking-stats

# 5. View the execution details
writeros view-execution <id-from-stats>
```

### Option 2: Create Test Vault

If you don't have a vault, create a minimal test vault:

```bash
# 1. Create test directory
mkdir -p /tmp/test-vault
cd /tmp/test-vault

# 2. Create a simple markdown file
cat > character.md << 'EOF'
# Jon Snow

Jon Snow is the bastard son of Ned Stark. He joins the Night's Watch.

## Personality
- Honorable like his father
- Struggles with his identity
- Natural leader

## Journey
Jon travels from Winterfell to Castle Black, a journey of 700 miles that takes 14 days on horseback.

## Relationships
- Ned Stark (father figure)
- Arya Stark (half-sister, close bond)
- Robb Stark (half-brother)
EOF

# 3. Ingest the vault
writeros ingest --vault-path /tmp/test-vault

# Output will show:
# Ingestion Complete!
# Documents Indexed: 1
# Chunks Created: 3

# 4. Run test query
writeros chat "If Jon sends a raven from Castle Black to Winterfell, how long would it take?" --vault-path /tmp/test-vault

# Expected output:
# ## 📊 SYSTEMATIC ANALYSIS
#
# ### 🗺️ TRAVEL ANALYSIS
# **Distance:** 700 miles
# **Travel Time:** ... days
#
# ## 💬 NARRATIVE SUMMARY
# Based on the distance between Castle Black and Winterfell...
```

---

## ASOIAF Stress Test (Full Test)

This is the test case from the diagnostic report.

### Prerequisites

You need an ASOIAF vault ingested. If you don't have one:

```bash
# Option A: Use sample ASOIAF text
mkdir -p /tmp/asoiaf-test
cd /tmp/asoiaf-test

# Create sample scenes
cat > catelyn-winterfell.md << 'EOF'
# Catelyn I - Winterfell

Catelyn sat with Maester Luwin in his tower.

"The seed is strong," she repeated, thinking of Jon Arryn's final words.

She decided to write to Ned immediately, warning him about the Lannisters.

The raven would take at least two weeks to reach King's Landing.
EOF

cat > ned-kingslanding.md << 'EOF'
# Eddard III - King's Landing (Day 7)

Ned confronted Littlefinger in the throne room.

"I know the truth about the royal children," Ned said.

This scene happens on the 7th day after Ned arrived in King's Landing.
EOF

# Ingest
writeros ingest --vault-path /tmp/asoiaf-test
```

### Run the Test

```bash
# The exact query from the diagnostic report
writeros chat "I'm revising ASOIAF Book 1. Catelyn discusses Jon Arryn's final words ('the seed is strong') with Maester Luwin at Winterfell, sends letter to Ned before Littlefinger scene. What breaks?" --vault-path /tmp/asoiaf-test
```

### Expected Output

```markdown
## 📊 SYSTEMATIC ANALYSIS

### ⏱️ TIMELINE ANALYSIS
**Events Identified:** 3
1. **Catelyn-Luwin Discussion** (Order: 1)
   Catelyn discusses Jon Arryn's final words with Maester Luwin
2. **Letter Sent** (Order: 2)
   Catelyn sends raven to King's Landing
3. **Ned-Littlefinger Scene** (Order: 3)
   Ned confronts Littlefinger (Day 7)

**⚠️ Continuity Notes:** Raven requires 14 days travel time but scene occurs on day 7

### 🗺️ TRAVEL ANALYSIS
**Distance:** ~850 km (Winterfell to King's Landing)
**Travel Time:** 14 days (raven)

### 🏛️ STRUCTURAL ANALYSIS
**Chapters Affected:** Catelyn I, Eddard III

**⚠️ Plot Conflicts Detected:** 1
1. Letter cannot arrive before Littlefinger confrontation

## 💬 NARRATIVE SUMMARY

This revision creates a timeline problem. If Catelyn sends the letter before
the Littlefinger scene, the raven needs 14 days to travel from Winterfell to
King's Landing. However, the Littlefinger scene occurs on day 7, meaning the
letter hasn't arrived yet.

To fix this, you could:
1. Move the Catelyn scene to happen after the Littlefinger scene
2. Extend the timeline so more than 14 days pass
3. Use a different communication method
```

### Validation Checklist

After running the test, verify:

- [ ] **Structured section appears** - Contains "📊 SYSTEMATIC ANALYSIS"
- [ ] **Timeline section** - Shows "⏱️ TIMELINE ANALYSIS"
- [ ] **Events listed** - Shows at least 2-3 events
- [ ] **Continuity warning** - Mentions the 14-day conflict
- [ ] **Travel section** - Shows "🗺️ TRAVEL ANALYSIS" with distance/time
- [ ] **Structural section** - Shows "🏛️ STRUCTURAL ANALYSIS" with chapters
- [ ] **Conflicts listed** - Shows the timeline conflict
- [ ] **Narrative section** - Contains "💬 NARRATIVE SUMMARY"
- [ ] **Narrative coherent** - Prose advice is readable and helpful
- [ ] **No truncation** - No "..." or cut-off text at 200 characters

---

## Testing Execution Tracking

### Check Tracking Stats

```bash
# View recent executions
writeros tracking-stats

# Expected output:
# ============================================================
# Agent Execution Statistics (Last 24 hours)
# ============================================================
#
# Recent Executions: 5
#   ✓ OrchestratorAgent - success (5200ms)
#   ✓ ChronologistAgent - success (1200ms)
#   ✓ PsychologistAgent - success (1800ms)
#
# LLM Response Quality:
#   Total Responses: 5
#   Valid: 5 (100%)
#   Avg Quality Score: 0.92
```

### View Specific Execution

```bash
# Get execution ID from tracking-stats, then:
writeros view-execution <execution-id>

# Expected output:
# ============================================================
# Execution Details: abc-123-def-456
# ============================================================
#
# Agent: OrchestratorAgent
# Method: process_chat
# Status: success
# Duration: 5200ms
#
# Stage Timeline:
#   [pre_process] Starting iterative RAG retrieval (100ms)
#   [post_process] Broadcasting to specialized agents (3800ms)
#   [complete] Building structured output (1200ms)
```

### Debug Agent Behavior

```bash
# Check if specific agent fired
writeros debug-agent ChronologistAgent --conversation-id <conv-id> --vault-id <vault-id>

# To get conversation-id, check database:
psql $DATABASE_URL -c "SELECT id FROM conversations ORDER BY created_at DESC LIMIT 1;"
```

---

## Database Verification

### Check Orchestrator Executions

```bash
psql $DATABASE_URL << 'EOF'
SELECT
    id,
    status,
    duration_ms,
    output_data->'responding_agents' as agents,
    output_data->'structured_summary_generated' as has_summary,
    created_at
FROM agent_executions
WHERE agent_name = 'OrchestratorAgent'
ORDER BY created_at DESC
LIMIT 5;
EOF
```

Expected output:
```
 id                  | status  | duration_ms | agents                          | has_summary
---------------------+---------+-------------+---------------------------------+-------------
 abc-123-def-456     | success | 5200        | ["chronologist","psychologist"] | true
```

### Check Stage Timeline

```bash
psql $DATABASE_URL << 'EOF'
SELECT
    stage,
    message,
    duration_ms,
    timestamp
FROM agent_execution_logs
WHERE execution_id = '<execution-id-from-above>'
ORDER BY timestamp;
EOF
```

### Check Agent Responses

```bash
psql $DATABASE_URL << 'EOF'
SELECT
    agent_name,
    status,
    output_data
FROM agent_executions
WHERE vault_id = '<your-vault-id>'
  AND created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
EOF
```

---

## Troubleshooting

### Issue: No Structured Summary Appears

**Symptoms:**
- Only "💬 NARRATIVE SUMMARY" appears
- No "📊 SYSTEMATIC ANALYSIS" section

**Debug Steps:**

1. Check if agents are responding:
   ```bash
   writeros tracking-stats
   # Look for "Recent Executions" - should show agent names
   ```

2. Check orchestrator output data:
   ```bash
   psql $DATABASE_URL -c "SELECT output_data FROM agent_executions WHERE agent_name='OrchestratorAgent' ORDER BY created_at DESC LIMIT 1;"
   ```

3. Check if agents returned structured data:
   ```python
   # In Python shell
   from writeros.utils.execution_analytics import ExecutionAnalytics
   from uuid import UUID

   # Get last orchestrator execution
   execs = ExecutionAnalytics.get_recent_executions(limit=1)
   print(execs[0].output_data)
   # Should show: {'responding_agents': [...], 'structured_summary_generated': true}
   ```

**Possible Causes:**
- No agents responded (all skipped due to low relevance)
- Agents returned data in unexpected format
- Bug in `_build_structured_summary()`

**Fix:**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
writeros chat "test query" --vault-path ./path

# Check logs for "agent_responding" messages
```

### Issue: Execution Tracking Not Working

**Symptoms:**
- `writeros tracking-stats` shows no data
- Database has no agent_executions records

**Debug Steps:**

1. Check if tracking is enabled:
   ```python
   from writeros.agents.orchestrator import OrchestratorAgent
   orch = OrchestratorAgent()
   print(orch.enable_tracking)  # Should be True
   ```

2. Check database schema:
   ```bash
   psql $DATABASE_URL -c "\d agent_executions"
   # Should show table structure
   ```

3. Check if database is accessible:
   ```bash
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM agent_executions;"
   ```

**Possible Causes:**
- Tracking disabled in CLI (`--no-enable-tracking`)
- Database migration not run
- Database connection issue

**Fix:**
```bash
# Run database migrations
alembic upgrade head

# Or initialize database
python -c "from writeros.utils.db import init_db; init_db()"

# Test with tracking explicitly enabled
writeros chat "test" --enable-tracking
```

### Issue: Agents Not Responding

**Symptoms:**
- `tracking-stats` shows "0 agents responded"
- Only synthesis appears, no structured data

**Debug Steps:**

1. Check agent relevance scores:
   ```bash
   writeros debug-agent ChronologistAgent --conversation-id <id> --vault-id <id>
   ```

2. Check if query matches agent domains:
   ```bash
   # Timeline queries should trigger Chronologist
   writeros chat "What's the timeline of events?" --vault-path ./path

   # Character queries should trigger Psychologist
   writeros chat "Tell me about the main character's personality" --vault-path ./path
   ```

3. Check RAG retrieval:
   ```bash
   # Check if documents are being retrieved
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM documents WHERE vault_id='<vault-id>';"
   ```

**Possible Causes:**
- Query too generic (agents skip due to low relevance)
- No relevant documents in RAG context
- Agent `should_respond()` method too strict

**Fix:**
```bash
# Use more specific queries
writeros chat "How long does it take to travel from A to B?" --vault-path ./path

# Check vault has documents
writeros stats
```

### Issue: Database Errors

**Symptoms:**
- Error: "relation 'agent_executions' does not exist"
- Error: "column 'output_data' does not exist"

**Fix:**
```bash
# Run all migrations
cd <project-root>
alembic upgrade head

# Or create tables manually
python << 'EOF'
from writeros.utils.db import init_db, engine
from writeros.schema.agent_execution import AgentExecution, AgentExecutionLog
from sqlmodel import SQLModel

# Create all tables
SQLModel.metadata.create_all(engine)
print("✅ Tables created")
EOF
```

---

## Performance Testing

### Measure Response Time

```bash
# Time the query
time writeros chat "Test query about timeline conflicts" --vault-path ./path

# Expected: < 10 seconds total
```

### Check Stage Durations

```bash
# View execution to see stage breakdown
writeros view-execution <id>

# Look for:
# - RAG retrieval: < 2 seconds
# - Agent broadcast: < 5 seconds
# - Output building: < 1 second
```

### Load Testing (Optional)

```bash
# Run multiple queries in sequence
for i in {1..5}; do
  echo "Query $i"
  writeros chat "Query $i: timeline conflicts" --vault-path ./path
  sleep 2
done

# Check tracking stats
writeros tracking-stats --hours 1
```

---

## Automated Testing (For Developers)

### Unit Test

Create `tests/test_dual_mode_output.py`:

```python
import pytest
from writeros.agents.orchestrator import OrchestratorAgent
from pydantic import BaseModel

class MockTimelineExtraction(BaseModel):
    events: list
    continuity_notes: str

def test_structured_summary_chronologist():
    """Test chronologist output formatting."""
    orchestrator = OrchestratorAgent(enable_tracking=False)

    mock_results = {
        "chronologist": MockTimelineExtraction(
            events=[
                {"title": "Event 1", "order": 1, "summary": "First"},
                {"title": "Event 2", "order": 2, "summary": "Second"}
            ],
            continuity_notes="Timeline conflict"
        )
    }

    summary = orchestrator._build_structured_summary(mock_results)

    assert "📊 SYSTEMATIC ANALYSIS" in summary
    assert "⏱️ TIMELINE ANALYSIS" in summary
    assert "Event 1" in summary
    assert "Timeline conflict" in summary

def test_structured_summary_empty():
    """Test with no agent results."""
    orchestrator = OrchestratorAgent(enable_tracking=False)
    summary = orchestrator._build_structured_summary({})
    assert summary == ""

def test_structured_summary_skipped_agents():
    """Test with agents that skipped."""
    orchestrator = OrchestratorAgent(enable_tracking=False)

    mock_results = {
        "chronologist": {"skipped": True, "reason": "Low relevance"}
    }

    summary = orchestrator._build_structured_summary(mock_results)
    assert summary == ""  # Skipped agents don't generate output
```

Run tests:
```bash
pytest tests/test_dual_mode_output.py -v
```

### Integration Test

Create `tests/integration/test_asoiaf.py`:

```python
import pytest
from writeros.agents.orchestrator import OrchestratorAgent
from uuid import uuid4

@pytest.mark.asyncio
async def test_asoiaf_stress_test(test_vault_id):
    """Full ASOIAF stress test."""
    orchestrator = OrchestratorAgent(enable_tracking=True)

    query = (
        "I'm revising ASOIAF Book 1. Catelyn discusses Jon Arryn's final words "
        "with Maester Luwin at Winterfell, sends letter to Ned before Littlefinger scene. "
        "What breaks?"
    )

    output = ""
    async for chunk in orchestrator.process_chat(query, vault_id=test_vault_id):
        output += chunk

    # Assertions
    assert "## 📊 SYSTEMATIC ANALYSIS" in output
    assert "## 💬 NARRATIVE SUMMARY" in output
    assert "⏱️ TIMELINE" in output or "⏱️ TIMELINE ANALYSIS" in output
    assert "days" in output.lower()  # Should mention timeline

    # Check tracking
    from writeros.utils.execution_analytics import ExecutionAnalytics
    recent = ExecutionAnalytics.get_recent_executions(vault_id=test_vault_id, limit=1)
    assert len(recent) == 1
    assert recent[0].status == "success"
```

Run integration tests:
```bash
pytest tests/integration/test_asoiaf.py -v -s
```

---

## Success Criteria

### Minimum Viable Test (Must Pass)

- [ ] Code runs without errors
- [ ] Output contains "📊 SYSTEMATIC ANALYSIS"
- [ ] Output contains "💬 NARRATIVE SUMMARY"
- [ ] `writeros tracking-stats` shows execution
- [ ] Database has agent_executions record

### Full Test (Should Pass)

- [ ] Structured summary shows agent-specific sections
- [ ] Timeline analysis appears (if Chronologist responds)
- [ ] Narrative summary is coherent prose
- [ ] No 200-character truncation
- [ ] Execution tracking shows all stages
- [ ] CLI commands work (tracking-stats, view-execution)

### ASOIAF Stress Test (Nice to Have)

- [ ] Shows specific timeline conflict (14 days vs 7 days)
- [ ] Shows travel distance (850 km)
- [ ] Shows affected chapters
- [ ] Narrative integrates metrics naturally
- [ ] Response time < 10 seconds

---

## Quick Troubleshooting Checklist

When things don't work:

1. **Check database:** `psql $DATABASE_URL -c "SELECT COUNT(*) FROM vaults;"`
2. **Check vault:** `writeros stats`
3. **Check tracking:** `writeros tracking-stats`
4. **Check logs:** `export LOG_LEVEL=DEBUG` and re-run
5. **Check migrations:** `alembic current` (should not be empty)
6. **Check Python version:** `python --version` (should be 3.11+)
7. **Check environment:** `echo $DATABASE_URL` (should not be empty)

---

## Getting Help

If tests fail:

1. **Check logs:**
   ```bash
   export LOG_LEVEL=DEBUG
   writeros chat "test" --vault-path ./path 2>&1 | tee debug.log
   ```

2. **Check database:**
   ```bash
   psql $DATABASE_URL
   \dt agent_*
   SELECT * FROM agent_executions ORDER BY created_at DESC LIMIT 1;
   ```

3. **Report issue with:**
   - Error message
   - Full command run
   - Database query results
   - Log output

---

## Next Steps After Testing

Once tests pass:

1. **Validate with real queries** - Try different types of queries
2. **Tune agent formatters** - Add more agent-specific extractions
3. **Implement Phase 2** - Solution validation with Provenance
4. **Add user controls** - Output mode flags
5. **Set up monitoring** - Automated health checks

---

**Dev1 | 2025-11-26**
