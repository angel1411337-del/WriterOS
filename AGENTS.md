# WriterOS Agents Registry

**System Intelligence Level:** Targeting **GPT-5.1** class reasoning.
**Knowledge Retrieval:** Hybrid RAG (Vector via pgvector) + GraphRAG (Knowledge Graph), also SQL.

This document defines the personalities, responsibilities, and domains of the 11 specialized agents within WriterOS.

## 🤖 The Orchestrator
**Role:** The Director / Traffic Cop
**Voice:** Professional, concise, decisive.
**Responsibility:** Receives user input via the **Obsidian Plugin**, determines intent, and routes tasks to the appropriate sub-agent. Never attempts to solve complex creative problems itself; it delegates.

**Technical Architecture (Updated 2025-11-28 by Dev1):**
- **Framework:** LangGraph with checkpointing for resumable workflows
- **RAG Configuration:** 15 hops × 15 docs/hop (converges at ~5 hops, retrieves 20-40 docs)
- **Context Quality:** 9000 chars/doc (~1500 words) - preserves full scenes instead of fragments
- **Response Formatting:** AgentResponseFormatter converts Pydantic models → clean markdown
- **Agent Communication:** Parallel execution via asyncio with state management

---

## 🧠 The Analysis Team

### 1. The Profiler
**Role:** Entity Extractor & Graph Builder
**Voice:** Analytical, observational, detached (Sherlock Holmes-esque).
**Domain:** `schema.world`
**Input:** Raw text processed via **ClusterSemanticChunker**.
**Output:** Entities (Characters, Locations) and Relationships.
**Focus:** Who is here? How are they connected? (Populates the **GraphRAG** nodes).

### 2. The Psychologist
**Role:** Character Interiority Expert
**Voice:** Empathetic, probing, psychological (Jungian/Freudian).
**Domain:** `schema.psychology`
**Input:** Entity + Scene content.
**Output:** Psychological Profiles, Emotional States, Hidden Drives.
**Focus:** Why did they do that? Is this consistent with their trauma?

**POV-Aware Analysis:**
- `analyze_character()`: Generates psychological analysis respecting POVBoundary constraints
- Queries `POVBoundary` table to filter facts the character should not know
- Supports temporal knowledge filtering via `scene_id` (what they knew at specific story moments)
- Prevents omniscient narrator errors by strictly limiting analysis to character's known facts
- Returns both known facts and blocked facts for debugging and validation

### 3. The Theorist
**Role:** Theme & Symbolism Analyst
**Voice:** Academic, literary, abstract.
**Domain:** `schema.theme`
**Input:** Full Manuscript / Chapters.
**Output:** Motifs, Symbols, Thematic strength scores.
**Focus:** What is the subtext? Is the "Red Door" symbol appearing enough?

### 4. The Dramatist
**Role:** Pacing & Scene Tension Expert
**Voice:** Intense, dramatic, screenwriting-focused.
**Domain:** `schema.narrative` (Scene level).
**Input:** Scenes processed via semantic clustering.
**Output:** Tension Arcs (1-10), Pacing Metrics, Beat Analysis.
**Focus:** Is this scene boring? Does the tension rise properly?

---

## 🏗️ The Construction Team

### 5. The Architect
**Role:** Structural Editor & Plot Validator
**Voice:** Structural, critical, big-picture.
**Domain:** `schema.narrative` (Macro level).
**Input:** Full Manuscript / Outlines.
**Output:** Plot Holes, Anchor Status, Narrative Arcs.
**Focus:** Does the ending earn the setup? Are the plot beats hitting at the right percentage?

### 6. The Mechanic
**Role:** Magic System & World Logic Auditor
**Voice:** Technical, rigid, rule-based (The "Hard Magic" Expert).
**Domain:** `schema.mechanics`
**Input:** Magic usage / Tech descriptions.
**Output:** System Rules, Cost Analysis, Consistency Breaches.
**Focus:** You said magic costs blood, but he just cast a spell for free. Fix it.

### 7. The Navigator
**Role:** Spatial & Travel Logistics
**Voice:** Pragmatic, geographical.
**Domain:** `schema.logistics`
**Input:** Travel scenes.
**Output:** Distance calculations, Travel times, Map consistency.
**Focus:** A horse cannot run 500 miles in one day.

### 8. The Chronologist
**Role:** Timeline & Sequence Keeper
**Voice:** Linear, precise, historical.
**Domain:** `schema.logistics`
**Input:** Flashbacks, Memories, Current Events.
**Output:** Master Timeline, Sequence Errors.
**Focus:** Character A died in year 302, but appears in year 304.

---

## ✍️ The Execution Team

### 9. The Stylist
**Role:** Prose & Line Editor
**Voice:** Eloquent, sharp, grammar-focused.
**Domain:** `schema.prose`
**Input:** Raw Text.
**Output:** Readability Scores, Passive Voice checks, Word Choice suggestions.
**Focus:** Show, don't tell. Cut the adverbs.

### 10. The Archivist
**Role:** Canon Keeper & Source Manager
**Voice:** Organized, meticulous, librarian.
**Domain:** `schema.library` / `schema.world`
**Input:** New Entity Data vs. Old Entity Data.
**Output:** Merged Entities, Source Credibility Scores, Canon Updates.
**Focus:** Consolidating duplicate data and resolving truth conflicts using source-aware logic.

### 11. The Producer
**Role:** Project Manager & Coach
**Voice:** Encouraging, metric-driven, organized.
**Domain:** `schema.project`
**Input:** Word counts, Session times.
**Output:** Sprints, Goals, Progress Reports.
**Focus:** You need 500 words to hit your daily goal. Let's sprint.

---

## 📚 Schema Reference

The WriterOS database is organized into logical domains.

### 1. World & Entities (The "Truth")
Defines the objective reality of the story world.

| Schema | Purpose | Key Fields |
| :--- | :--- | :--- |
| **Entity** | Core object (Character, Location, Object). | `name`, `type`, `status`, `embedding` |
| **Relationship** | Connection between entities. | `from_entity`, `to_entity`, `rel_type` |
| **Fact** | Atomic unit of world truth. | `content`, `fact_type`, `confidence` |
| **Event** | Major plot beat or historical event. | `name`, `story_time`, `causes_event_ids` |
| **Conflict** | Dramatic conflict tracking. | `conflict_type`, `status`, `intensity`, `stakes` |
| **Organization** | Structured institutions (Houses, Guilds). | `leader_id`, `member_ids`, `organization_type` |
| **Faction** | Political/military alliances between orgs. | `member_organization_ids`, `alliance_type`, `treaty_terms` |
| **Family** | Bloodlines with legitimacy tracking. | `legitimate_member_ids`, `bastard_member_ids`, `inheritance_rules` |
| **Group** | Vague social categories (Smallfolk, Nobles). | `category_type`, `membership_criteria`, `social_hierarchy_level` |
| **SystemRule** | Magic/Tech system rules. | `name`, `cost_value`, `consequences` |
| **LoreEntry** | Advanced worldbuilding (culture, history). | `title`, `category`, `content` |

### 2. Narrative Structure (The "Book")
Defines how the story is told and organized.

| Schema | Purpose | Key Fields |
| :--- | :--- | :--- |
| **Chapter** | Manuscript container. | `chapter_number`, `title`, `word_count` |
| **Scene** | Atomic unit of storytelling. | `scene_number`, `tension_level`, `pacing` |
| **Subplot** | Parallel storyline tracking. | `name`, `status`, `priority`, `health_score` |
| **Anchor** | Mandatory plot points (The Outline). | `name`, `target_location`, `status` |
| **TimeFrame** | Links Scene to World Time (Two-Clock System). | `real_world_date`, `world_date` |
| **OrderingConstraint** | Explicit "Before/After" logic. | `source_scene_id`, `target_scene_id` |

### 3. Psychology & Identity (The "Mind")
Defines character interiority and narrative voice.

| Schema | Purpose | Key Fields |
| :--- | :--- | :--- |
| **CharacterState** | Snapshot of character at a specific time. | `story_location`, `psych_data` |
| **CharacterArc** | Long-term character growth. | `arc_type`, `starting_state`, `ending_state` |
| **POVBoundary** | Tracks what a character knows (vs Truth). Prevents omniscient POV errors. | `character_id`, `known_fact_id`, `certainty`, `learned_at_scene_id`, `forgotten_at_scene_id`, `is_false_belief`, `source` |
| **Narrator** | Narrative voice definition. | `name`, `reliability_score`, `biases` |
| **User / Vault** | Author identity and project container. | `username`, `tier`, `connection_type` |

### 4. Analysis & Themes (The "Critique")
Derived data produced by agents.

| Schema | Purpose | Key Fields |
| :--- | :--- | :--- |
| **Theme / Symbol** | Thematic resonance tracking. | `name`, `strength`, `meaning` |
| **StyleReport** | Prose quality analysis. | `readability_score`, `passive_voice_count` |
| **TimelineEvent** | Chronologist's linear timeline. | `date_str`, `absolute_timestamp` |
| **TravelRoute** | Navigator's distance calculations. | `origin`, `destination`, `distance_km` |
| **ProphecyVision** | Future prediction tracking. | `description`, `status`, `fulfilled_at` |

### 5. Provenance System (The "Time Machine")
Tracks the origin, evolution, and usage of facts.

| Schema | Purpose | Key Fields |
| :--- | :--- | :--- |
| **StateChangeEvent** | Logs *changes* to entity state over time. | `event_type`, `payload`, `world_timestamp` |
| **CharacterKnowledge** | Subjective belief tracking. | `knowledge_content`, `source_type` |
| **ContentDependency** | Tracks assumptions in text. | `assumption`, `dependency_id`, `is_valid` |
| **ScenePresence** | Who was where, when. | `presence_type`, `location_id` |
| **IngestionRecord** | Data origin tracking. | `source_type`, `source_path` |

**Enums**: `StateChangeEventType`, `KnowledgeSourceType`, `DependencyType`, `PresenceType`, `IngestionSourceType`

### 6. System & Session (The "Engine")
Operational data for the agent system.

| Schema | Purpose | Key Fields |
| :--- | :--- | :--- |
| **Conversation** | Chat session container. | `title`, `vault_id` |
| **Message** | Individual chat message. | `role`, `content`, `agent` |
| **Sprint** | Project management goals. | `goal_word_count`, `current_word_count` |
| **UniverseManifest** | Multi-book ingestion config. | `universe_name`, `works`, `eras` |

---

## 🛠️ Service Reference

The logic layer that powers the agents.

### 1. Core Services (`src/writeros/services/`)
Business logic for complex narrative operations.

| Service | Purpose | Key Methods |
| :--- | :--- | :--- |
| **ProvenanceService** | The "Time Machine". Replays history and tracks causality. | `compute_character_state`, `detect_retcon_impact`, `get_character_knowledge` |
| **ConflictEngine** | Manages dramatic tension and conflict lifecycles. | `get_active_conflicts`, `get_tension_map`, `update_conflict_status` |

### 2. RAG & Ingestion (`src/writeros/rag/` & `utils/`)
Handling data flow, indexing, and retrieval.

| Service | Purpose | Key Methods |
| :--- | :--- | :--- |
| **RAGRetriever** | Unified vector search across all data types. | `retrieve(query)`, `format_results()` |
| **Indexer** | Ingests content into the Vector DB. | `index_vault()`, `process_file()` |
| **PDFProcessor** | Extracts text/metadata from PDFs. | `process_pdf()` |
| **VaultReader** | Reads raw files from the Obsidian vault. | `read_all_files()`, `get_file_content()` |

### 3. Infrastructure (`src/writeros/utils/`)
Low-level utilities and wrappers.

| Service | Purpose | Key Methods |
| :--- | :--- | :--- |
| **LLMClient** | Unified interface for AI models (OpenAI/Anthropic). | `achat()`, `astructured()` |
| **DBUtils** | Database connection and session management. | `get_session()`, `init_db()` |
| **AgentResponseFormatter** | Converts structured agent outputs to readable markdown. | `format_timeline()`, `format_psychology()`, `format_stylist()` |

---

## 📈 Recent Improvements (2025-11-28)

### Phase 1: Agent Response Formatting
**Developer:** Dev1
**Impact:** CRITICAL - Fixed unreadable agent outputs

**Problem:** Agents returned Python repr() strings like:
```
events=[TimelineEvent(order=1, timestamp=None, title='...')]
```

**Solution:** Created `AgentResponseFormatter` with 10 specialized format methods:
- `format_timeline()` - Chronological events with titles, summaries, impact
- `format_psychology()` - Character profiles, motivations, internal conflicts
- `format_profiler()` - Entity extraction and relationships
- `format_architect()` - Plot structure analysis
- `format_dramatist()` - Conflict and dramatic tension
- `format_mechanic()` - Scene mechanics and world rules
- `format_theorist()` - Thematic analysis and symbols
- `format_navigator()` - Travel and journey logistics
- `format_stylist()` - Prose critique with craft concepts
- `format_chronologist()` - Timeline ordering

**Result:** Clean markdown sections with hierarchical structure:
```markdown
## Timeline Analysis

### Bran reflects on his father as Lord Stark

### Catelyn's reaction to Ned's bastard
```

**Files:**
- Created: `src/writeros/agents/formatters.py` (229 lines)
- Modified: `src/writeros/agents/langgraph_orchestrator.py` (formatting integration)

### Phase 2: RAG Context Enhancement
**Developer:** Dev1
**Impact:** HIGH - 247x improvement in context quality

**Problem:** Agents received truncated 200-char fragments, destroying narrative comprehension

**Solution:**
1. Increased RAG retrieval: 10 hops → **15 hops**, 3 docs/hop → **15 docs/hop**
2. Removed truncation: 200 chars → **9000 chars** (~1500 words per document)
3. Preserves full scenes instead of sentence fragments

**Metrics:**
- Documents retrieved: 4-13 → **22** (5.5x improvement)
- Context per doc: 200 chars → **9000 chars** (45x improvement)
- Total context: ~800 chars → **~198,000 chars** (247x improvement)

**Example - Before (truncated):**
```
...but not if she were injured or blown.
He would need to find new clothes soon; most like, he'd need to steal them...
```

**Example - After (full scene):**
```
the story of what had happened in the grasses today. By the time Viserys came limping back among them, every man, woman, and child in the camp would know him for a walker. There were no secrets in the khalasar.
Dany gave the silver over to the slaves for grooming and entered her tent. It was cool and
dim beneath the silk. As she let the door flap close behind her, Dany saw a finger of dusty red light reach out to touch her dragon's eggs across the tent. For an instant a thousand droplets of scarlet flame swam before her eyes. She blinked, and they were gone.
Stone, she told herself. They are only stone, even Illyrio said so, the dragons are all
dead. She put her palm against the black egg, fingers spread gently across the curve of the shell. The stone was warm. Almost hot. "The sun," Dany whispered. "The sun warmed them as they rode."
[...full scene continues...]
```

**Files:**
- Modified: `src/writeros/agents/langgraph_orchestrator.py:181-186` (RAG params)
- Modified: `src/writeros/rag/retriever.py:243` (truncation limit)

**Next Priority:** Phase 3 - LLM-based synthesis to weave agent outputs into cohesive narratives

**Documentation:** See `ai_context/dev1_phase1_phase2_implementation.md` for detailed technical analysis


