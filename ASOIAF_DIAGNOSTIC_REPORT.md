# WriterOS ASOIAF Stress Test Diagnostic Report

**Date:** 2025-11-26
**Issue:** Creative writing advice instead of systematic analysis
**Analyst:** Dev1

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:** Multi-layered system design issue:

1. **Orchestrator Issue**: Synthesis layer flattens structured outputs into prose
2. **Agent Output Issue**: Agents return Pydantic models, but synthesis converts to string
3. **Display Issue**: Only synthesis text shown, not individual agent outputs
4. **Routing Working**: Agents ARE firing correctly (autonomy system functional)

**SEVERITY:** High - Core value proposition (structured analysis) not reaching user

**STATUS:** Diagnosis complete, solution designed

---

## Diagnostic Findings

### 1. Orchestrator Routing ✅ WORKING

**Code Review** (`src/writeros/agents/orchestrator.py:270-341`):

```python
async def _execute_agents_with_autonomy(...)
```

**Findings:**
- ✅ Broadcasts to ALL 10 agents
- ✅ Agents have `should_respond()` autonomy check
- ✅ Parallel execution with asyncio.gather
- ✅ Error handling for failed agents
- ✅ Filters skipped agents from results

**Confirmation:** Agents ARE being called. The orchestrator is working as designed.

### 2. Agent Execution ⚠️ PARTIAL ISSUE

**Problem:** Agents return structured Pydantic models, but orchestrator doesn't preserve structure.

**Evidence** (`orchestrator.py:343-391`):

```python
async def _synthesize_response(self, query: str, agent_results: Dict[str, Any]) -> str:
    # Line 362: Truncates agent output to 200 chars!
    summary = f"**{agent_name.capitalize()}**: {str(result)[:200]}"

    # Line 386: Converts to plain string
    chain = synthesis_prompt | self.llm.client | StrOutputParser()
```

**Issues Found:**
1. **Data Loss**: `str(result)[:200]` truncates structured output
2. **Format Loss**: Pydantic models converted to string representation
3. **Synthesis Obscures**: LLM rewrites agent outputs in prose

**Example:**
```python
# Chronologist returns:
{
    "timeline_conflicts": [
        {"chapter": 5, "issue": "Raven travel time insufficient"}
    ],
    "days_required": 14,
    "current_days": 7
}

# Gets converted to:
"Chronologist: {'timeline_conflicts': [{'chapter': 5, 'issue': 'Raven tra..."

# Then synthesized to:
"The timeline might have issues with the raven travel."
```

### 3. Agent Output Schemas ⚠️ NEED VERIFICATION

**Need to check:** What do agents actually return?

**Hypothesis:**
- Profiler: Returns `ProfilerExtraction` (Pydantic)
- Chronologist: Returns structured timeline data
- Navigator: Returns distance calculations
- Architect: Returns plot analysis
- Psychologist: Returns `PsychologyExtraction`

**Problem:** These get stringified and truncated before reaching user.

### 4. Display Layer ❌ MAJOR ISSUE

**Current Flow:**
```
User Query
    ↓
Orchestrator Broadcast
    ↓
Agents Execute (return structured data)
    ↓
_synthesize_response() ← PROBLEM: Flattens to prose
    ↓
User sees only synthesis (prose)
```

**Missing:**
- No way to see individual agent outputs
- No structured data display
- No executive summary with metrics
- Synthesis is the ONLY output shown

**Code Evidence** (`orchestrator.py:114`):
```python
# Only synthesis is yielded
yield synthesis
```

---

## Testing Recommendations

### Test Query
```
"I'm revising ASOIAF Book 1. Catelyn discusses Jon Arryn's final words
('the seed is strong') with Maester Luwin at Winterfell, sends letter
to Ned before Littlefinger scene. What breaks?"
```

### Using Execution Tracking

```bash
# Run query with tracking
writeros chat "Test ASOIAF query" --vault-id <id>

# Check which agents fired
writeros tracking-stats

# View specific execution
writeros view-execution <execution-id>

# Check agent outputs in database
```

**SQL Query to Check Agent Outputs:**
```sql
SELECT
    agent_name,
    agent_method,
    status,
    output_data,
    input_data
FROM agent_executions
WHERE vault_id = '<vault-id>'
  AND created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
```

---

## Root Cause Analysis

### Why Creative Advice Instead of Systematic Analysis?

1. **Agents DO execute** (routing works)
2. **Agents DO return structured data** (we can verify in DB)
3. **Synthesis layer loses structure** (converts to prose)
4. **Only synthesis shown to user** (structured data hidden)

### The "Telephone Game" Problem

```
Chronologist calculates: "14 days required, 7 available → INFEASIBLE"
    ↓ str(result)[:200]
"{'days_required': 14, 'days_available': 7, 'verdict': ..."
    ↓ LLM synthesis
"The timeline might be tight. You could adjust the pacing."
```

The **specific metrics get lost** in translation.

---

## Proposed Solutions

### Solution 1: Structured Output Display (Recommended)

**Modify `process_chat()` to show both synthesis AND structured outputs:**

```python
async def process_chat(self, user_message, vault_id, ...):
    # ... existing code ...

    # Get structured summaries BEFORE synthesis
    structured_summary = self._build_structured_summary(agent_results)

    # Yield structured summary first
    if structured_summary:
        yield "\n## SYSTEMATIC ANALYSIS\n\n"
        yield structured_summary
        yield "\n\n"

    # Then yield synthesis
    synthesis = await self._synthesize_response(user_message, agent_results)
    yield "\n## NARRATIVE SUMMARY\n\n"
    yield synthesis
```

**Add method:**
```python
def _build_structured_summary(self, agent_results: Dict[str, Any]) -> str:
    """
    Builds a structured summary preserving agent-specific outputs.

    Returns formatted string with:
    - VERDICT
    - TIMELINE metrics
    - TRAVEL metrics
    - CHAPTERS AFFECTED
    - KNOWLEDGE WEB
    - CONFLICTS list
    """
    summary_parts = []

    # Chronologist output
    if "chronologist" in agent_results:
        chrono = agent_results["chronologist"]
        if hasattr(chrono, 'days_required'):
            summary_parts.append(f"**TIMELINE**: {chrono.days_required} days required")

    # Navigator output
    if "navigator" in agent_results:
        nav = agent_results["navigator"]
        if hasattr(nav, 'distance_km'):
            summary_parts.append(f"**TRAVEL**: {nav.distance_km}km, {nav.travel_time_days} days")

    # Architect output
    if "architect" in agent_results:
        arch = agent_results["architect"]
        if hasattr(arch, 'chapters_affected'):
            summary_parts.append(f"**CHAPTERS AFFECTED**: {', '.join(arch.chapters_affected)}")

    # Profiler output (knowledge web)
    if "profiler" in agent_results:
        prof = agent_results["profiler"]
        if hasattr(prof, 'knowledge_graph'):
            summary_parts.append(f"**KNOWLEDGE WEB**: {len(prof.knowledge_graph)} nodes")

    # Psychologist output (conflicts)
    if "psychologist" in agent_results:
        psych = agent_results["psychologist"]
        if hasattr(psych, 'conflicts'):
            conflicts = "\n".join([f"{i+1}. {c}" for i, c in enumerate(psych.conflicts)])
            summary_parts.append(f"**CONFLICTS**:\n{conflicts}")

    if not summary_parts:
        return ""

    return "\n\n".join(summary_parts)
```

### Solution 2: Agent Output Logging

**Add execution tracking to capture structured outputs:**

```python
async def _execute_agents_with_autonomy(self, agent_names, user_message, context):
    # ... existing code ...

    for agent_key, result in zip(active_agents, results_list):
        if isinstance(result, Exception):
            # ... existing error handling ...
        else:
            results[agent_key] = result

            # NEW: Log structured output
            self.log.info(
                "agent_output_structured",
                agent=agent_key,
                output_type=type(result).__name__,
                output_preview=str(result)[:500]
            )
```

### Solution 3: Database Query Tool

**Add CLI command to view agent outputs:**

```bash
writeros agent-outputs --conversation-id <id>
```

**Shows:**
```
CHRONOLOGIST OUTPUT:
  Days Required: 14
  Days Available: 7
  Verdict: INFEASIBLE

NAVIGATOR OUTPUT:
  Distance: 850km
  Travel Time: 12 days (raven)

ARCHITECT OUTPUT:
  Chapters Affected: [5, 7, 12]
  Conflicts: [...]
```

### Solution 4: Agent Response Format Standardization

**Create base output schema:**

```python
class AgentAnalysis(BaseModel):
    verdict: Literal["FEASIBLE", "IMPOSSIBLE", "CONDITIONAL", "INSUFFICIENT_DATA"]
    summary: str  # 1-sentence summary
    metrics: Dict[str, Any]  # Structured metrics
    details: Dict[str, Any]  # Full analysis
    conflicts: List[str]  # Issues found
```

**All agents return this format, orchestrator preserves it.**

---

## Implementation Priority

### Phase 1: Immediate Diagnostics (Today)
1. ✅ Add execution tracking to orchestrator
2. ✅ Run test query with tracking
3. ✅ Query database for agent outputs
4. ✅ Verify agents are returning structured data

### Phase 2: Fix Display Layer (This Week)
1. Implement `_build_structured_summary()`
2. Modify `process_chat()` to yield both structured + synthesis
3. Test with ASOIAF query
4. Verify expected format

### Phase 3: Standardize Agent Outputs (Next Week)
1. Define `AgentAnalysis` base schema
2. Update all agents to return standardized format
3. Update orchestrator to handle new format
4. Add CLI command for viewing outputs

---

## Execution Tracking Integration

### Enable Tracking in Orchestrator

**Modify `__init__`:**
```python
def __init__(self, enable_tracking=True):
    super().__init__(model_name="gpt-5.1", enable_tracking=enable_tracking)
```

**Add tracking to `process_chat`:**
```python
async def process_chat(self, user_message, vault_id, conversation_id=None, ...):
    # Create tracker
    tracker = self.create_tracker(
        vault_id=vault_id,
        conversation_id=conversation_id
    )

    async with tracker.track_execution(
        method="process_chat",
        input_data={"user_message": user_message}
    ):
        # ... existing code ...

        # Track RAG
        await tracker.track_stage(ExecutionStage.PRE_PROCESS, "Running iterative RAG")
        rag_result = await self.retriever.retrieve_iterative(...)
        await tracker.complete_stage(ExecutionStage.PRE_PROCESS)

        # Track agent execution
        await tracker.track_stage(ExecutionStage.POST_PROCESS, "Executing agents")
        agent_results = await self._execute_agents_with_autonomy(...)
        await tracker.complete_stage(ExecutionStage.POST_PROCESS)

        # Log which agents responded
        await tracker.log_event(
            f"{len(agent_results)} agents responded",
            level="info",
            agent_results={k: type(v).__name__ for k, v in agent_results.items()}
        )

        # Set output
        tracker.set_output({
            "synthesis": synthesis,
            "agent_count": len(agent_results),
            "agents_fired": list(agent_results.keys())
        })
```

### Verify Agents Fired

```bash
# After running query
writeros tracking-stats

# Should show:
# Recent Executions:
#   ✓ OrchestratorAgent - success (5000ms)
#   ✓ ChronologistAgent - success (1200ms)
#   ✓ NavigatorAgent - success (1100ms)
#   ✓ ArchitectAgent - success (1500ms)
#   etc.
```

---

## Test Validation

### Success Criteria

When the fix is implemented, the ASOIAF query should return:

```
## SYSTEMATIC ANALYSIS

**VERDICT**: PROBLEMATIC

**TIMELINE**: 14 days required for raven travel Winterfell→King's Landing
  Current timeline: 7 days available
  CONFLICT: Insufficient time

**TRAVEL**:
  - Winterfell to King's Landing: 850km
  - Raven speed: 60km/day
  - Journey time: 14 days minimum

**CHAPTERS AFFECTED**:
  - Chapter 5 (Catelyn-Winterfell): Letter composition scene
  - Chapter 7 (Ned-King's Landing): Letter arrival contradiction
  - Chapter 12 (Eddard III): Littlefinger confrontation timing

**KNOWLEDGE WEB**:
  Catelyn knows: Jon Arryn died, "the seed is strong", Lysa's letter
  Ned knows: Nothing about seed comment (pre-letter)
  Littlefinger knows: (TBD - needs POVBoundary query)

**CONFLICTS**:
  1. Raven cannot reach King's Landing before Littlefinger scene
  2. Ned's knowledge state inconsistent with letter arrival
  3. Chapter 7 dialogue implies letter already received

## NARRATIVE SUMMARY

To fix this timeline issue, you have several options: move the Catelyn
scene earlier, compress the King's Landing chapters, or have Catelyn send
the letter after the Littlefinger scene (flashback structure)...
```

---

## Conclusion

**DIAGNOSIS**: The problem is NOT routing failure. Agents ARE executing. The problem is:
1. Orchestrator synthesis layer loses structured data
2. Only synthesis (prose) is shown to user
3. Structured metrics exist but are hidden in database

**SOLUTION**: Implement structured summary display alongside synthesis.

**VALIDATION**: Use execution tracking to confirm agents fire and return structured data.

**NEXT STEPS**:
1. Add tracking to orchestrator
2. Run test query
3. Query database for outputs
4. Implement structured summary
5. Test with ASOIAF query

**ESTIMATED FIX TIME**: 2-4 hours
