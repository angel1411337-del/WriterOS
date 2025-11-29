# WriterOS Approved Refactor Plan
**Date:** 2025-11-27
**Status:** ✅ APPROVED with Adjustments
**Approved By:** Product Owner

---

## Executive Decisions

### ✅ **GREEN LIGHT - Execute Immediately**
Memory & Sync systems (diskcache, python-frontmatter, watchdog)

### 🔄 **PIVOT - TensorFlow → NetworkX**
Replace heavy ML with lightweight graph algorithms

### ⏩ **PULL FORWARD - LangGraph for Mechanic Veto**
Use LangGraph specifically for human-in-the-loop workflows (Phase 3)

---

## Phase 1: Memory & Sync Foundation (Week 1) - **START NOW**

### 1.1 DiskCache Integration (3 hours)

**File:** `src/writeros/agents/base.py`

**Implementation:**
```python
from diskcache import Cache
from pathlib import Path

class BaseAgent:
    def __init__(self, model_name="gpt-4", enable_tracking=True):
        # Existing init...

        # Add persistent scratchpad
        cache_dir = Path('.writeros/scratchpad')
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.scratchpad = Cache(str(cache_dir))

    def remember(self, key: str, value: Any, expire: int = 3600) -> None:
        """Store transient thought with TTL (default 1 hour)"""
        agent_key = f"{self.__class__.__name__}:{key}"
        self.scratchpad.set(agent_key, value, expire=expire)

    def recall(self, key: str, default=None) -> Any:
        """Retrieve cached thought"""
        agent_key = f"{self.__class__.__name__}:{key}"
        return self.scratchpad.get(agent_key, default)

    def forget(self, key: str) -> None:
        """Clear specific memory"""
        agent_key = f"{self.__class__.__name__}:{key}"
        self.scratchpad.delete(agent_key)
```

**Usage Example (in any agent):**
```python
class ChronologistAgent(BaseAgent):
    async def run(self, query, vault_id):
        # Check if we've recently analyzed this timeline
        cached = self.recall(f"timeline:{vault_id}")
        if cached:
            logger.info("Using cached timeline analysis")
            return cached

        # Perform analysis
        result = await self._analyze_timeline(query, vault_id)

        # Cache for 30 minutes
        self.remember(f"timeline:{vault_id}", result, expire=1800)
        return result
```

**Testing:**
```bash
# Verify cache persistence
pytest tests/test_scratchpad.py -v
```

**Acceptance Criteria:**
- ✅ Agent state survives restart
- ✅ TTL expiration works correctly
- ✅ Cache keys are namespaced by agent class

---

### 1.2 Python-Frontmatter Integration (1 hour)

**File:** `src/writeros/utils/indexer.py`

**Current (Brittle):**
```python
def extract_metadata(file_path):
    with open(file_path) as f:
        content = f.read()

    metadata = {}
    if content.startswith('---'):
        # Regex nightmare for YAML extraction
        yaml_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if yaml_match:
            metadata = yaml.safe_load(yaml_match.group(1))
```

**New (Robust):**
```python
import frontmatter

def extract_metadata(file_path):
    """Robust YAML frontmatter extraction"""
    post = frontmatter.load(file_path)
    return {
        'metadata': post.metadata,  # Dict of YAML fields
        'content': post.content,    # Clean markdown body
        'file_path': file_path
    }

def update_metadata(file_path, new_metadata):
    """Update frontmatter without corrupting file"""
    post = frontmatter.load(file_path)
    post.metadata.update(new_metadata)

    # Write back with formatting preserved
    with open(file_path, 'wb') as f:
        frontmatter.dump(post, f)
```

**Testing:**
```python
# tests/test_frontmatter.py
def test_nested_yaml_extraction():
    """Ensure complex YAML structures parse correctly"""
    content = """---
temporal_tags:
  - date: 298 AC
    era: War of Five Kings
character_states:
  Jon Snow:
    location: Castle Black
    health: 85
---
# Scene Content
"""
    result = extract_metadata(content)
    assert result['metadata']['temporal_tags'][0]['date'] == '298 AC'
```

**Migration:**
```bash
# Replace all regex parsing in one pass
grep -r "startswith('---')" src/writeros/utils/ | wc -l  # Find occurrences
# Then replace with frontmatter.load()
```

**Acceptance Criteria:**
- ✅ Handles nested YAML
- ✅ Preserves formatting on round-trip
- ✅ No data loss on edge cases (quotes, colons, etc.)

---

### 1.3 Watchdog Live Sync (1 day)

**File:** `src/writeros/services/watcher.py` (NEW)

**Implementation:**
```python
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import defaultdict
from datetime import datetime
import structlog

logger = structlog.get_logger()

class VaultWatcher(FileSystemEventHandler):
    """Shadow Scribe: Real-time vault synchronization"""

    def __init__(self, vault_path: str, indexer, debounce_seconds: float = 2.0):
        self.vault_path = vault_path
        self.indexer = indexer
        self.debounce_seconds = debounce_seconds
        self.debounce_timers = defaultdict(lambda: None)
        self.loop = asyncio.get_event_loop()

    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return

        # Only process markdown files
        if not event.src_path.endswith('.md'):
            return

        logger.info("file_modified", path=event.src_path)

        # Cancel existing timer for this file
        if self.debounce_timers[event.src_path]:
            self.debounce_timers[event.src_path].cancel()

        # Schedule new index after debounce delay
        timer = asyncio.create_task(
            self._index_after_delay(event.src_path)
        )
        self.debounce_timers[event.src_path] = timer

    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory or not event.src_path.endswith('.md'):
            return

        logger.info("file_created", path=event.src_path)
        asyncio.create_task(self._index_after_delay(event.src_path, delay=0.5))

    def on_deleted(self, event):
        """Handle file deletion"""
        if event.is_directory or not event.src_path.endswith('.md'):
            return

        logger.info("file_deleted", path=event.src_path)
        asyncio.create_task(self._remove_from_index(event.src_path))

    async def _index_after_delay(self, file_path: str, delay: float = None):
        """Index file after debounce delay"""
        await asyncio.sleep(delay or self.debounce_seconds)

        try:
            await self.indexer.index_file(file_path)
            logger.info("sync_complete", path=file_path, timestamp=datetime.now())
        except Exception as e:
            logger.error("sync_failed", path=file_path, error=str(e))

    async def _remove_from_index(self, file_path: str):
        """Remove deleted file from database"""
        # Extract file hash or path-based ID
        # Delete from Document table
        pass

def start_vault_watcher(vault_path: str, indexer):
    """Start background file watcher"""
    event_handler = VaultWatcher(vault_path, indexer)
    observer = Observer()
    observer.schedule(event_handler, vault_path, recursive=True)
    observer.start()

    logger.info("shadow_scribe_started", vault_path=vault_path)
    return observer

def stop_vault_watcher(observer):
    """Graceful shutdown"""
    observer.stop()
    observer.join()
    logger.info("shadow_scribe_stopped")
```

**CLI Integration:**
```python
# src/writeros/cli/main.py
@app.command()
def watch(
    vault_path: str = typer.Option(None, help="Path to vault"),
    debounce: float = typer.Option(2.0, help="Debounce delay in seconds")
):
    """Start Shadow Scribe (live file sync)"""
    from writeros.services.watcher import start_vault_watcher
    from writeros.utils.indexer import VaultIndexer

    indexer = VaultIndexer()
    observer = start_vault_watcher(vault_path, indexer, debounce)

    try:
        print(f"👁️ Watching {vault_path} (Ctrl+C to stop)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_vault_watcher(observer)
```

**Usage:**
```bash
# Run in background or as systemd service
writeros watch --vault-path "C:\Users\rahme\Desktop\Genius Loci"

# Or auto-start with ingest
writeros ingest --vault-path ./vault --watch
```

**Acceptance Criteria:**
- ✅ Detects file changes within 2 seconds
- ✅ Debouncing prevents thrashing during rapid edits
- ✅ Works across Windows/Mac/Linux
- ✅ Graceful shutdown on Ctrl+C

---

### Phase 1 Summary

**Timeline:** **1 week**
**Risk:** **LOW**
**Dependencies:**
```txt
diskcache>=5.6.3
python-frontmatter>=1.1.0
watchdog>=4.0.0
```

**Deliverables:**
1. ✅ Agent scratchpad with TTL
2. ✅ Robust metadata parsing
3. ✅ Real-time vault sync ("Shadow Scribe")

---

## Phase 2: NetworkX Intelligence (Week 2) - **PIVOT FROM TENSORFLOW**

### 2.1 Theorist Link Prediction (NetworkX)

**Decision:** Use lightweight graph algorithms instead of GNN

**File:** `src/writeros/agents/theorist.py`

**Implementation:**
```python
import networkx as nx
from typing import List, Tuple

class TheoristAgent(BaseAgent):
    """Analyzes narrative patterns and predicts story developments"""

    def predict_missing_links(
        self,
        graph: nx.Graph,
        limit: int = 10
    ) -> List[Tuple[str, str, float]]:
        """
        Predict likely future relationships using Adamic-Adar Index.

        No ML required - uses graph topology heuristics.
        """
        # Get all non-connected node pairs
        non_edges = list(nx.non_edges(graph))

        # Calculate Adamic-Adar score for each potential link
        predictions = nx.adamic_adar_index(graph, non_edges)

        # Sort by score and return top predictions
        sorted_predictions = sorted(
            predictions,
            key=lambda x: x[2],
            reverse=True
        )[:limit]

        return [
            {
                'source': u,
                'target': v,
                'score': score,
                'interpretation': self._interpret_link(u, v, score, graph)
            }
            for u, v, score in sorted_predictions
        ]

    def _interpret_link(self, u, v, score, graph):
        """Generate narrative explanation"""
        common_neighbors = list(nx.common_neighbors(graph, u, v))

        if score > 2.0:
            return f"High likelihood: {u} and {v} share {len(common_neighbors)} connections"
        elif score > 1.0:
            return f"Possible alliance: Mutual associates include {', '.join(common_neighbors[:3])}"
        else:
            return f"Weak connection: Minimal shared context"

    def detect_factions(self, graph: nx.Graph) -> Dict[str, List[str]]:
        """Identify communities (factions/alliances)"""
        from networkx.algorithms import community

        # Louvain method (fast, deterministic)
        communities = community.louvain_communities(graph)

        factions = {}
        for i, faction in enumerate(communities):
            factions[f"Faction_{i+1}"] = list(faction)

        return factions

    def find_key_brokers(self, graph: nx.Graph, top_n: int = 5) -> List[Dict]:
        """Identify characters who bridge disconnected groups"""
        betweenness = nx.betweenness_centrality(graph)

        sorted_nodes = sorted(
            betweenness.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [
            {
                'character': node,
                'broker_score': score,
                'interpretation': f"Controls information flow between {graph.degree(node)} factions"
            }
            for node, score in sorted_nodes
        ]
```

**API Response Example:**
```json
{
  "predicted_alliances": [
    {
      "source": "Jon Snow",
      "target": "Daenerys",
      "score": 3.2,
      "interpretation": "High likelihood: Share 5 connections (Tyrion, Varys...)"
    }
  ],
  "factions_detected": {
    "Faction_1": ["Starks", "Tullys", "Arryns"],
    "Faction_2": ["Lannisters", "Freys", "Boltons"]
  },
  "key_brokers": [
    {
      "character": "Littlefinger",
      "broker_score": 0.87,
      "interpretation": "Controls information flow between 4 factions"
    }
  ]
}
```

**No TensorFlow Required:**
- ✅ Same user value (predictions)
- ✅ Zero extra dependencies
- ✅ 100x faster (no model training)
- ✅ Deterministic results

---

### 2.2 Mechanic Logic Validator (Heuristic Rules)

**Decision:** Use Python rules instead of Decision Forests

**File:** `src/writeros/agents/mechanic.py`

**Implementation:**
```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class ViolationType(Enum):
    FATAL = "fatal"           # Breaks story logic
    WARNING = "warning"       # Suspicious but possible
    SUGGESTION = "suggestion" # Style/optimization hint

@dataclass
class ConsistencyViolation:
    type: ViolationType
    message: str
    affected_entities: List[str]
    suggested_fix: Optional[str]

class MechanicAgent(BaseAgent):
    """Logic and consistency validator"""

    VALIDATION_RULES = {
        'dead_character_acts': {
            'check': lambda c, s: c.status == 'dead' and s.character_id == c.id,
            'violation': ViolationType.FATAL,
            'message': "Dead character {character} cannot perform actions"
        },
        'health_threshold': {
            'check': lambda c, s: c.health < 10 and s.action in ['fights', 'runs', 'climbs'],
            'violation': ViolationType.WARNING,
            'message': "Character {character} at {health}% health performing strenuous action"
        },
        'location_mismatch': {
            'check': lambda c, s: c.location != s.location,
            'violation': ViolationType.FATAL,
            'message': "Character {character} at {c_loc}, scene at {s_loc}"
        },
        'impossible_travel': {
            'check': lambda prev_scene, curr_scene: self._check_travel_time(prev_scene, curr_scene),
            'violation': ViolationType.WARNING,
            'message': "Travel time insufficient: {distance}km in {time}h"
        }
    }

    async def validate_scene(
        self,
        scene,
        character_states,
        previous_scene=None
    ) -> List[ConsistencyViolation]:
        """Run all validation rules"""
        violations = []

        for rule_name, rule_def in self.VALIDATION_RULES.items():
            try:
                if rule_def['check'](character_states, scene):
                    violations.append(ConsistencyViolation(
                        type=rule_def['violation'],
                        message=rule_def['message'].format(
                            character=scene.character_id,
                            **character_states.__dict__
                        ),
                        affected_entities=[scene.character_id],
                        suggested_fix=self._generate_fix(rule_name, scene)
                    ))
            except Exception as e:
                logger.warning(f"Rule {rule_name} failed: {e}")

        return violations

    def _check_travel_time(self, prev_scene, curr_scene) -> bool:
        """Validate realistic travel between scenes"""
        if not prev_scene:
            return False

        # Calculate distance
        distance_km = self._haversine_distance(
            prev_scene.location,
            curr_scene.location
        )

        # Calculate time delta
        time_hours = (curr_scene.timestamp - prev_scene.timestamp).total_seconds() / 3600

        # Assume horseback travel (~8 km/h)
        required_hours = distance_km / 8

        return time_hours < required_hours * 0.8  # 20% grace margin

    def _generate_fix(self, rule_name, scene):
        """Suggest narrative fixes"""
        fixes = {
            'dead_character_acts': "Remove scene or revive character",
            'health_threshold': "Reduce action intensity or heal character",
            'location_mismatch': "Update character location or scene setting",
            'impossible_travel': "Add time skip or reduce distance"
        }
        return fixes.get(rule_name)
```

**No ML Required:**
- ✅ Clear, auditable rules
- ✅ Easy to customize per-universe
- ✅ No training data needed
- ✅ Instant validation

---

## Phase 3: LangGraph for Mechanic Veto (Month 2) - **PULLED FORWARD**

### 3.1 Human-in-the-Loop Workflow

**Reason for LangGraph:** Existing orchestrator cannot handle:
- ⏸️ **Pause/Resume:** Wait for user approval mid-execution
- 🔄 **Cycles:** Write → Critique → Revise loops
- 💾 **State Persistence:** Survive crashes during user review

**File:** `src/writeros/workflows/mechanic_veto.py` (NEW)

**LangGraph Implementation:**
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, Annotated
from operator import add

class MechanicVetoState(TypedDict):
    """Workflow state for write-review-approve cycle"""
    user_message: str
    vault_id: str

    # RAG context
    rag_documents: list

    # Generated content
    draft_content: str

    # Mechanic validation
    violations: list
    has_fatal_errors: bool

    # Human decision
    user_approved: bool
    user_feedback: str

    # Revision tracking
    revision_count: int
    max_revisions: int

    # Final output
    final_content: str

def run_rag_retrieval(state: MechanicVetoState) -> MechanicVetoState:
    """Step 1: Retrieve context"""
    retriever = RAGRetriever()
    results = await retriever.retrieve(
        query=state['user_message'],
        vault_id=state['vault_id']
    )
    state['rag_documents'] = results.documents
    return state

def generate_draft(state: MechanicVetoState) -> MechanicVetoState:
    """Step 2: Generate initial draft"""
    writer = ProducerAgent()
    draft = await writer.write_scene(
        prompt=state['user_message'],
        context=state['rag_documents']
    )
    state['draft_content'] = draft
    return state

def validate_consistency(state: MechanicVetoState) -> MechanicVetoState:
    """Step 3: Check for logic errors"""
    mechanic = MechanicAgent()
    violations = await mechanic.validate_content(state['draft_content'])

    state['violations'] = violations
    state['has_fatal_errors'] = any(
        v.type == ViolationType.FATAL for v in violations
    )
    return state

def request_user_review(state: MechanicVetoState) -> MechanicVetoState:
    """Step 4: Pause for human input"""
    print("\n⚠️ MECHANIC VETO TRIGGERED\n")
    print("Draft Content:")
    print(state['draft_content'])
    print("\nViolations Detected:")
    for v in state['violations']:
        print(f"  [{v.type.value}] {v.message}")

    # THIS IS WHERE LANGGRAPH PAUSES
    # State is saved to SQLite checkpoint
    # Can resume days later

    user_input = input("\nApprove anyway? (yes/no/revise): ").lower()

    if user_input == 'yes':
        state['user_approved'] = True
    elif user_input == 'revise':
        state['user_approved'] = False
        state['user_feedback'] = input("Revision instructions: ")
        state['revision_count'] += 1
    else:
        state['user_approved'] = False
        state['final_content'] = None  # Rejected

    return state

def revise_draft(state: MechanicVetoState) -> MechanicVetoState:
    """Step 5: Apply user feedback"""
    writer = ProducerAgent()
    revised = await writer.revise_scene(
        original=state['draft_content'],
        feedback=state['user_feedback'],
        violations=state['violations']
    )
    state['draft_content'] = revised
    return state

def finalize_output(state: MechanicVetoState) -> MechanicVetoState:
    """Step 6: Save approved content"""
    state['final_content'] = state['draft_content']
    print(f"\n✅ Content approved after {state['revision_count']} revisions")
    return state

def build_mechanic_veto_workflow():
    """Construct the state graph"""
    # Persistent checkpointing (survives crashes)
    checkpointer = SqliteSaver.from_conn_string(".writeros/checkpoints.db")

    workflow = StateGraph(MechanicVetoState)

    # Add nodes
    workflow.add_node("rag", run_rag_retrieval)
    workflow.add_node("draft", generate_draft)
    workflow.add_node("validate", validate_consistency)
    workflow.add_node("user_review", request_user_review)
    workflow.add_node("revise", revise_draft)
    workflow.add_node("finalize", finalize_output)

    # Linear flow up to validation
    workflow.set_entry_point("rag")
    workflow.add_edge("rag", "draft")
    workflow.add_edge("draft", "validate")

    # Conditional branching after validation
    workflow.add_conditional_edges(
        "validate",
        lambda s: "review" if s['has_fatal_errors'] else "finalize",
        {
            "review": "user_review",
            "finalize": "finalize"
        }
    )

    # After user review: approve, revise, or reject
    workflow.add_conditional_edges(
        "user_review",
        lambda s: (
            "finalize" if s['user_approved'] else
            "revise" if s['revision_count'] < s['max_revisions'] else
            END
        ),
        {
            "finalize": "finalize",
            "revise": "revise"
        }
    )

    # After revision: re-validate
    workflow.add_edge("revise", "validate")

    # Terminal node
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)

# Usage
graph = build_mechanic_veto_workflow()

# Start execution
config = {"configurable": {"thread_id": "session_123"}}
result = await graph.ainvoke({
    "user_message": "Write a battle scene where Jon defeats 10 soldiers",
    "vault_id": vault_id,
    "revision_count": 0,
    "max_revisions": 3
}, config)

# Can resume later if interrupted
# graph.ainvoke(None, config)  # Continues from last checkpoint
```

**Why LangGraph is Necessary Here:**

| Feature | `asyncio.gather()` | LangGraph |
|---------|-------------------|-----------|
| Parallel execution | ✅ | ✅ |
| Sequential steps | ✅ | ✅ |
| **Pause for user input** | ❌ | ✅ |
| **State persistence** | ❌ | ✅ |
| **Cycles (revise loop)** | ⚠️ Manual | ✅ |
| **Resume after crash** | ❌ | ✅ |

**Acceptance Criteria:**
- ✅ Workflow pauses at user review
- ✅ State persists across restarts
- ✅ Handles up to 3 revision cycles
- ✅ Visual graph export for debugging

---

## Updated Timeline

| Phase | Task | Effort | Start | End |
|-------|------|--------|-------|-----|
| 1 | DiskCache | 3h | Week 1 Mon | Week 1 Mon |
| 1 | Frontmatter | 1h | Week 1 Mon | Week 1 Mon |
| 1 | Watchdog | 1d | Week 1 Tue | Week 1 Wed |
| 2 | NetworkX Theorist | 2d | Week 2 Mon | Week 2 Tue |
| 2 | Heuristic Mechanic | 1d | Week 2 Wed | Week 2 Wed |
| 3 | LangGraph Veto | 3d | Month 2 | Month 2 |

**Total: 8 days** (vs original 3 weeks)

---

## Updated Dependencies

```txt
# requirements.txt additions

# Phase 1: Memory & Sync
diskcache>=5.6.3
python-frontmatter>=1.1.0
watchdog>=4.0.0

# Phase 2: Graph Intelligence (NetworkX already installed)
# No new dependencies - using existing networkx

# Phase 3: Human-in-the-Loop
langgraph>=0.2.0
langgraph-checkpoint-sqlite>=0.1.0

# NOT ADDING:
# tensorflow - rejected
# tf-gnn - rejected
# tensorflow-decision-forests - rejected
# mem0ai - deferred to later phase
```

---

## Success Metrics

### Phase 1 (Memory & Sync)
- ✅ Agent memory survives restart (verify with test)
- ✅ Metadata parsing handles 100% of vault files without errors
- ✅ Files sync within 2 seconds of save in Obsidian

### Phase 2 (NetworkX Intelligence)
- ✅ Theorist predicts ≥5 plausible character relationships
- ✅ Mechanic detects fatal errors (dead character acting, etc.)
- ✅ Zero TensorFlow dependencies added

### Phase 3 (LangGraph Veto)
- ✅ User can approve/reject/revise generated content
- ✅ Workflow resumes correctly after interruption
- ✅ Maximum 3 revision cycles enforced

---

## Next Actions

1. ✅ **Approve this plan** (awaiting confirmation)
2. 🔨 **Install Phase 1 dependencies**
   ```bash
   pip install diskcache python-frontmatter watchdog
   ```
3. 🧪 **Create test suite** for scratchpad persistence
4. 📝 **Update ai_context.md** with approved changes
5. 🚀 **Begin implementation** (Monday morning)

**Prepared by:** Dev Team
**Approved by:** Product Owner (2025-11-27)
**Status:** ✅ READY TO EXECUTE
