# AI Assistant Troubleshooting Protocol

## When User Reports an Error

### Step 1: Systematic Investigation (Socratic Method)

Use layered analysis to understand the problem deeply:

```
Layer 1: SYMPTOM
├─ What error message appears?
├─ What command/action triggered it?
└─ What was the expected behavior?

Layer 2: IMMEDIATE CAUSE
├─ What technical component failed?
├─ What does the stack trace reveal?
└─ What data/state caused the failure?

Layer 3: ROOT CAUSE
├─ Why did the immediate cause occur?
├─ What design/config led to this?
└─ What assumptions were violated?

Layer 4: CONTEXT
├─ Why did this happen now vs. before?
├─ What changed recently?
└─ Are there environmental factors?

Layer 5: PREVENTION
├─ How do we prevent recurrence?
├─ What can be automated/validated?
└─ What documentation is needed?
```

### Step 2: Leverage Internal Diagnostic Tools

**CRITICAL: Always use WriterOS's built-in diagnostic tools LIBERALLY before manual investigation.**

WriterOS has a comprehensive telemetry system built on SQLModel. These tools should be your FIRST step when troubleshooting:

#### 1. Execution Analytics (src/writeros/utils/execution_analytics.py)

**Purpose**: Query the internal database of agent runs to understand system health.

**Always run these diagnostics FIRST:**

```python
from writeros.utils.execution_analytics import ExecutionAnalytics

# 1. Check for recent failures (last 24 hours)
failed_executions = ExecutionAnalytics.get_failed_executions(hours=24)
for exec in failed_executions:
    print(f"Failed: {exec.agent_name} - {exec.error_message}")
    print(f"Stack trace: {exec.stack_trace}")

# 2. Find performance bottlenecks (agents taking >5 seconds)
slow_executions = ExecutionAnalytics.find_slow_executions(threshold_ms=5000)
for exec in slow_executions:
    print(f"Slow: {exec.agent_name} took {exec.execution_time_ms}ms")

# 3. Debug relevance scoring (why did agent skip?)
skipped = ExecutionAnalytics.get_skipped_executions()
for exec in skipped:
    print(f"Skipped: {exec.agent_name} - Relevance: {exec.relevance_score}")

# 4. Trace call chains (who called whom?)
call_chain = ExecutionAnalytics.get_execution_call_chain(execution_id="...")
print(f"Call tree: {call_chain}")

# 5. Find poor quality LLM responses
poor_quality = ExecutionAnalytics.get_poor_quality_responses()
for exec in poor_quality:
    print(f"Quality issue: {exec.agent_name} - {exec.validation_errors}")
```

**When to use each diagnostic:**
- **Crashes/Errors**: `get_failed_executions()` - Shows exact error traces
- **Slow performance**: `find_slow_executions()` - Identifies bottlenecks
- **Agent not running**: `get_skipped_executions()` - Shows relevance scoring decisions
- **Call flow unclear**: `get_execution_call_chain()` - Reconstructs execution tree
- **Bad LLM output**: `get_poor_quality_responses()` - Finds validation failures

#### 2. Execution Tracker (src/writeros/utils/agent_tracker.py)

**Purpose**: Real-time logging during agent execution (writes data that ExecutionAnalytics reads).

**Features automatically tracked:**
- Agent lifecycle stages (Init → Plan → Execute → Review)
- LLM response validation (JSON validity, hallucination checks, refusal detection)
- Exception capture with full stack traces
- Execution timing and performance metrics

**Use this when adding new diagnostic logging:**
```python
from writeros.utils.agent_tracker import ExecutionTracker

tracker = ExecutionTracker()
execution_id = tracker.track_agent_start(
    agent_name="MyAgent",
    vault_id=vault_id,
    inputs={"query": "..."}
)

# Track LLM responses (automatically validates)
tracker.track_llm_response(
    execution_id=execution_id,
    response=llm_output,
    model="gpt-4",
    tokens_used=1500
)
```

#### 3. Narrative Consistency (src/writeros/agents/mechanic.py)

**Purpose**: Checks for story-world contradictions (not code errors).

**MechanicAgent acts as a "linter" for narrative rules:**
- Magic system violations
- Character inconsistencies
- Timeline contradictions
- World-building errors

**Not typically used for code debugging, but useful for content quality issues.**

### Step 3: Manual Investigation Commands

**Only run these if diagnostic tools don't reveal the issue:**

```python
# 1. Verify actual configuration being used
from writeros.utils.db import engine
print(f"Database: {engine.url}")

# 2. Check database schema
SELECT column_name FROM information_schema.columns
WHERE table_name = 'tablename';

# 3. Compare expected vs actual
- Expected schema (from code)
- Actual schema (from database)
- Configuration files (.env, config.py)
- Environment variables (os.environ)
```

**Rule: ALWAYS check ExecutionAnalytics BEFORE manual debugging!**

### Step 3: Ask Clarifying Questions

Before proposing solutions:

1. "What specific command did you run?"
2. "Are you using any environment variable overrides?"
3. "When did this last work correctly?"
4. "Have you made any recent changes?"

### Step 4: Document in STAR Format

Always create/update documentation using STAR:

```markdown
## Issue: [Error Name/Description]

### Situation
- Date: YYYY-MM-DD
- Symptom: [Error message]
- Context: [What user was trying to do]
- Environment: [OS, Python version, etc.]

### Task
- [What needed to be fixed]
- [Success criteria]

### Action
#### Phase 1: Investigation
- [What you checked]
- [What you discovered]

#### Phase 2: Root Cause Analysis
- Layer 1: [Symptom]
- Layer 2: [Immediate cause]
- Layer 3: [Root cause]
- Layer 4: [Why it happened]
- Layer 5: [Prevention]

#### Phase 3: Solution
- [Step 1]
- [Step 2]
- [Step 3]

### Result
- ✅ [What now works]
- ✅ [What was fixed]
- 📊 [Metrics/verification]
```

## Common Pitfalls to Avoid

### ❌ DON'T:
- **Skip ExecutionAnalytics diagnostics** - This is the #1 mistake!
- Jump to solutions without root cause analysis
- Assume the obvious explanation is correct
- Make changes without understanding why
- Forget to document the fix
- Miss environment variable overrides
- Ignore multiple database instances
- Skip schema verification
- **Manually debug before checking telemetry database**

### ✅ DO:
- **ALWAYS run ExecutionAnalytics diagnostics FIRST** (get_failed_executions, find_slow_executions, etc.)
- **Use diagnostic tools LIBERALLY** - they're designed for this
- Use Socratic method to dig deeper
- Verify assumptions with commands
- Check environment variables
- Compare expected vs actual state
- Document in STAR format
- Create prevention guidelines
- Add quick reference commands
- **Double-check by running multiple diagnostic queries**

## Quick Start: System Health Check

**Copy-paste this script FIRST when troubleshooting ANY issue:**

```python
# Quick System Health Diagnostic
# Run this immediately when user reports a problem

from writeros.utils.execution_analytics import ExecutionAnalytics
from writeros.utils.db import engine

print("=" * 60)
print("WRITEROS SYSTEM HEALTH CHECK")
print("=" * 60)

# 1. Database Connection
print(f"\n[DATABASE]")
print(f"Connected to: {engine.url.render_as_string(hide_password=True)}")

# 2. Recent Failures (last 24 hours)
print(f"\n[RECENT FAILURES]")
failed = ExecutionAnalytics.get_failed_executions(hours=24)
if failed:
    print(f"Found {len(failed)} failures:")
    for exec in failed[:5]:  # Show first 5
        print(f"  - {exec.agent_name}: {exec.error_message[:100]}")
else:
    print("No failures in last 24 hours")

# 3. Performance Issues
print(f"\n[PERFORMANCE]")
slow = ExecutionAnalytics.find_slow_executions(threshold_ms=5000)
if slow:
    print(f"Found {len(slow)} slow executions (>5s):")
    for exec in slow[:5]:
        print(f"  - {exec.agent_name}: {exec.execution_time_ms}ms")
else:
    print("No slow executions detected")

# 4. Skipped Agents (relevance scoring)
print(f"\n[SKIPPED AGENTS]")
skipped = ExecutionAnalytics.get_skipped_executions()
if skipped:
    print(f"Found {len(skipped)} skipped executions:")
    for exec in skipped[:5]:
        print(f"  - {exec.agent_name}: relevance={exec.relevance_score}")
else:
    print("No skipped executions")

# 5. LLM Quality Issues
print(f"\n[LLM QUALITY]")
poor = ExecutionAnalytics.get_poor_quality_responses()
if poor:
    print(f"Found {len(poor)} quality issues:")
    for exec in poor[:5]:
        print(f"  - {exec.agent_name}: {exec.validation_errors}")
else:
    print("No quality issues detected")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE - Review findings above")
print("=" * 60)
```

**This script is saved as `diagnostic_health_check.py` in the project root.**

**Run it immediately:**
```bash
python diagnostic_health_check.py
```

This provides instant visibility into:
- Database connectivity issues
- Recent agent failures with stack traces
- Performance bottlenecks
- Relevance scoring problems
- LLM validation failures

## Database Issues - Specific Protocol

### Always Check:
1. **Which database is being used?**
   ```python
   from writeros.utils.db import engine
   print(engine.url)  # Actual connection
   ```

2. **Environment variable overrides?**
   ```bash
   # Check PowerShell
   Get-Item Env:DATABASE_URL

   # Check .env file
   cat .env | grep DATABASE_URL
   ```

3. **Schema matches code?**
   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_name = 'entities';
   ```

4. **Multiple instances running?**
   - Check all ports (5432, 5433, etc.)
   - Verify which has correct schema
   - Document which to use

## Documentation Standards

### File Naming:
- `TROUBLESHOOTING.md` - Main troubleshooting guide
- `TROUBLESHOOTING_PROTOCOL.md` - This file (for AI assistants)
- `docs/issues/ISSUE_YYYY_MM_DD_[name].md` - Individual issue docs

### Required Sections:
1. **STAR Format** (Situation, Task, Action, Result)
2. **Lessons Learned**
3. **Prevention Guidelines**
4. **Quick Reference** (copy-paste commands)
5. **Related Issues** (cross-references)

### Quick Reference Template:
```markdown
## Quick Reference

### Check [Something]
\`\`\`bash
command here
\`\`\`

### Expected Output
\`\`\`
what you should see
\`\`\`

### Fix If Wrong
\`\`\`bash
fix command here
\`\`\`
```

## Examples

### Good Investigation Flow (WITH DIAGNOSTICS):

```
User: "Getting entity_type error"
↓
Step 1: Run ExecutionAnalytics.get_failed_executions(hours=24)
↓
Found: 15 failures with same error, all in RAGRetriever
↓
Step 2: Check stack traces from telemetry
↓
Layer 1: Error message → column entities.entity_type doesn't exist
↓
Layer 2: Check database schema → has 'type' not 'entity_type'
↓
Layer 3: Why wrong schema? → checking multiple DBs
↓
Layer 4: Found two databases on different ports (via env check)
↓
Layer 5: Check which is being used → env var override!
↓
Solution: Remove env override, use .env file
↓
Verify: Run get_failed_executions() again → 0 errors
↓
Document: STAR format in TROUBLESHOOTING.md + diagnostic patterns
```

### Bad Investigation Flow (WITHOUT DIAGNOSTICS):

```
User: "Getting entity_type error"
↓
Assume: Database needs migration (didn't check telemetry!)
↓
Run: alembic upgrade head
↓
Still broken: Not the real problem
↓
No telemetry check: Missed pattern of 15 identical failures
↓
No root cause: Just guessing solutions
↓
No documentation: Can't prevent recurrence
```

## Template Responses

### When User Reports Error:

```markdown
I'll investigate this systematically using WriterOS's diagnostic tools and the Socratic method.

**Step 1 - Check Telemetry Database:**
Let me run ExecutionAnalytics diagnostics first:

[Run get_failed_executions(), find_slow_executions(), etc.]

**Step 2 - Socratic Analysis:**

**Layer 1 - Understanding the Symptom:**
[Analyze error from telemetry + user report]

**Layer 2 - Immediate Cause:**
[Identify technical failure point from stack traces]

**Layer 3 - Root Cause:**
[Determine why failure occurred using diagnostic data]

[Continue with Layers 4-5...]

**Step 3 - Additional Diagnostics:**
[Run manual investigation commands if needed]
```

### After Fixing:

```markdown
✅ FIXED! Here's what happened:

**Root Cause:** [Brief explanation]

**Solution Applied:** [What was done]

**How to Prevent:**
- [Guideline 1]
- [Guideline 2]

**Documentation Created:**
- TROUBLESHOOTING.md updated with STAR format
- Quick reference commands added
- Prevention guidelines documented

**To verify it's working:**
\`\`\`bash
[verification command]
\`\`\`
```

## Checklist Before Closing Issue

- [ ] **Ran ExecutionAnalytics diagnostics** (get_failed_executions, etc.)
- [ ] **Checked telemetry database for patterns**
- [ ] Root cause identified (not just symptom)
- [ ] Solution tested and verified
- [ ] STAR documentation created/updated
- [ ] Prevention guidelines added
- [ ] Quick reference commands provided
- [ ] Related issues cross-referenced
- [ ] User understands how to prevent recurrence
- [ ] **Verified fix doesn't appear in future ExecutionAnalytics queries**

## Remember:

> "The goal is not just to fix the problem, but to ensure it never happens again and to make the next debugging session faster."

**Always - In This Order:**
1. **RUN EXECUTIONANALYTICS DIAGNOSTICS FIRST** - This is mandatory!
2. **Use diagnostic tools liberally** - They're your primary investigation method
3. Think in layers (Socratic method) - Analyze telemetry data systematically
4. Verify assumptions with commands - Double-check diagnostic findings
5. Document in STAR format - Include which diagnostics revealed the issue
6. Create prevention guidelines - Mention diagnostic patterns to watch
7. Provide quick reference - Include diagnostic commands

**Critical Rule:**
> "Never manually debug before checking ExecutionAnalytics. The telemetry database knows what happened - use it!"

**Diagnostic-First Workflow:**
```
Error Reported
    ↓
1. get_failed_executions() - What crashed?
    ↓
2. get_execution_call_chain() - What led to it?
    ↓
3. find_slow_executions() - Performance issue?
    ↓
4. get_poor_quality_responses() - LLM problem?
    ↓
5. Socratic analysis of diagnostic data
    ↓
6. Manual investigation ONLY if diagnostics unclear
    ↓
7. Document in STAR format
```

**Last Updated**: 2025-11-28
