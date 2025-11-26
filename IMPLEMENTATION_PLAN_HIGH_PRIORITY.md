# HIGH-PRIORITY IMPLEMENTATION PLAN
## Provenance System Integration & Entity Deduplication

**Document Version:** 1.0
**Date:** 2025-11-26
**Estimated Total Effort:** 3-4 weeks
**Business Impact:** Critical - Enables time-travel queries and solves duplicate entity problem

---

## EXECUTIVE SUMMARY

This document provides a step-by-step implementation plan for the two highest-value dormant systems:

1. **Provenance System Integration** (Week 1-2)
   - Enable time-travel queries ("What did we know in Chapter 5?")
   - Track character knowledge vs objective truth
   - Detect retcon impact automatically
   - **Value:** Core feature for narrative consistency

2. **Entity Deduplication System** (Week 3-4)
   - Auto-detect duplicate entities ("Strider" = "Aragorn")
   - ML-based similarity scoring
   - User-approved merge workflow
   - **Value:** Solves major pain point

---

# PHASE 1: PROVENANCE SYSTEM INTEGRATION

**Timeline:** Week 1-2 (10 working days)
**Effort:** ~60-80 hours
**Dependencies:** None (tables already exist)
**Risk:** Low (well-defined problem)

---

## Week 1: Foundation Layer

### Day 1-2: StateChangeEvent Integration

#### Objective
Log all entity state changes for time-travel replay.

#### Tasks

**1.1: Add StateChangeEvent to ProfilerAgent.find_or_create_entity()**

**File:** `src/writeros/agents/profiler.py`
**Lines:** After line 481 (after entity creation)

**Code to Add:**
```python
# Import at top of file
from writeros.schema.provenance import StateChangeEvent
from writeros.schema.enums import StateChangeEventType

# After entity is created and committed (line 481)
def find_or_create_entity(...):
    # ... existing code ...

    # NEW: Log entity creation as state change event
    if not existing_entity:  # Only if we created a new entity
        state_event = StateChangeEvent(
            vault_id=vault_id,
            entity_id=entity.id,
            event_type=StateChangeEventType.ATTRIBUTE_CHANGE,
            payload={
                "action": "entity_created",
                "entity_name": name,
                "entity_type": str(entity_type),
                "description": description,
                "metadata": metadata,
                "created_by": "profiler_agent"
            },
            world_timestamp=None,  # No story time context at creation
            narrative_sequence=None,
            source_scene_id=None,  # Created outside scene context
            dimension="reality"
        )
        session.add(state_event)
        session.commit()

        self.log.info(
            "entity_creation_logged",
            entity_id=str(entity.id),
            entity_name=name
        )
```

**Testing:**
```python
# Test file: tests/test_provenance_integration.py
def test_entity_creation_logs_state_change(session):
    profiler = ProfilerAgent()
    entity = profiler.find_or_create_entity(
        name="Jon Snow",
        entity_type=EntityType.CHARACTER,
        vault_id=test_vault_id,
        session=session
    )

    # Check StateChangeEvent was created
    events = session.exec(
        select(StateChangeEvent).where(
            StateChangeEvent.entity_id == entity.id
        )
    ).all()

    assert len(events) == 1
    assert events[0].event_type == StateChangeEventType.ATTRIBUTE_CHANGE
    assert events[0].payload["action"] == "entity_created"
    assert events[0].payload["entity_name"] == "Jon Snow"
```

**Acceptance Criteria:**
- ✅ Every new entity creates a StateChangeEvent
- ✅ Event includes entity name, type, description
- ✅ Event payload is valid JSON
- ✅ Test passes

---

**1.2: Add StateChangeEvent for Relationship Creation**

**File:** `src/writeros/agents/profiler.py`
**Method:** Add new method `log_relationship_change()`

**Code to Add:**
```python
def log_relationship_change(
    self,
    session: Session,
    vault_id: UUID,
    from_entity: Entity,
    to_entity: Entity,
    rel_type: RelationType,
    relationship_id: UUID,
    action: str = "relationship_added",
    scene_id: Optional[UUID] = None
):
    """
    Log relationship creation/deletion as state change event.

    Args:
        session: Database session
        vault_id: Vault ID
        from_entity: Source entity
        to_entity: Target entity
        rel_type: Relationship type
        relationship_id: ID of the relationship
        action: "relationship_added" or "relationship_removed"
        scene_id: Scene where this relationship was established (if any)
    """
    state_event = StateChangeEvent(
        vault_id=vault_id,
        entity_id=from_entity.id,
        event_type=StateChangeEventType.RELATIONSHIP_CHANGE,
        payload={
            "action": action,
            "rel_type": str(rel_type),
            "to_entity_id": str(to_entity.id),
            "to_entity_name": to_entity.name,
            "relationship_id": str(relationship_id)
        },
        world_timestamp=None,
        narrative_sequence=None,
        source_scene_id=scene_id,
        dimension="reality"
    )
    session.add(state_event)
    session.commit()

    self.log.info(
        "relationship_change_logged",
        from_entity=from_entity.name,
        to_entity=to_entity.name,
        rel_type=str(rel_type),
        action=action
    )
```

**Integration Points:**
- Call this method wherever Relationship records are created
- Typically in profiler when building family trees or faction connections
- In any future relationship creation code

**Testing:**
```python
def test_relationship_creation_logs_state_change(session):
    profiler = ProfilerAgent()

    # Create two entities
    jon = profiler.find_or_create_entity("Jon Snow", EntityType.CHARACTER, vault_id, session)
    ned = profiler.find_or_create_entity("Ned Stark", EntityType.CHARACTER, vault_id, session)

    # Create relationship
    rel = Relationship(
        vault_id=vault_id,
        from_entity_id=jon.id,
        to_entity_id=ned.id,
        rel_type=RelationType.PARENT
    )
    session.add(rel)
    session.commit()

    # Log the relationship
    profiler.log_relationship_change(
        session=session,
        vault_id=vault_id,
        from_entity=jon,
        to_entity=ned,
        rel_type=RelationType.PARENT,
        relationship_id=rel.id,
        action="relationship_added"
    )

    # Verify event logged
    events = session.exec(
        select(StateChangeEvent).where(
            StateChangeEvent.entity_id == jon.id,
            StateChangeEvent.event_type == StateChangeEventType.RELATIONSHIP_CHANGE
        )
    ).all()

    assert len(events) == 1
    assert events[0].payload["rel_type"] == "PARENT"
```

**Acceptance Criteria:**
- ✅ Relationship creation logs StateChangeEvent
- ✅ Event includes both entity names and relationship type
- ✅ Test passes

---

### Day 3-4: CharacterKnowledge Integration

#### Objective
Track what characters believe (vs objective truth) for epistemic consistency.

#### Tasks

**2.1: Extend PsychologistAgent to Create CharacterKnowledge**

**File:** `src/writeros/agents/psychologist.py`
**Method:** Modify `run()` or add new method `track_character_knowledge()`

**Code to Add:**
```python
# Import at top
from writeros.schema.provenance import CharacterKnowledge
from writeros.schema.enums import KnowledgeSourceType

def track_character_knowledge(
    self,
    session: Session,
    vault_id: UUID,
    character_id: UUID,
    knowledge_content: str,
    fact_id: Optional[UUID] = None,
    is_accurate: bool = True,
    source_type: KnowledgeSourceType = KnowledgeSourceType.UNKNOWN,
    source_entity_id: Optional[UUID] = None,
    learned_in_scene_id: Optional[UUID] = None,
    confidence: float = 1.0
):
    """
    Create a CharacterKnowledge entry.

    Use cases:
    - Character learns truth: is_accurate=True
    - Character believes a lie: is_accurate=False
    - Character suspects something: confidence < 1.0

    Args:
        session: Database session
        vault_id: Vault ID
        character_id: Character who knows this
        knowledge_content: What they believe
        fact_id: Link to objective truth (if exists)
        is_accurate: Does this match reality?
        source_type: How did they learn this?
        source_entity_id: Who told them? (if TOLD_BY)
        learned_in_scene_id: Scene where they learned it
        confidence: How certain are they? (0.0-1.0)
    """
    knowledge = CharacterKnowledge(
        vault_id=vault_id,
        character_id=character_id,
        fact_id=fact_id,
        knowledge_content=knowledge_content,
        subject_entity_id=None,  # TODO: Extract from knowledge_content
        source_type=source_type,
        source_entity_id=source_entity_id,
        learned_in_scene_id=learned_in_scene_id,
        confidence=confidence,
        is_accurate=is_accurate,
        forgotten_at_sequence=None,
        superseded_by_id=None
    )
    session.add(knowledge)
    session.commit()

    self.log.info(
        "character_knowledge_tracked",
        character_id=str(character_id),
        knowledge=knowledge_content,
        is_accurate=is_accurate,
        source_type=str(source_type)
    )

    return knowledge
```

**Example Usage in PsychologistAgent:**
```python
async def run(self, full_text: str, existing_notes: str, title: str):
    # ... existing profiling code ...

    # NEW: After extracting character beliefs/knowledge
    # Example: Extract what character believes about their parentage
    if "believes" in profile_result or "thinks" in profile_result:
        # Parse belief statements
        # Example: "Jon believes Ned Stark is his father"

        # Check if this is accurate
        actual_fact = self.check_fact_database(vault_id, "Jon's parentage")
        is_lie = (actual_fact and actual_fact != belief)

        # Track the belief
        self.track_character_knowledge(
            session=session,
            vault_id=vault_id,
            character_id=jon_entity.id,
            knowledge_content="Ned Stark is my father",
            fact_id=actual_fact.id if actual_fact else None,
            is_accurate=not is_lie,
            source_type=KnowledgeSourceType.TOLD_BY,
            source_entity_id=ned_entity.id,
            learned_in_scene_id=scene.id,
            confidence=1.0
        )
```

**Testing:**
```python
def test_character_knowledge_creation(session):
    psychologist = PsychologistAgent()

    # Create character
    jon = Entity(name="Jon Snow", type=EntityType.CHARACTER, vault_id=vault_id)
    session.add(jon)
    session.commit()

    # Track knowledge
    knowledge = psychologist.track_character_knowledge(
        session=session,
        vault_id=vault_id,
        character_id=jon.id,
        knowledge_content="Ned Stark is my father",
        is_accurate=False,  # This is the lie!
        source_type=KnowledgeSourceType.TOLD_BY,
        confidence=1.0
    )

    # Verify
    assert knowledge.character_id == jon.id
    assert knowledge.is_accurate == False
    assert knowledge.knowledge_content == "Ned Stark is my father"
```

**Acceptance Criteria:**
- ✅ CharacterKnowledge records can be created
- ✅ is_accurate flag correctly tracks lies vs truth
- ✅ source_type tracks how knowledge was acquired
- ✅ Test passes

---

**2.2: Add ProvenanceService Method: get_character_beliefs_at_time()**

**File:** `src/writeros/services/provenance.py`
**Method:** Add new query method

**Code to Add:**
```python
def get_character_beliefs_at_time(
    self,
    character_id: UUID,
    scene_id: Optional[UUID] = None,
    world_timestamp: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get what a character believes at a specific point in the story.

    Returns both accurate knowledge and false beliefs.

    Args:
        character_id: Character to query
        scene_id: Specific scene (optional)
        world_timestamp: Narrative sequence number (optional)

    Returns:
        Dict with:
        - truths: List of accurate knowledge
        - lies: List of false beliefs
        - uncertainties: List of low-confidence beliefs
    """
    knowledge_list = self.get_character_knowledge(character_id, world_timestamp)

    result = {
        "truths": [],
        "lies": [],
        "uncertainties": []
    }

    for k in knowledge_list:
        entry = {
            "content": k.knowledge_content,
            "source": str(k.source_type),
            "confidence": k.confidence,
            "learned_in_scene": k.learned_in_scene_id
        }

        if not k.is_accurate:
            result["lies"].append(entry)
        elif k.confidence < 0.7:
            result["uncertainties"].append(entry)
        else:
            result["truths"].append(entry)

    return result
```

**Usage Example:**
```python
# In OrchestratorAgent or API endpoint
provenance = ProvenanceService(session)

# User asks: "What did Jon know in Chapter 5?"
beliefs = provenance.get_character_beliefs_at_time(
    character_id=jon_id,
    world_timestamp=5  # Chapter 5
)

response = f"""
At Chapter 5, Jon Snow believed:

TRUTHS:
{chr(10).join('- ' + t['content'] for t in beliefs['truths'])}

FALSE BELIEFS:
{chr(10).join('- ' + l['content'] for l in beliefs['lies'])}

UNCERTAINTIES:
{chr(10).join('- ' + u['content'] for u in beliefs['uncertainties'])}
"""
```

**Testing:**
```python
def test_character_beliefs_at_time(session):
    provenance = ProvenanceService(session)

    # Setup: Jon believes lie in Chapter 1, learns truth in Chapter 45
    jon = create_test_entity("Jon Snow", session)

    # Chapter 1: Believes lie
    knowledge1 = CharacterKnowledge(
        vault_id=vault_id,
        character_id=jon.id,
        knowledge_content="Ned is my father",
        is_accurate=False,
        forgotten_at_sequence=45  # Forgotten when truth revealed
    )
    session.add(knowledge1)

    # Chapter 45: Learns truth
    knowledge2 = CharacterKnowledge(
        vault_id=vault_id,
        character_id=jon.id,
        knowledge_content="I am Aegon Targaryen",
        is_accurate=True,
        superseded_by_id=None
    )
    session.add(knowledge2)
    session.commit()

    # Query: Chapter 10 (still believes lie)
    beliefs_ch10 = provenance.get_character_beliefs_at_time(jon.id, world_timestamp=10)
    assert len(beliefs_ch10["lies"]) == 1
    assert "Ned is my father" in beliefs_ch10["lies"][0]["content"]

    # Query: Chapter 50 (knows truth)
    beliefs_ch50 = provenance.get_character_beliefs_at_time(jon.id, world_timestamp=50)
    assert len(beliefs_ch50["truths"]) == 1
    assert "Aegon Targaryen" in beliefs_ch50["truths"][0]["content"]
    assert len(beliefs_ch50["lies"]) == 0  # Lie forgotten
```

**Acceptance Criteria:**
- ✅ Can query character beliefs at any timestamp
- ✅ Correctly filters forgotten knowledge
- ✅ Separates truths from lies
- ✅ Test passes

---

### Day 5-6: ContentDependency Integration

#### Objective
Track which scenes depend on which facts/events for retcon detection.

#### Tasks

**3.1: Add ContentDependency Creation to ChronologistAgent**

**File:** `src/writeros/agents/chronologist.py`
**Method:** Modify event extraction to create dependencies

**Code to Add:**
```python
# Import at top
from writeros.schema.provenance import ContentDependency
from writeros.schema.enums import DependencyType

async def run(self, full_text: str, existing_notes: str, title: str):
    # ... existing event extraction code ...

    # NEW: After extracting events, create content dependencies
    for event in extracted_events:
        # Create the event record
        event_record = Event(
            vault_id=vault_id,
            name=event.name,
            description=event.description,
            sequence_order=event.sequence,
            # ...
        )
        session.add(event_record)
        session.commit()

        # NEW: Create content dependency
        # This scene depends on this event existing
        dependency = ContentDependency(
            vault_id=vault_id,
            dependent_scene_id=scene_id,  # This scene
            dependency_type=DependencyType.REFERENCES_EVENT,
            dependency_id=event_record.id,  # Depends on this event
            assumption=f"Scene assumes event '{event.name}' has occurred",
            is_valid=True,
            auto_detected=True,
            confidence=0.8  # AI-detected
        )
        session.add(dependency)

        self.log.info(
            "content_dependency_created",
            scene_id=str(scene_id),
            event_id=str(event_record.id),
            event_name=event.name
        )

    session.commit()
```

**Testing:**
```python
def test_event_creates_content_dependency(session):
    chronologist = ChronologistAgent()

    # Create scene
    scene = Scene(vault_id=vault_id, title="Chapter 10", content="The battle ended...")
    session.add(scene)
    session.commit()

    # Run chronologist (extracts events)
    result = await chronologist.run(
        full_text=scene.content,
        existing_notes="",
        title=scene.title
    )

    # Verify ContentDependency was created
    dependencies = session.exec(
        select(ContentDependency).where(
            ContentDependency.dependent_scene_id == scene.id
        )
    ).all()

    assert len(dependencies) > 0
    assert dependencies[0].dependency_type == DependencyType.REFERENCES_EVENT
    assert dependencies[0].is_valid == True
```

**Acceptance Criteria:**
- ✅ Event extraction creates ContentDependency
- ✅ Dependency links scene to event
- ✅ auto_detected flag set correctly
- ✅ Test passes

---

**3.2: Add Retcon Detection to ProvenanceService**

**File:** `src/writeros/services/provenance.py`
**Method:** Enhance `detect_retcon_impact()`

**Code to Add:**
```python
def analyze_retcon_impact(
    self,
    modified_entity_id: UUID,
    modification_type: str = "deleted"
) -> Dict[str, Any]:
    """
    Comprehensive retcon impact analysis.

    Args:
        modified_entity_id: Entity that was changed/deleted
        modification_type: "deleted", "status_changed", "relationship_removed"

    Returns:
        Dict with:
        - affected_scenes: List of scenes that break
        - affected_anchors: List of plot anchors that become impossible
        - affected_knowledge: List of character beliefs that are now invalid
        - severity: HIGH/MEDIUM/LOW
    """
    # Get all content dependencies
    broken_dependencies = self.detect_retcon_impact(modified_entity_id)

    # Get affected scenes
    affected_scene_ids = [dep.dependent_scene_id for dep in broken_dependencies]
    affected_scenes = self.session.exec(
        select(Scene).where(Scene.id.in_(affected_scene_ids))
    ).all()

    # Get affected character knowledge
    affected_knowledge = self.session.exec(
        select(CharacterKnowledge).where(
            CharacterKnowledge.fact_id == modified_entity_id
        )
    ).all()

    # Calculate severity
    total_impact = len(broken_dependencies) + len(affected_knowledge)
    if total_impact > 10:
        severity = "HIGH"
    elif total_impact > 3:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    return {
        "modification_type": modification_type,
        "affected_scenes": [
            {
                "scene_id": str(s.id),
                "scene_title": s.title,
                "assumption": next(
                    (d.assumption for d in broken_dependencies if d.dependent_scene_id == s.id),
                    "Unknown"
                )
            }
            for s in affected_scenes
        ],
        "affected_knowledge": [
            {
                "character_id": str(k.character_id),
                "knowledge": k.knowledge_content,
                "now_invalid": True
            }
            for k in affected_knowledge
        ],
        "total_dependencies_broken": len(broken_dependencies),
        "severity": severity,
        "recommendation": self._get_recommendation(severity, modification_type)
    }

def _get_recommendation(self, severity: str, modification_type: str) -> str:
    """Generate recommendation based on severity."""
    if severity == "HIGH":
        return f"⚠️ HIGH IMPACT: {modification_type} will break {severity} scenes. Review carefully before proceeding."
    elif severity == "MEDIUM":
        return f"⚠️ MEDIUM IMPACT: Several scenes reference this. Consider updating affected content."
    else:
        return f"✅ LOW IMPACT: Minimal dependencies found. Safe to proceed."
```

**Usage Example:**
```python
# User deletes entity "Longclaw" (Jon's sword)
provenance = ProvenanceService(session)

impact = provenance.analyze_retcon_impact(
    modified_entity_id=longclaw_entity.id,
    modification_type="deleted"
)

print(impact)
# Output:
# {
#   "affected_scenes": [
#     {"scene_id": "...", "scene_title": "Chapter 15", "assumption": "Jon has Longclaw"},
#     {"scene_id": "...", "scene_title": "Chapter 23", "assumption": "Jon uses Longclaw in battle"}
#   ],
#   "total_dependencies_broken": 2,
#   "severity": "MEDIUM",
#   "recommendation": "⚠️ MEDIUM IMPACT: Several scenes reference this..."
# }
```

**Testing:**
```python
def test_retcon_impact_analysis(session):
    provenance = ProvenanceService(session)

    # Setup: Create entity and dependencies
    longclaw = Entity(name="Longclaw", type=EntityType.ITEM, vault_id=vault_id)
    session.add(longclaw)
    session.commit()

    scene1 = Scene(vault_id=vault_id, title="Chapter 15")
    session.add(scene1)
    session.commit()

    dep = ContentDependency(
        vault_id=vault_id,
        dependent_scene_id=scene1.id,
        dependency_type=DependencyType.ASSUMES_ALIVE,
        dependency_id=longclaw.id,
        assumption="Jon has Longclaw",
        is_valid=True
    )
    session.add(dep)
    session.commit()

    # Analyze retcon impact
    impact = provenance.analyze_retcon_impact(
        modified_entity_id=longclaw.id,
        modification_type="deleted"
    )

    assert impact["severity"] in ["LOW", "MEDIUM", "HIGH"]
    assert len(impact["affected_scenes"]) == 1
    assert impact["affected_scenes"][0]["scene_title"] == "Chapter 15"
```

**Acceptance Criteria:**
- ✅ Retcon analysis returns affected scenes
- ✅ Severity calculated correctly
- ✅ Recommendations provided
- ✅ Test passes

---

## Week 2: Advanced Features & Testing

### Day 7-8: Time-Travel Query API

#### Objective
Expose time-travel query capabilities via API and integrate with OrchestratorAgent.

#### Tasks

**4.1: Add API Endpoint for Time-Travel Queries**

**File:** `src/writeros/api/endpoints.py` (or create new `provenance_endpoints.py`)

**Code to Add:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from writeros.services.provenance import ProvenanceService
from writeros.utils.db import get_session

router = APIRouter(prefix="/api/v1/provenance", tags=["provenance"])

@router.get("/character/{character_id}/knowledge")
async def get_character_knowledge_at_time(
    character_id: str,
    world_timestamp: Optional[int] = None,
    scene_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Get what a character knew at a specific point in time.

    Use cases:
    - "What did Jon know in Chapter 5?"
    - "Did Sansa know about Jon's parentage in this scene?"

    Query params:
    - world_timestamp: Sequence number (e.g., chapter number)
    - scene_id: Specific scene UUID (alternative to timestamp)
    """
    try:
        character_uuid = UUID(character_id)
        provenance = ProvenanceService(session)

        # If scene_id provided, get its sequence number
        if scene_id:
            scene = session.get(Scene, UUID(scene_id))
            if scene:
                world_timestamp = scene.sequence_order

        beliefs = provenance.get_character_beliefs_at_time(
            character_id=character_uuid,
            world_timestamp=world_timestamp
        )

        return {
            "character_id": character_id,
            "timestamp": world_timestamp,
            "beliefs": beliefs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/retcon-analysis")
async def analyze_retcon_impact(
    entity_id: str,
    modification_type: str = "deleted",
    session: Session = Depends(get_session)
):
    """
    Analyze the impact of changing/deleting an entity.

    Use cases:
    - "What breaks if I delete this character?"
    - "What scenes reference this event?"

    Body:
    - entity_id: UUID of entity to modify
    - modification_type: "deleted", "status_changed", "relationship_removed"
    """
    try:
        entity_uuid = UUID(entity_id)
        provenance = ProvenanceService(session)

        impact = provenance.analyze_retcon_impact(
            modified_entity_id=entity_uuid,
            modification_type=modification_type
        )

        return impact
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vault/{vault_id}/state-at-time")
async def get_vault_state_at_time(
    vault_id: str,
    world_timestamp: int,
    session: Session = Depends(get_session)
):
    """
    Get the complete vault state at a specific point in time.

    Returns:
    - All entities that existed
    - All relationships that were active
    - All events that had occurred

    This is the "time machine" feature.
    """
    try:
        vault_uuid = UUID(vault_id)
        provenance = ProvenanceService(session)

        # Get all entities created before this timestamp
        entities = session.exec(
            select(Entity).where(
                Entity.vault_id == vault_uuid,
                Entity.created_at <= datetime.fromtimestamp(world_timestamp)
            )
        ).all()

        # Get all state change events up to this timestamp
        state_events = session.exec(
            select(StateChangeEvent).where(
                StateChangeEvent.vault_id == vault_uuid,
                StateChangeEvent.world_timestamp <= world_timestamp
            ).order_by(StateChangeEvent.world_timestamp)
        ).all()

        # Replay state for each entity
        entity_states = {}
        for entity in entities:
            state = provenance.compute_character_state(
                character_id=entity.id,
                world_timestamp=world_timestamp
            )
            entity_states[str(entity.id)] = {
                "name": entity.name,
                "type": str(entity.type),
                "state": state
            }

        return {
            "vault_id": vault_id,
            "timestamp": world_timestamp,
            "entities": entity_states,
            "total_entities": len(entities),
            "total_events_replayed": len(state_events)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Testing:**
```python
from fastapi.testclient import TestClient

def test_time_travel_api(client: TestClient):
    # Create test data
    # ...

    response = client.get(
        f"/api/v1/provenance/character/{jon_id}/knowledge",
        params={"world_timestamp": 5}
    )

    assert response.status_code == 200
    data = response.json()
    assert "beliefs" in data
    assert "truths" in data["beliefs"]
    assert "lies" in data["beliefs"]

def test_retcon_analysis_api(client: TestClient):
    response = client.post(
        "/api/v1/provenance/retcon-analysis",
        json={
            "entity_id": str(longclaw_id),
            "modification_type": "deleted"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "affected_scenes" in data
    assert "severity" in data
```

**Acceptance Criteria:**
- ✅ API endpoints work correctly
- ✅ Time-travel queries return valid data
- ✅ Retcon analysis endpoint functions
- ✅ Tests pass

---

**4.2: Integrate Time-Travel Queries into OrchestratorAgent**

**File:** `src/writeros/agents/orchestrator.py`

**Code to Add:**
```python
async def handle_time_travel_query(
    self,
    query: str,
    vault_id: UUID,
    session: Session
) -> str:
    """
    Handle time-travel queries like:
    - "What did Jon know in Chapter 5?"
    - "Show me the vault state at Chapter 10"
    - "What breaks if I delete Longclaw?"
    """
    # Detect query type
    if "what did" in query.lower() and "know" in query.lower():
        # Character knowledge query
        # Extract character name and timestamp
        # Use regex or LLM to parse

        # Example: "What did Jon know in Chapter 5?"
        character_name = self._extract_character_name(query)
        timestamp = self._extract_timestamp(query)

        # Look up character
        character = session.exec(
            select(Entity).where(
                Entity.vault_id == vault_id,
                Entity.name.ilike(f"%{character_name}%"),
                Entity.type == EntityType.CHARACTER
            )
        ).first()

        if not character:
            return f"Character '{character_name}' not found."

        # Query provenance
        provenance = ProvenanceService(session)
        beliefs = provenance.get_character_beliefs_at_time(
            character_id=character.id,
            world_timestamp=timestamp
        )

        # Format response
        response = f"At Chapter {timestamp}, {character.name} believed:\n\n"

        if beliefs["truths"]:
            response += "TRUTHS:\n"
            for truth in beliefs["truths"]:
                response += f"- {truth['content']}\n"

        if beliefs["lies"]:
            response += "\nFALSE BELIEFS:\n"
            for lie in beliefs["lies"]:
                response += f"- {lie['content']} (believed to be true)\n"

        if beliefs["uncertainties"]:
            response += "\nUNCERTAINTIES:\n"
            for unc in beliefs["uncertainties"]:
                response += f"- {unc['content']} (confidence: {unc['confidence']})\n"

        return response

    elif "what breaks" in query.lower() or "retcon" in query.lower():
        # Retcon impact query
        # Extract entity name

        entity_name = self._extract_entity_name(query)
        entity = session.exec(
            select(Entity).where(
                Entity.vault_id == vault_id,
                Entity.name.ilike(f"%{entity_name}%")
            )
        ).first()

        if not entity:
            return f"Entity '{entity_name}' not found."

        # Analyze retcon impact
        provenance = ProvenanceService(session)
        impact = provenance.analyze_retcon_impact(
            modified_entity_id=entity.id,
            modification_type="deleted"
        )

        # Format response
        response = f"Retcon Impact Analysis for '{entity.name}':\n\n"
        response += f"Severity: {impact['severity']}\n"
        response += f"Total dependencies broken: {impact['total_dependencies_broken']}\n\n"

        if impact['affected_scenes']:
            response += "AFFECTED SCENES:\n"
            for scene in impact['affected_scenes']:
                response += f"- {scene['scene_title']}: {scene['assumption']}\n"

        response += f"\n{impact['recommendation']}"

        return response

    else:
        return "I don't recognize this as a time-travel query."

def _extract_character_name(self, query: str) -> str:
    """Extract character name from query using regex or LLM."""
    # Simple regex approach
    import re
    match = re.search(r"what did (\w+) know", query, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def _extract_timestamp(self, query: str) -> Optional[int]:
    """Extract timestamp (chapter number) from query."""
    import re
    match = re.search(r"chapter (\d+)", query, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def _extract_entity_name(self, query: str) -> str:
    """Extract entity name from retcon query."""
    import re
    match = re.search(r"delete (\w+)", query, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""
```

**Usage in Orchestrator's run() method:**
```python
async def run(self, query: str, vault_id: UUID, session: Session):
    # Check if this is a time-travel query
    time_travel_keywords = ["what did", "know in chapter", "what breaks", "retcon"]
    if any(kw in query.lower() for kw in time_travel_keywords):
        return await self.handle_time_travel_query(query, vault_id, session)

    # Otherwise, proceed with normal RAG flow
    # ...
```

**Testing:**
```python
async def test_orchestrator_time_travel_query():
    orchestrator = OrchestratorAgent()

    response = await orchestrator.run(
        query="What did Jon know in Chapter 5?",
        vault_id=test_vault_id,
        session=test_session
    )

    assert "Jon" in response
    assert "believed" in response or "knew" in response
```

**Acceptance Criteria:**
- ✅ Orchestrator recognizes time-travel queries
- ✅ Extracts character name and timestamp
- ✅ Returns formatted response
- ✅ Test passes

---

### Day 9-10: Integration Testing & Documentation

#### Tasks

**5.1: End-to-End Integration Tests**

**File:** `tests/integration/test_provenance_e2e.py`

```python
import pytest
from uuid import uuid4
from sqlmodel import Session
from writeros.agents.profiler import ProfilerAgent
from writeros.agents.psychologist import PsychologistAgent
from writeros.agents.orchestrator import OrchestratorAgent
from writeros.services.provenance import ProvenanceService

@pytest.mark.asyncio
async def test_full_provenance_workflow(session: Session):
    """
    Test complete provenance workflow from entity creation to time-travel query.

    Scenario:
    1. Create character "Jon Snow"
    2. Track that Jon believes "Ned is my father" (false belief)
    3. Later reveal truth: "Jon is Aegon Targaryen"
    4. Query: "What did Jon know in Chapter 5?" (before reveal)
    5. Query: "What did Jon know in Chapter 50?" (after reveal)
    6. Verify correct beliefs returned for each timestamp
    """
    vault_id = uuid4()
    profiler = ProfilerAgent()
    psychologist = PsychologistAgent()
    orchestrator = OrchestratorAgent()
    provenance = ProvenanceService(session)

    # Step 1: Create Jon Snow
    jon = profiler.find_or_create_entity(
        name="Jon Snow",
        entity_type=EntityType.CHARACTER,
        vault_id=vault_id,
        session=session
    )

    # Verify StateChangeEvent created
    events = session.exec(
        select(StateChangeEvent).where(StateChangeEvent.entity_id == jon.id)
    ).all()
    assert len(events) == 1
    assert events[0].payload["action"] == "entity_created"

    # Step 2: Track false belief (Chapter 1-44)
    lie_knowledge = psychologist.track_character_knowledge(
        session=session,
        vault_id=vault_id,
        character_id=jon.id,
        knowledge_content="Ned Stark is my father",
        is_accurate=False,
        source_type=KnowledgeSourceType.TOLD_BY,
        forgotten_at_sequence=45  # Forgotten when truth revealed
    )

    # Step 3: Track truth reveal (Chapter 45+)
    truth_knowledge = psychologist.track_character_knowledge(
        session=session,
        vault_id=vault_id,
        character_id=jon.id,
        knowledge_content="I am Aegon Targaryen, son of Rhaegar",
        is_accurate=True,
        source_type=KnowledgeSourceType.TOLD_BY,
        learned_in_scene_id=None  # Scene ID would be set in real usage
    )

    # Step 4: Query Chapter 5 (before truth reveal)
    response_ch5 = await orchestrator.handle_time_travel_query(
        query="What did Jon Snow know in Chapter 5?",
        vault_id=vault_id,
        session=session
    )

    assert "Ned Stark is my father" in response_ch5
    assert "FALSE BELIEFS" in response_ch5
    assert "Aegon Targaryen" not in response_ch5  # Not known yet

    # Step 5: Query Chapter 50 (after truth reveal)
    response_ch50 = await orchestrator.handle_time_travel_query(
        query="What did Jon Snow know in Chapter 50?",
        vault_id=vault_id,
        session=session
    )

    assert "Aegon Targaryen" in response_ch50
    assert "TRUTHS" in response_ch50
    assert "Ned Stark is my father" not in response_ch50  # Forgotten

    # Step 6: Test retcon analysis
    # Create a scene that references Jon
    scene = Scene(
        vault_id=vault_id,
        title="Chapter 10",
        content="Jon wielded his sword..."
    )
    session.add(scene)
    session.commit()

    dep = ContentDependency(
        vault_id=vault_id,
        dependent_scene_id=scene.id,
        dependency_type=DependencyType.ASSUMES_ALIVE,
        dependency_id=jon.id,
        assumption="Jon is alive",
        is_valid=True
    )
    session.add(dep)
    session.commit()

    # Analyze impact of deleting Jon
    impact = provenance.analyze_retcon_impact(
        modified_entity_id=jon.id,
        modification_type="deleted"
    )

    assert impact["severity"] in ["LOW", "MEDIUM", "HIGH"]
    assert len(impact["affected_scenes"]) >= 1
    assert impact["affected_scenes"][0]["scene_title"] == "Chapter 10"

@pytest.mark.asyncio
async def test_relationship_provenance(session: Session):
    """
    Test relationship creation logs StateChangeEvent.
    """
    vault_id = uuid4()
    profiler = ProfilerAgent()

    # Create two characters
    jon = profiler.find_or_create_entity("Jon Snow", EntityType.CHARACTER, vault_id, session)
    ned = profiler.find_or_create_entity("Ned Stark", EntityType.CHARACTER, vault_id, session)

    # Create relationship
    rel = Relationship(
        vault_id=vault_id,
        from_entity_id=jon.id,
        to_entity_id=ned.id,
        rel_type=RelationType.PARENT
    )
    session.add(rel)
    session.commit()

    # Log relationship
    profiler.log_relationship_change(
        session=session,
        vault_id=vault_id,
        from_entity=jon,
        to_entity=ned,
        rel_type=RelationType.PARENT,
        relationship_id=rel.id
    )

    # Verify StateChangeEvent
    events = session.exec(
        select(StateChangeEvent).where(
            StateChangeEvent.entity_id == jon.id,
            StateChangeEvent.event_type == StateChangeEventType.RELATIONSHIP_CHANGE
        )
    ).all()

    assert len(events) == 1
    assert events[0].payload["rel_type"] == "PARENT"
    assert events[0].payload["to_entity_name"] == "Ned Stark"
```

**Acceptance Criteria:**
- ✅ Full workflow test passes
- ✅ Time-travel queries work end-to-end
- ✅ Retcon analysis works
- ✅ All assertions pass

---

**5.2: Documentation**

**File:** `docs/PROVENANCE_SYSTEM.md`

```markdown
# Provenance System Documentation

## Overview

The Provenance System enables time-travel queries and retcon detection by tracking:
1. **StateChangeEvent** - Every entity state change
2. **CharacterKnowledge** - What characters believe (vs objective truth)
3. **ContentDependency** - Which scenes depend on which facts

## Use Cases

### 1. Time-Travel Queries

**Query:** "What did Jon know in Chapter 5?"

**System Behavior:**
1. Look up Jon Snow entity
2. Query CharacterKnowledge with world_timestamp=5
3. Filter by forgotten_at_sequence (exclude knowledge learned later)
4. Return truths, lies, and uncertainties

**Example Response:**
```
At Chapter 5, Jon Snow believed:

TRUTHS:
- I am a member of the Night's Watch
- The White Walkers are returning

FALSE BELIEFS:
- Ned Stark is my father (believed to be true)

UNCERTAINTIES:
- My mother might be a tavern wench (confidence: 0.5)
```

### 2. Retcon Detection

**Query:** "What breaks if I delete Longclaw?"

**System Behavior:**
1. Look up Longclaw entity
2. Query ContentDependency for dependency_id=Longclaw
3. Find all scenes that assume Jon has Longclaw
4. Calculate severity (HIGH/MEDIUM/LOW)
5. Return affected scenes with recommendations

**Example Response:**
```
Retcon Impact Analysis for 'Longclaw':

Severity: MEDIUM
Total dependencies broken: 3

AFFECTED SCENES:
- Chapter 15: Jon draws Longclaw in battle
- Chapter 23: Jon polishes Longclaw
- Chapter 30: Jon gives Longclaw to Arya

⚠️ MEDIUM IMPACT: Several scenes reference this. Consider updating affected content.
```

### 3. Vault State at Time

**Query:** "Show me the vault state at Chapter 10"

**System Behavior:**
1. Query all entities created before Chapter 10
2. Replay all StateChangeEvents up to Chapter 10
3. Reconstruct inventory, locations, statuses for each entity
4. Return complete snapshot

## API Endpoints

### GET `/api/v1/provenance/character/{character_id}/knowledge`

**Query Parameters:**
- `world_timestamp`: Sequence number (e.g., chapter)
- `scene_id`: Alternative to timestamp

**Response:**
```json
{
  "character_id": "uuid",
  "timestamp": 5,
  "beliefs": {
    "truths": [...],
    "lies": [...],
    "uncertainties": [...]
  }
}
```

### POST `/api/v1/provenance/retcon-analysis`

**Request Body:**
```json
{
  "entity_id": "uuid",
  "modification_type": "deleted"
}
```

**Response:**
```json
{
  "severity": "MEDIUM",
  "affected_scenes": [...],
  "total_dependencies_broken": 3,
  "recommendation": "..."
}
```

## Integration with Agents

### ProfilerAgent
- Creates StateChangeEvent on entity creation
- Logs relationship changes

### PsychologistAgent
- Creates CharacterKnowledge entries
- Tracks lies vs truths
- Marks false beliefs

### ChronologistAgent
- Creates ContentDependency for event references
- Links scenes to events

### OrchestratorAgent
- Handles time-travel queries
- Routes to ProvenanceService

## Database Schema

### StateChangeEvent
- `entity_id`: Entity that changed
- `event_type`: ATTRIBUTE_CHANGE, RELATIONSHIP_CHANGE, LOCATION_MOVE, etc.
- `payload`: JSONB with change details
- `world_timestamp`: When it happened (in-story)
- `narrative_sequence`: Sequence order

### CharacterKnowledge
- `character_id`: Who knows this
- `knowledge_content`: What they believe
- `is_accurate`: True belief or lie?
- `confidence`: How certain (0.0-1.0)
- `forgotten_at_sequence`: When they forgot (if ever)

### ContentDependency
- `dependent_scene_id`: Scene that depends
- `dependency_id`: Entity/Event it depends on
- `assumption`: Plain text assumption
- `is_valid`: Still valid or broken?

## Testing

Run integration tests:
```bash
pytest tests/integration/test_provenance_e2e.py -v
```

Run unit tests:
```bash
pytest tests/test_provenance_integration.py -v
```

## Future Enhancements

1. **Visual Timeline**: Graph view of state changes
2. **Diff Viewer**: Compare vault state at two timestamps
3. **Auto-Retcon Detection**: Alert on contradictions
4. **Batch Retcon Fixing**: Update multiple scenes at once
```

**Acceptance Criteria:**
- ✅ Documentation complete
- ✅ All use cases explained
- ✅ API documented
- ✅ Examples provided

---

## Phase 1 Deliverables Checklist

- ✅ StateChangeEvent integration (ProfilerAgent)
- ✅ CharacterKnowledge integration (PsychologistAgent)
- ✅ ContentDependency integration (ChronologistAgent)
- ✅ ProvenanceService query methods
- ✅ API endpoints for time-travel queries
- ✅ OrchestratorAgent integration
- ✅ End-to-end integration tests
- ✅ Documentation

**Success Criteria:**
- User can ask "What did Jon know in Chapter 5?" and get accurate answer
- User can ask "What breaks if I delete X?" and get list of affected scenes
- All tests pass (unit + integration)
- Documentation complete

---

# PHASE 2: ENTITY DEDUPLICATION SYSTEM

**Timeline:** Week 3-4 (10 working days)
**Effort:** ~80-100 hours
**Dependencies:** Embeddings service (already exists)
**Risk:** Medium-High (ML complexity, merge complexity)

---

## Week 3: Detection & Similarity Algorithm

### Day 1-3: Similarity Detection Algorithm

#### Objective
Build ML-based similarity scoring to detect duplicate entities.

#### Tasks

**1.1: Create EntitySimilarityService**

**File:** `src/writeros/services/entity_similarity.py` (NEW FILE)

**Code:**
```python
"""
Entity Similarity Service
Detects potential duplicate entities using multiple signals.
"""
from typing import List, Dict, Any, Tuple
from uuid import UUID
from sqlmodel import Session, select
import numpy as np
from difflib import SequenceMatcher

from writeros.schema.world import Entity
from writeros.schema.extended_universe import EntityMergeCandidate
from writeros.services.embeddings import EmbeddingService


class EntitySimilarityService:
    """
    Detects potential duplicate entities.

    Similarity signals:
    1. Name similarity (Levenshtein distance)
    2. Alias overlap
    3. Embedding similarity (semantic)
    4. Co-occurrence in scenes
    5. Shared relationships
    """

    def __init__(self, session: Session, embedding_service: EmbeddingService):
        self.session = session
        self.embedding_service = embedding_service

    def calculate_similarity(
        self,
        entity_a: Entity,
        entity_b: Entity
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate similarity score between two entities.

        Returns:
            (similarity_score, evidence_dict)

        Score range: 0.0 (completely different) to 1.0 (identical)
        """
        evidence = {}
        weights = {
            "name": 0.30,
            "alias": 0.20,
            "embedding": 0.25,
            "co_occurrence": 0.15,
            "relationships": 0.10
        }

        # 1. Name similarity
        name_similarity = self._name_similarity(entity_a.name, entity_b.name)
        evidence["name_similarity"] = name_similarity

        # 2. Alias overlap
        alias_similarity = self._alias_similarity(entity_a, entity_b)
        evidence["alias_overlap"] = alias_similarity

        # 3. Embedding similarity
        embedding_similarity = self._embedding_similarity(entity_a, entity_b)
        evidence["embedding_similarity"] = embedding_similarity

        # 4. Co-occurrence in scenes
        co_occurrence = self._co_occurrence_score(entity_a, entity_b)
        evidence["co_occurrence_score"] = co_occurrence

        # 5. Shared relationships
        relationship_similarity = self._relationship_similarity(entity_a, entity_b)
        evidence["relationship_overlap"] = relationship_similarity

        # Weighted average
        total_score = (
            weights["name"] * name_similarity +
            weights["alias"] * alias_similarity +
            weights["embedding"] * embedding_similarity +
            weights["co_occurrence"] * co_occurrence +
            weights["relationships"] * relationship_similarity
        )

        return total_score, evidence

    def _name_similarity(self, name_a: str, name_b: str) -> float:
        """Calculate name similarity using sequence matching."""
        return SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()

    def _alias_similarity(self, entity_a: Entity, entity_b: Entity) -> float:
        """Calculate alias overlap."""
        aliases_a = set(entity_a.aliases or [])
        aliases_b = set(entity_b.aliases or [])

        if not aliases_a and not aliases_b:
            return 0.0

        # Jaccard similarity
        intersection = aliases_a & aliases_b
        union = aliases_a | aliases_b

        return len(intersection) / len(union) if union else 0.0

    def _embedding_similarity(self, entity_a: Entity, entity_b: Entity) -> float:
        """Calculate cosine similarity between embeddings."""
        if entity_a.embedding is None or entity_b.embedding is None:
            return 0.0

        # Cosine similarity
        emb_a = np.array(entity_a.embedding)
        emb_b = np.array(entity_b.embedding)

        dot_product = np.dot(emb_a, emb_b)
        norm_a = np.linalg.norm(emb_a)
        norm_b = np.linalg.norm(emb_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _co_occurrence_score(self, entity_a: Entity, entity_b: Entity) -> float:
        """
        Calculate co-occurrence in scenes.
        High co-occurrence suggests they're different (both appear together).
        Low co-occurrence with high other signals suggests they're the same.
        """
        # Query scenes where both entities appear
        # This requires ScenePresence table or scene content analysis
        # For now, return 0.0 (not implemented yet)
        # TODO: Implement when ScenePresence is populated
        return 0.0

    def _relationship_similarity(self, entity_a: Entity, entity_b: Entity) -> float:
        """Calculate overlap in relationships."""
        from writeros.schema.world import Relationship

        # Get relationships for both entities
        rels_a = self.session.exec(
            select(Relationship).where(Relationship.from_entity_id == entity_a.id)
        ).all()

        rels_b = self.session.exec(
            select(Relationship).where(Relationship.from_entity_id == entity_b.id)
        ).all()

        # Extract target entity IDs
        targets_a = set(r.to_entity_id for r in rels_a)
        targets_b = set(r.to_entity_id for r in rels_b)

        if not targets_a and not targets_b:
            return 0.0

        # Jaccard similarity
        intersection = targets_a & targets_b
        union = targets_a | targets_b

        return len(intersection) / len(union) if union else 0.0

    def find_duplicates(
        self,
        vault_id: UUID,
        threshold: float = 0.75,
        max_candidates: int = 50
    ) -> List[EntityMergeCandidate]:
        """
        Find potential duplicate entities in vault.

        Args:
            vault_id: Vault to search
            threshold: Minimum similarity score (0.0-1.0)
            max_candidates: Maximum candidates to return

        Returns:
            List of EntityMergeCandidate objects (not yet committed)
        """
        # Get all entities in vault
        entities = self.session.exec(
            select(Entity).where(Entity.vault_id == vault_id)
        ).all()

        candidates = []

        # Pairwise comparison
        for i, entity_a in enumerate(entities):
            for entity_b in entities[i+1:]:
                # Skip if different types
                if entity_a.type != entity_b.type:
                    continue

                # Calculate similarity
                score, evidence = self.calculate_similarity(entity_a, entity_b)

                # If above threshold, create candidate
                if score >= threshold:
                    candidate = EntityMergeCandidate(
                        vault_id=vault_id,
                        primary_entity_id=entity_a.id,
                        duplicate_entity_id=entity_b.id,
                        similarity_score=score,
                        evidence=evidence,
                        status="pending",
                        detected_by="archivist_agent"
                    )
                    candidates.append(candidate)

        # Sort by similarity score (highest first)
        candidates.sort(key=lambda c: c.similarity_score, reverse=True)

        return candidates[:max_candidates]
```

**Testing:**
```python
def test_entity_similarity_service(session):
    embedding_service = EmbeddingService()
    similarity_service = EntitySimilarityService(session, embedding_service)

    # Create two similar entities
    aragorn = Entity(
        vault_id=vault_id,
        name="Aragorn",
        type=EntityType.CHARACTER,
        aliases=["Strider", "Elessar"],
        description="Ranger of the North"
    )
    strider = Entity(
        vault_id=vault_id,
        name="Strider",
        type=EntityType.CHARACTER,
        aliases=["Aragorn"],
        description="Mysterious ranger"
    )
    session.add_all([aragorn, strider])
    session.commit()

    # Calculate similarity
    score, evidence = similarity_service.calculate_similarity(aragorn, strider)

    assert score > 0.7  # High similarity
    assert evidence["name_similarity"] > 0.5
    assert evidence["alias_overlap"] > 0.0

def test_find_duplicates(session):
    similarity_service = EntitySimilarityService(session, embedding_service)

    # Create multiple entities with duplicates
    entities = [
        Entity(vault_id=vault_id, name="Aragorn", type=EntityType.CHARACTER),
        Entity(vault_id=vault_id, name="Strider", type=EntityType.CHARACTER),
        Entity(vault_id=vault_id, name="Gandalf", type=EntityType.CHARACTER),
        Entity(vault_id=vault_id, name="Gandolf", type=EntityType.CHARACTER),  # Typo
    ]
    session.add_all(entities)
    session.commit()

    # Find duplicates
    candidates = similarity_service.find_duplicates(vault_id, threshold=0.6)

    assert len(candidates) >= 2  # Should find Aragorn/Strider and Gandalf/Gandolf
    assert all(c.similarity_score >= 0.6 for c in candidates)
```

**Acceptance Criteria:**
- ✅ Similarity service calculates scores correctly
- ✅ Name similarity works
- ✅ Alias overlap detected
- ✅ find_duplicates() returns candidates
- ✅ Tests pass

---

**1.2: Create ArchivistAgent**

**File:** `src/writeros/agents/archivist.py` (NEW FILE)

**Code:**
```python
"""
Archivist Agent
Detects and manages duplicate entities.
"""
from typing import List, Dict, Any
from uuid import UUID
from sqlmodel import Session

from .base import BaseAgent
from writeros.services.entity_similarity import EntitySimilarityService
from writeros.services.embeddings import EmbeddingService
from writeros.schema.extended_universe import EntityMergeCandidate


class ArchivistAgent(BaseAgent):
    """
    Detects duplicate entities and manages merge candidates.

    Responsibilities:
    - Scan vault for potential duplicates
    - Create EntityMergeCandidate records
    - Provide merge recommendations
    """

    def __init__(self, model_name: str = "gpt-4o"):
        super().__init__(model_name)
        self.embedding_service = EmbeddingService()

    async def should_respond(self, query: str, context: str = "") -> tuple[bool, float, str]:
        """Archivist responds to deduplication queries."""
        keywords = [
            "duplicate", "duplicates", "same entity", "merge",
            "aragorn strider", "consolidate", "dedup"
        ]

        query_lower = query.lower()
        if any(kw in query_lower for kw in keywords):
            return (True, 0.9, "Query involves entity deduplication")
        return (False, 0.1, "Not a deduplication query")

    async def run(
        self,
        vault_id: UUID,
        session: Session,
        threshold: float = 0.75,
        max_candidates: int = 50
    ) -> Dict[str, Any]:
        """
        Run duplicate detection on vault.

        Args:
            vault_id: Vault to scan
            session: Database session
            threshold: Minimum similarity score
            max_candidates: Maximum candidates to return

        Returns:
            Dict with:
            - candidates_found: Number of candidates
            - candidates: List of merge candidates
            - recommendations: List of recommended merges
        """
        self.log.info("archivist_scan_started", vault_id=str(vault_id))

        # Initialize similarity service
        similarity_service = EntitySimilarityService(session, self.embedding_service)

        # Find duplicates
        candidates = similarity_service.find_duplicates(
            vault_id=vault_id,
            threshold=threshold,
            max_candidates=max_candidates
        )

        # Save candidates to database
        for candidate in candidates:
            # Check if already exists
            existing = session.exec(
                select(EntityMergeCandidate).where(
                    EntityMergeCandidate.primary_entity_id == candidate.primary_entity_id,
                    EntityMergeCandidate.duplicate_entity_id == candidate.duplicate_entity_id,
                    EntityMergeCandidate.status == "pending"
                )
            ).first()

            if not existing:
                session.add(candidate)

        session.commit()

        # Generate recommendations
        recommendations = self._generate_recommendations(candidates)

        self.log.info(
            "archivist_scan_completed",
            candidates_found=len(candidates),
            high_confidence=len([c for c in candidates if c.similarity_score > 0.9])
        )

        return {
            "candidates_found": len(candidates),
            "candidates": [self._format_candidate(c, session) for c in candidates],
            "recommendations": recommendations
        }

    def _format_candidate(
        self,
        candidate: EntityMergeCandidate,
        session: Session
    ) -> Dict[str, Any]:
        """Format candidate for display."""
        from writeros.schema.world import Entity

        primary = session.get(Entity, candidate.primary_entity_id)
        duplicate = session.get(Entity, candidate.duplicate_entity_id)

        return {
            "id": str(candidate.id),
            "primary": {
                "id": str(primary.id),
                "name": primary.name,
                "type": str(primary.type),
                "aliases": primary.aliases
            },
            "duplicate": {
                "id": str(duplicate.id),
                "name": duplicate.name,
                "type": str(duplicate.type),
                "aliases": duplicate.aliases
            },
            "similarity_score": candidate.similarity_score,
            "evidence": candidate.evidence,
            "status": candidate.status
        }

    def _generate_recommendations(
        self,
        candidates: List[EntityMergeCandidate]
    ) -> List[Dict[str, Any]]:
        """
        Generate merge recommendations.

        High confidence (>0.9): Auto-merge suggested
        Medium confidence (0.75-0.9): Review suggested
        Low confidence (<0.75): Manual decision
        """
        recommendations = []

        for candidate in candidates:
            if candidate.similarity_score > 0.9:
                recommendations.append({
                    "candidate_id": str(candidate.id),
                    "action": "auto_merge",
                    "confidence": "high",
                    "reason": "Very high similarity score, likely the same entity"
                })
            elif candidate.similarity_score > 0.8:
                recommendations.append({
                    "candidate_id": str(candidate.id),
                    "action": "review",
                    "confidence": "medium",
                    "reason": "High similarity, but manual review recommended"
                })
            else:
                recommendations.append({
                    "candidate_id": str(candidate.id),
                    "action": "manual_decision",
                    "confidence": "low",
                    "reason": "Moderate similarity, requires careful review"
                })

        return recommendations
```

**Testing:**
```python
@pytest.mark.asyncio
async def test_archivist_agent(session):
    archivist = ArchivistAgent()

    # Create vault with duplicates
    vault_id = uuid4()
    aragorn = Entity(vault_id=vault_id, name="Aragorn", type=EntityType.CHARACTER)
    strider = Entity(vault_id=vault_id, name="Strider", type=EntityType.CHARACTER, aliases=["Aragorn"])
    session.add_all([aragorn, strider])
    session.commit()

    # Run archivist
    result = await archivist.run(vault_id=vault_id, session=session, threshold=0.6)

    assert result["candidates_found"] >= 1
    assert len(result["candidates"]) >= 1
    assert result["candidates"][0]["similarity_score"] > 0.6

    # Verify EntityMergeCandidate created
    candidates = session.exec(
        select(EntityMergeCandidate).where(EntityMergeCandidate.vault_id == vault_id)
    ).all()

    assert len(candidates) >= 1
```

**Acceptance Criteria:**
- ✅ ArchivistAgent finds duplicates
- ✅ Creates EntityMergeCandidate records
- ✅ Generates recommendations
- ✅ Tests pass

---

### Day 4-5: Merge Workflow Implementation

#### Objective
Build the merge workflow to consolidate duplicate entities.

#### Tasks

**2.1: Create EntityMergeService**

**File:** `src/writeros/services/entity_merge.py` (NEW FILE)

**Code:**
```python
"""
Entity Merge Service
Handles the complex process of merging duplicate entities.
"""
from typing import List, Dict, Any
from uuid import UUID
from sqlmodel import Session, select
from datetime import datetime

from writeros.schema.world import Entity, Relationship, Fact
from writeros.schema.extended_universe import EntityMergeCandidate
from writeros.schema.provenance import StateChangeEvent, CharacterKnowledge, ContentDependency


class EntityMergeService:
    """
    Merges duplicate entities and updates all references.

    Merge process:
    1. Validate merge is safe
    2. Consolidate data (names, aliases, descriptions)
    3. Update all foreign key references
    4. Mark duplicate as merged
    5. Log merge as StateChangeEvent
    """

    def __init__(self, session: Session):
        self.session = session

    def merge_entities(
        self,
        primary_id: UUID,
        duplicate_id: UUID,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Merge duplicate entity into primary entity.

        Args:
            primary_id: Entity to keep
            duplicate_id: Entity to merge (will be marked as merged)
            user_id: User who approved the merge

        Returns:
            Dict with merge summary
        """
        primary = self.session.get(Entity, primary_id)
        duplicate = self.session.get(Entity, duplicate_id)

        if not primary or not duplicate:
            raise ValueError("Entity not found")

        if primary.type != duplicate.type:
            raise ValueError("Cannot merge entities of different types")

        summary = {
            "primary_entity": {"id": str(primary.id), "name": primary.name},
            "duplicate_entity": {"id": str(duplicate.id), "name": duplicate.name},
            "updates": {
                "relationships_updated": 0,
                "facts_updated": 0,
                "knowledge_updated": 0,
                "dependencies_updated": 0
            }
        }

        # Step 1: Consolidate data
        self._consolidate_entity_data(primary, duplicate)

        # Step 2: Update Relationships
        summary["updates"]["relationships_updated"] = self._update_relationships(primary, duplicate)

        # Step 3: Update Facts
        summary["updates"]["facts_updated"] = self._update_facts(primary, duplicate)

        # Step 4: Update CharacterKnowledge
        summary["updates"]["knowledge_updated"] = self._update_character_knowledge(primary, duplicate)

        # Step 5: Update ContentDependencies
        summary["updates"]["dependencies_updated"] = self._update_content_dependencies(primary, duplicate)

        # Step 6: Mark duplicate as merged
        duplicate.status = "merged"
        duplicate.properties = duplicate.properties or {}
        duplicate.properties["merged_into"] = str(primary.id)
        duplicate.properties["merged_at"] = datetime.utcnow().isoformat()
        duplicate.properties["merged_by"] = user_id

        # Step 7: Log merge as StateChangeEvent
        merge_event = StateChangeEvent(
            vault_id=primary.vault_id,
            entity_id=primary.id,
            event_type="entity_merged",
            payload={
                "action": "entity_merged",
                "merged_entity_id": str(duplicate.id),
                "merged_entity_name": duplicate.name,
                "merged_by": user_id
            }
        )
        self.session.add(merge_event)

        # Step 8: Update EntityMergeCandidate status
        candidate = self.session.exec(
            select(EntityMergeCandidate).where(
                EntityMergeCandidate.primary_entity_id == primary.id,
                EntityMergeCandidate.duplicate_entity_id == duplicate.id
            )
        ).first()

        if candidate:
            candidate.status = "merged"
            candidate.resolved_at = datetime.utcnow()
            candidate.resolved_by = user_id
            candidate.merge_notes = "Entities successfully merged"

        self.session.commit()

        return summary

    def _consolidate_entity_data(self, primary: Entity, duplicate: Entity):
        """Merge data from duplicate into primary."""
        # Merge aliases
        primary_aliases = set(primary.aliases or [])
        duplicate_aliases = set(duplicate.aliases or [])
        primary_aliases.update(duplicate_aliases)
        primary_aliases.add(duplicate.name)  # Add duplicate name as alias
        primary.aliases = list(primary_aliases)

        # Merge descriptions (if primary is empty)
        if not primary.description and duplicate.description:
            primary.description = duplicate.description

        # Merge properties
        primary_props = primary.properties or {}
        duplicate_props = duplicate.properties or {}
        for key, value in duplicate_props.items():
            if key not in primary_props:
                primary_props[key] = value
        primary.properties = primary_props

        self.session.add(primary)

    def _update_relationships(self, primary: Entity, duplicate: Entity) -> int:
        """Update all relationships pointing to duplicate."""
        count = 0

        # Update from_entity_id references
        rels_from = self.session.exec(
            select(Relationship).where(Relationship.from_entity_id == duplicate.id)
        ).all()

        for rel in rels_from:
            # Check if relationship already exists for primary
            existing = self.session.exec(
                select(Relationship).where(
                    Relationship.from_entity_id == primary.id,
                    Relationship.to_entity_id == rel.to_entity_id,
                    Relationship.rel_type == rel.rel_type
                )
            ).first()

            if not existing:
                rel.from_entity_id = primary.id
                self.session.add(rel)
                count += 1
            else:
                # Duplicate relationship, delete
                self.session.delete(rel)

        # Update to_entity_id references
        rels_to = self.session.exec(
            select(Relationship).where(Relationship.to_entity_id == duplicate.id)
        ).all()

        for rel in rels_to:
            existing = self.session.exec(
                select(Relationship).where(
                    Relationship.from_entity_id == rel.from_entity_id,
                    Relationship.to_entity_id == primary.id,
                    Relationship.rel_type == rel.rel_type
                )
            ).first()

            if not existing:
                rel.to_entity_id = primary.id
                self.session.add(rel)
                count += 1
            else:
                self.session.delete(rel)

        return count

    def _update_facts(self, primary: Entity, duplicate: Entity) -> int:
        """Update all facts referencing duplicate."""
        count = 0

        # Update entity_id references in Facts
        facts = self.session.exec(
            select(Fact).where(Fact.entity_id == duplicate.id)
        ).all()

        for fact in facts:
            fact.entity_id = primary.id
            self.session.add(fact)
            count += 1

        return count

    def _update_character_knowledge(self, primary: Entity, duplicate: Entity) -> int:
        """Update CharacterKnowledge references."""
        count = 0

        # Update character_id
        knowledge_as_character = self.session.exec(
            select(CharacterKnowledge).where(CharacterKnowledge.character_id == duplicate.id)
        ).all()

        for k in knowledge_as_character:
            k.character_id = primary.id
            self.session.add(k)
            count += 1

        # Update subject_entity_id
        knowledge_as_subject = self.session.exec(
            select(CharacterKnowledge).where(CharacterKnowledge.subject_entity_id == duplicate.id)
        ).all()

        for k in knowledge_as_subject:
            k.subject_entity_id = primary.id
            self.session.add(k)
            count += 1

        # Update source_entity_id
        knowledge_as_source = self.session.exec(
            select(CharacterKnowledge).where(CharacterKnowledge.source_entity_id == duplicate.id)
        ).all()

        for k in knowledge_as_source:
            k.source_entity_id = primary.id
            self.session.add(k)
            count += 1

        return count

    def _update_content_dependencies(self, primary: Entity, duplicate: Entity) -> int:
        """Update ContentDependency references."""
        count = 0

        dependencies = self.session.exec(
            select(ContentDependency).where(ContentDependency.dependency_id == duplicate.id)
        ).all()

        for dep in dependencies:
            dep.dependency_id = primary.id
            dep.assumption = dep.assumption.replace(duplicate.name, primary.name)
            self.session.add(dep)
            count += 1

        return count
```

**Testing:**
```python
def test_entity_merge_service(session):
    merge_service = EntityMergeService(session)

    # Create primary and duplicate
    vault_id = uuid4()
    aragorn = Entity(
        vault_id=vault_id,
        name="Aragorn",
        type=EntityType.CHARACTER,
        description="True king",
        aliases=["Elessar"]
    )
    strider = Entity(
        vault_id=vault_id,
        name="Strider",
        type=EntityType.CHARACTER,
        description="Ranger",
        aliases=["Dunadan"]
    )
    session.add_all([aragorn, strider])
    session.commit()

    # Create relationships for duplicate
    gandalf = Entity(vault_id=vault_id, name="Gandalf", type=EntityType.CHARACTER)
    session.add(gandalf)
    session.commit()

    rel = Relationship(
        vault_id=vault_id,
        from_entity_id=strider.id,
        to_entity_id=gandalf.id,
        rel_type=RelationType.FRIEND
    )
    session.add(rel)
    session.commit()

    # Merge
    summary = merge_service.merge_entities(
        primary_id=aragorn.id,
        duplicate_id=strider.id,
        user_id="test_user"
    )

    # Verify merge
    assert summary["updates"]["relationships_updated"] > 0

    # Verify primary has consolidated data
    session.refresh(aragorn)
    assert "Strider" in aragorn.aliases
    assert "Dunadan" in aragorn.aliases
    assert "Elessar" in aragorn.aliases

    # Verify relationship updated
    rel_after = session.get(Relationship, rel.id)
    assert rel_after.from_entity_id == aragorn.id

    # Verify duplicate marked as merged
    session.refresh(strider)
    assert strider.status == "merged"
    assert strider.properties["merged_into"] == str(aragorn.id)
```

**Acceptance Criteria:**
- ✅ Merge consolidates entity data
- ✅ Updates all foreign key references
- ✅ Marks duplicate as merged
- ✅ Logs StateChangeEvent
- ✅ Tests pass

---

## Week 4: UI Integration & Advanced Features

### Day 6-8: API Endpoints & UI

#### Tasks

**3.1: Create Merge Management API**

**File:** `src/writeros/api/merge_endpoints.py` (NEW FILE)

**Code:**
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from uuid import UUID

from writeros.agents.archivist import ArchivistAgent
from writeros.services.entity_merge import EntityMergeService
from writeros.schema.extended_universe import EntityMergeCandidate
from writeros.utils.db import get_session

router = APIRouter(prefix="/api/v1/merge", tags=["entity-merge"])


@router.post("/scan/{vault_id}")
async def scan_for_duplicates(
    vault_id: str,
    threshold: float = 0.75,
    max_candidates: int = 50,
    session: Session = Depends(get_session)
):
    """
    Scan vault for duplicate entities.

    Returns list of EntityMergeCandidate objects.
    """
    try:
        archivist = ArchivistAgent()
        result = await archivist.run(
            vault_id=UUID(vault_id),
            session=session,
            threshold=threshold,
            max_candidates=max_candidates
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candidates/{vault_id}")
async def get_merge_candidates(
    vault_id: str,
    status: str = "pending",
    session: Session = Depends(get_session)
):
    """
    Get all merge candidates for a vault.

    Query params:
    - status: "pending", "approved", "rejected", "merged"
    """
    try:
        candidates = session.exec(
            select(EntityMergeCandidate).where(
                EntityMergeCandidate.vault_id == UUID(vault_id),
                EntityMergeCandidate.status == status
            ).order_by(EntityMergeCandidate.similarity_score.desc())
        ).all()

        return {
            "vault_id": vault_id,
            "status": status,
            "count": len(candidates),
            "candidates": [
                {
                    "id": str(c.id),
                    "primary_entity_id": str(c.primary_entity_id),
                    "duplicate_entity_id": str(c.duplicate_entity_id),
                    "similarity_score": c.similarity_score,
                    "evidence": c.evidence,
                    "status": c.status
                }
                for c in candidates
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve/{candidate_id}")
async def approve_merge(
    candidate_id: str,
    user_id: str = "api_user",
    session: Session = Depends(get_session)
):
    """
    Approve and execute entity merge.

    This will:
    1. Merge the duplicate into the primary
    2. Update all references
    3. Mark candidate as "merged"
    """
    try:
        candidate = session.get(EntityMergeCandidate, UUID(candidate_id))
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        if candidate.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Candidate already {candidate.status}"
            )

        # Execute merge
        merge_service = EntityMergeService(session)
        summary = merge_service.merge_entities(
            primary_id=candidate.primary_entity_id,
            duplicate_id=candidate.duplicate_entity_id,
            user_id=user_id
        )

        return {
            "status": "success",
            "message": "Entities successfully merged",
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reject/{candidate_id}")
async def reject_merge(
    candidate_id: str,
    reason: str = "",
    session: Session = Depends(get_session)
):
    """
    Reject a merge candidate.

    Marks entities as NOT duplicates.
    """
    try:
        candidate = session.get(EntityMergeCandidate, UUID(candidate_id))
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate.status = "rejected"
        candidate.resolved_at = datetime.utcnow()
        candidate.merge_notes = reason or "User rejected merge"

        session.add(candidate)
        session.commit()

        return {
            "status": "success",
            "message": "Merge candidate rejected"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Testing:**
```python
def test_merge_api_endpoints(client: TestClient):
    # Test scan
    response = client.post(f"/api/v1/merge/scan/{vault_id}")
    assert response.status_code == 200
    data = response.json()
    assert "candidates_found" in data

    # Test get candidates
    response = client.get(f"/api/v1/merge/candidates/{vault_id}")
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data

    # Test approve merge
    candidate_id = data["candidates"][0]["id"]
    response = client.post(f"/api/v1/merge/approve/{candidate_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Test reject merge
    response = client.post(
        f"/api/v1/merge/reject/{candidate_id}",
        json={"reason": "Not duplicates"}
    )
    assert response.status_code == 200
```

**Acceptance Criteria:**
- ✅ All endpoints work
- ✅ Scan finds duplicates
- ✅ Approve executes merge
- ✅ Reject marks candidate
- ✅ Tests pass

---

### Day 9-10: Integration Testing & Documentation

#### Tasks

**4.1: End-to-End Integration Test**

**File:** `tests/integration/test_entity_deduplication_e2e.py`

**Code:**
```python
@pytest.mark.asyncio
async def test_complete_deduplication_workflow(session):
    """
    Test complete deduplication workflow.

    Scenario:
    1. User creates entities "Aragorn" and "Strider"
    2. Archivist scans and detects they're duplicates
    3. User approves merge
    4. System consolidates data and updates references
    5. Verify all references updated correctly
    """
    vault_id = uuid4()

    # Step 1: Create entities
    aragorn = Entity(
        vault_id=vault_id,
        name="Aragorn",
        type=EntityType.CHARACTER,
        description="True king of Gondor",
        aliases=["Elessar", "Thorongil"]
    )
    strider = Entity(
        vault_id=vault_id,
        name="Strider",
        type=EntityType.CHARACTER,
        description="Ranger of the North",
        aliases=["Dunadan"]
    )
    gandalf = Entity(
        vault_id=vault_id,
        name="Gandalf",
        type=EntityType.CHARACTER
    )
    session.add_all([aragorn, strider, gandalf])
    session.commit()

    # Create relationships
    rel1 = Relationship(
        vault_id=vault_id,
        from_entity_id=strider.id,
        to_entity_id=gandalf.id,
        rel_type=RelationType.FRIEND
    )
    rel2 = Relationship(
        vault_id=vault_id,
        from_entity_id=aragorn.id,
        to_entity_id=gandalf.id,
        rel_type=RelationType.MENTOR
    )
    session.add_all([rel1, rel2])
    session.commit()

    # Step 2: Run Archivist
    archivist = ArchivistAgent()
    result = await archivist.run(
        vault_id=vault_id,
        session=session,
        threshold=0.6
    )

    assert result["candidates_found"] >= 1

    # Get candidate
    candidate = session.exec(
        select(EntityMergeCandidate).where(
            EntityMergeCandidate.vault_id == vault_id,
            EntityMergeCandidate.status == "pending"
        )
    ).first()

    assert candidate is not None
    assert candidate.similarity_score > 0.6

    # Step 3: Approve merge
    merge_service = EntityMergeService(session)
    summary = merge_service.merge_entities(
        primary_id=aragorn.id,
        duplicate_id=strider.id,
        user_id="test_user"
    )

    # Step 4: Verify consolidation
    session.refresh(aragorn)
    assert "Strider" in aragorn.aliases
    assert "Dunadan" in aragorn.aliases
    assert "Elessar" in aragorn.aliases

    # Step 5: Verify relationships updated
    rels_after = session.exec(
        select(Relationship).where(
            Relationship.from_entity_id == aragorn.id
        )
    ).all()

    # Should have both FRIEND and MENTOR relationships now
    # (duplicate FRIEND will be kept, since it was unique relationship)
    assert len(rels_after) >= 1

    # Step 6: Verify duplicate marked
    session.refresh(strider)
    assert strider.status == "merged"

    # Step 7: Verify candidate updated
    session.refresh(candidate)
    assert candidate.status == "merged"

    # Step 8: Verify StateChangeEvent logged
    events = session.exec(
        select(StateChangeEvent).where(
            StateChangeEvent.entity_id == aragorn.id,
            StateChangeEvent.event_type == "entity_merged"
        )
    ).all()

    assert len(events) == 1
    assert events[0].payload["merged_entity_name"] == "Strider"
```

**Acceptance Criteria:**
- ✅ Complete workflow test passes
- ✅ All steps execute correctly
- ✅ Data consolidated properly
- ✅ References updated
- ✅ Events logged

---

**4.2: Documentation**

**File:** `docs/ENTITY_DEDUPLICATION.md`

**Content:**
```markdown
# Entity Deduplication System Documentation

## Overview

The Entity Deduplication System automatically detects and merges duplicate entities using ML-based similarity scoring.

## How It Works

### 1. Detection

The **ArchivistAgent** scans the vault and calculates similarity scores using:

1. **Name Similarity** (30%) - Levenshtein distance
2. **Alias Overlap** (20%) - Shared aliases
3. **Embedding Similarity** (25%) - Semantic similarity
4. **Co-occurrence** (15%) - Appear in same scenes
5. **Relationship Overlap** (10%) - Share same connections

**Threshold:** 0.75 (configurable)

### 2. Review

System creates `EntityMergeCandidate` records with:
- Similarity score
- Evidence dictionary
- Status: "pending", "approved", "rejected", "merged"

### 3. Merge

When approved, `EntityMergeService` executes:

1. **Data Consolidation**
   - Merge aliases (add duplicate name as alias)
   - Merge descriptions
   - Merge properties

2. **Reference Updates**
   - Update all Relationships (from_entity_id, to_entity_id)
   - Update all Facts (entity_id)
   - Update CharacterKnowledge (character_id, subject_entity_id, source_entity_id)
   - Update ContentDependencies (dependency_id)

3. **Finalization**
   - Mark duplicate as "merged"
   - Log StateChangeEvent
   - Update EntityMergeCandidate status

## Usage

### Command Line

```bash
# Scan vault for duplicates
python -m writeros.scripts.scan_duplicates --vault-id <uuid> --threshold 0.75

# Auto-merge high confidence (>0.9)
python -m writeros.scripts.scan_duplicates --vault-id <uuid> --auto-merge
```

### API

```bash
# Scan for duplicates
POST /api/v1/merge/scan/{vault_id}

# Get candidates
GET /api/v1/merge/candidates/{vault_id}?status=pending

# Approve merge
POST /api/v1/merge/approve/{candidate_id}

# Reject merge
POST /api/v1/merge/reject/{candidate_id}
```

### Python API

```python
from writeros.agents.archivist import ArchivistAgent
from writeros.services.entity_merge import EntityMergeService

# Scan for duplicates
archivist = ArchivistAgent()
result = await archivist.run(vault_id=vault_id, session=session)

# Merge entities
merge_service = EntityMergeService(session)
summary = merge_service.merge_entities(
    primary_id=aragorn_id,
    duplicate_id=strider_id,
    user_id="user123"
)
```

## Examples

### Example 1: Aragorn / Strider

**Before:**
- Entity 1: name="Aragorn", aliases=["Elessar"]
- Entity 2: name="Strider", aliases=["Dunadan"]
- Relationship: Strider → FRIEND → Gandalf

**After Merge:**
- Entity 1: name="Aragorn", aliases=["Elessar", "Strider", "Dunadan"]
- Entity 2: status="merged"
- Relationship: Aragorn → FRIEND → Gandalf

### Example 2: Gandalf / Gandolf (Typo)

**Detection:**
- Name similarity: 0.93 (very high)
- Embedding similarity: 0.88
- Overall score: 0.90

**Recommendation:** AUTO_MERGE (high confidence)

## Safety Features

1. **Type Checking**: Only merges entities of same type
2. **Validation**: Checks for existing relationships before updating
3. **Rollback**: Transaction-based (rolls back on error)
4. **Audit Trail**: All merges logged as StateChangeEvent
5. **Undo**: Merged entity preserved (status="merged")

## Testing

```bash
# Run unit tests
pytest tests/test_entity_similarity.py -v

# Run integration tests
pytest tests/integration/test_entity_deduplication_e2e.py -v
```

## Configuration

**Similarity Weights** (`entity_similarity.py`):
```python
weights = {
    "name": 0.30,
    "alias": 0.20,
    "embedding": 0.25,
    "co_occurrence": 0.15,
    "relationships": 0.10
}
```

**Thresholds**:
- **High Confidence** (>0.9): Suggest auto-merge
- **Medium Confidence** (0.75-0.9): Suggest review
- **Low Confidence** (<0.75): Manual decision

## Troubleshooting

**Q: Merge failed with "different types" error**
A: Can't merge CHARACTER with LOCATION. Verify entity types match.

**Q: Some references not updated**
A: Check foreign key constraints. Verify entity IDs are valid.

**Q: Duplicate relationships after merge**
A: System deduplicates relationships automatically. Check relationship type.

## Future Enhancements

1. **Visual Diff UI**: Compare entities side-by-side
2. **Smart Consolidation**: ML decides which description to keep
3. **Batch Merge**: Merge multiple duplicates at once
4. **Undo Feature**: Revert merge operation
5. **Learning System**: Improve similarity algorithm based on user feedback
```

---

## Phase 2 Deliverables Checklist

- ✅ EntitySimilarityService (multi-signal similarity)
- ✅ ArchivistAgent (duplicate detection)
- ✅ EntityMergeService (merge workflow)
- ✅ API endpoints (scan, approve, reject)
- ✅ End-to-end integration tests
- ✅ Documentation

**Success Criteria:**
- System detects duplicates with 75%+ accuracy
- Merge consolidates all data correctly
- No data loss during merge
- All foreign key references updated
- Audit trail complete (StateChangeEvent)
- Tests pass (unit + integration)
- Documentation complete

---

# SUMMARY & ROADMAP

## Timeline Summary

**Week 1:** Provenance foundation (StateChangeEvent, CharacterKnowledge, ContentDependency)
**Week 2:** Provenance API & time-travel queries
**Week 3:** Entity similarity detection (ArchivistAgent)
**Week 4:** Entity merge workflow & UI integration

**Total:** 4 weeks (160-180 hours)

## Success Metrics

### Provenance System
- ✅ 100% of entity changes logged
- ✅ Time-travel queries return accurate results
- ✅ Retcon detection identifies affected scenes
- ✅ <100ms query latency

### Entity Deduplication
- ✅ 75%+ precision (true duplicates detected)
- ✅ 90%+ recall (few duplicates missed)
- ✅ Merge succeeds without data loss
- ✅ All references updated correctly

## Risk Mitigation

### Provenance System
- **Risk:** Performance impact of logging all changes
- **Mitigation:** Batch insert StateChangeEvents, use async logging

### Entity Deduplication
- **Risk:** False positives (non-duplicates flagged)
- **Mitigation:** Adjustable threshold, user approval required

- **Risk:** Complex merge breaks foreign keys
- **Mitigation:** Transaction rollback on error, thorough testing

## Next Steps After Completion

1. **Visual Timeline**: Build UI for state visualization
2. **Subplot System**: Implement Subplot tracking (Tier A priority)
3. **Narrator Integration**: Complete multi-POV support (Tier A priority)
4. **Historian Agent**: Build contradiction detection (Tier B priority)

---

## IMPLEMENTATION CHECKLIST

Use this checklist to track progress:

### Phase 1: Provenance System
- [ ] Day 1-2: StateChangeEvent integration
  - [ ] ProfilerAgent entity creation logging
  - [ ] Relationship change logging
  - [ ] Tests pass
- [ ] Day 3-4: CharacterKnowledge integration
  - [ ] PsychologistAgent knowledge tracking
  - [ ] ProvenanceService query methods
  - [ ] Tests pass
- [ ] Day 5-6: ContentDependency integration
  - [ ] ChronologistAgent dependency creation
  - [ ] Retcon impact analysis
  - [ ] Tests pass
- [ ] Day 7-8: Time-travel API
  - [ ] API endpoints created
  - [ ] OrchestratorAgent integration
  - [ ] Tests pass
- [ ] Day 9-10: Integration & docs
  - [ ] E2E tests pass
  - [ ] Documentation complete

### Phase 2: Entity Deduplication
- [ ] Day 1-3: Similarity detection
  - [ ] EntitySimilarityService created
  - [ ] ArchivistAgent created
  - [ ] Tests pass
- [ ] Day 4-5: Merge workflow
  - [ ] EntityMergeService created
  - [ ] Merge logic complete
  - [ ] Tests pass
- [ ] Day 6-8: API & UI
  - [ ] API endpoints created
  - [ ] Tests pass
- [ ] Day 9-10: Integration & docs
  - [ ] E2E tests pass
  - [ ] Documentation complete

---

**END OF IMPLEMENTATION PLAN**
