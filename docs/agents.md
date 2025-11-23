# WriterOS Agents

## Overview

Agents are specialized AI modules that analyze different aspects of creative writing.

## Available Agents

### ProducerAgent
**Purpose:** Ingest and process manuscripts from Obsidian vaults.

**Inputs:**
- Vault root path
- Individual markdown files

**Outputs:**
- `Source` records in database
- `Chapter` and `Scene` hierarchies

**Usage:**
```python
from writeros.agents.producer import ProducerAgent

agent = ProducerAgent(vault_root="./vault")
await agent.ingest_vault()
```

---

### ProfilerAgent
**Purpose:** Extract entities (characters, locations, factions) and their relationships.

**Inputs:**
- Full manuscript text
- Context from previous chapters

**Outputs:**
- `WorldExtractionSchema` (structured data)
- Entities with relationship networks

**Usage:**
```python
from writeros.agents.profiler import ProfilerAgent

agent = ProfilerAgent()
result = await agent.run(full_text, existing_notes, title)
```

---

### PsychologistAgent
**Purpose:** Analyze character psychology, emotional states, and character arcs.

**Inputs:**
- Scene text
- Character context

**Outputs:**
- `CharacterState` (current emotional state)
- `CharacterArc` (transformation over time)
- `TransformationMoment` (key turning points)

**Usage:**
```python
from writeros.agents.psychologist import PsychologistAgent

agent = PsychologistAgent()
result = await agent.run(full_text, existing_notes, title)
```

---

### DramatistAgent
**Purpose:** Track tension, pacing, and emotional beats across scenes.

**Inputs:**
- Scene text
- Genre context

**Outputs:**
- Tension scores (1-10)
- Emotion intensity
- Pacing analysis
- ASCII tension visualization

**Usage:**
```python
from writeros.agents.dramatist import DramatistAgent

agent = DramatistAgent()
result = await agent.run(full_text, existing_notes, title, genre="thriller")
```

---

### ArchitectAgent
**Purpose:** Manage narrative structure using story anchors.

**Inputs:**
- Vault ID
- Scene references

**Outputs:**
- `Anchor` records (plot points, character decisions)
- Narrative structure maps

**Usage:**
```python
from writeros.agents.architect import ArchitectAgent

agent = ArchitectAgent()
anchors = await agent.list_anchors(vault_id, status="active")
```

---

## Agent Orchestration

The `OrchestratorAgent` coordinates multi-agent workflows:

```python
from writeros.agents.orchestrator import OrchestratorAgent

orchestrator = OrchestratorAgent()
result = await orchestrator.run(user_query, vault_id)
```

## Extending Agents

To create a new agent:

1. Inherit from `BaseAgent`
2. Implement `async def run()`
3. Use `self.log` for structured logging
4. Define Pydantic schemas for outputs
