# WriterOS Database Schema

## Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│   Source    │───────│    Chapter       │───────│    Scene    │
│  (Novel)    │  1:N  │  (Chapter 1)     │  1:N  │   (Scene)   │
└─────────────┘       └──────────────────┘       └─────────────┘
                              │
                              │ 1:N
                              ▼
                      ┌──────────────┐
                      │   Anchor     │
                      │ (Plot Point) │
                      └──────────────┘

┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   Entity     │◄──────│  Relationship    │──────►│   Entity     │
│ (Character)  │  N:M  │  (FRIEND_OF)     │  N:M  │ (Character)  │
└──────────────┘       └──────────────────┘       └──────────────┘
       │
       │ 1:N
       ▼
┌──────────────────┐
│  CharacterState  │
│  (Emotional)     │
└──────────────────┘
```

## Core Tables

### `entities`
Represents story world elements (characters, locations, factions, items).

**Columns:**
- `id` (UUID) - Primary key
- `vault_id` (UUID) - Vault ownership
- `name` (VARCHAR) - Entity name
- `type` (ENUM) - EntityType (CHARACTER, LOCATION, FACTION, ITEM, EVENT)
- `description` (TEXT) - Full description
- `embedding` (VECTOR) - Semantic embedding for search
- `canon` (JSONB) - Canon info (layer, status)
- `properties` (JSONB) - Type-specific metadata
- Timestamps: `created_at`, `updated_at`

**Indexes:**
- Primary key on `id`
- Index on `vault_id`
- Vector index on `embedding` (using HNSW)

---

### `relationships`
Directed edges between entities.

**Columns:**
- `id` (UUID) - Primary key
- `vault_id` (UUID)
- `from_entity_id` (UUID) - Source entity
- `to_entity_id` (UUID) - Target entity
- `rel_type` (ENUM) - RelationType (PARENT, SIBLING, FRIEND, ENEMY, etc.)
- `strength` (FLOAT) - Relationship strength (0-1)
- `details` (TEXT) - Context/leverage
- `effective_from` (JSONB) - Temporal start
- `effective_until` (JSONB) - Temporal end
- `canon` (JSONB)

**Foreign Keys:**
- `from_entity_id` → `entities.id`
- `to_entity_id` → `entities.id`

---

### `sources`
Top-level manuscripts (novels, series).

**Columns:**
- `id` (UUID)
- `vault_id` (UUID)
- `title` (VARCHAR)
- `author` (VARCHAR)
- `genre` (VARCHAR)
- `metadata_` (JSONB)

---

### `chapters`
Chapters within a source.

**Columns:**
- `id` (UUID)
- `source_id` (UUID) → `sources.id`
- `chapter_number` (INT)
- `title` (VARCHAR)
- `summary` (TEXT)

---

### `scenes`
Individual scenes.

**Columns:**
- `id` (UUID)
- `chapter_id` (UUID) → `chapters.id`
- `scene_number` (INT)
- `content` (TEXT) - Raw markdown
- `setting` (VARCHAR)
- `participants` (ARRAY<UUID>)

---

### `character_states`
Emotional states of characters at specific story points.

**Columns:**
- `id` (UUID)
- `character_id` (UUID) → `entities.id`
- `scene_id` (UUID) → `scenes.id`
- `emotion` (VARCHAR)
- `motivation` (TEXT)
- `internal_conflict` (TEXT)
- `story_time` (JSONB)

---

### `anchors`
Narrative structure nodes (plot points, decisions, setups/payoffs).

**Columns:**
- `id` (UUID)
- `vault_id` (UUID)
- `anchor_type` (ENUM) - PLOT_POINT, CHARACTER_DECISION, WORLDBUILDING, etc.
- `title` (VARCHAR)
- `description` (TEXT)
- `scene_id` (UUID) → `scenes.id`
- `status` (ENUM) - active, resolved, abandoned

---

## Enums

### EntityType
- CHARACTER
- LOCATION
- FACTION
- ITEM
- EVENT

### RelationType
- PARENT / CHILD / SIBLING (family)
- FRIEND / ALLY
- ENEMY / RIVAL
- MEMBER_OF / LEADS (factions)
- LOCATED_IN (location)

### AnchorType
- PLOT_POINT
- CHARACTER_DECISION
- SETUP_PAYOFF
- WORLDBUILDING

## Migrations

Managed with Alembic:

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```
