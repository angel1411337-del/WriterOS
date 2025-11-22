import os
import re
import json
import logging
from pathlib import Path
from typing import List, Optional, Any

# --- DATABASE IMPORTS ---
from sqlmodel import Session, select
from utils.db import engine
from agents.schema import Entity, Relationship, EntityType, RelationType, CanonLayer

logger = logging.getLogger(__name__)

class ObsidianWriter:
    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.dirs = {
            "craft": self.vault_path / "Writing_Bible",
            "chars": self.vault_path / "Story_Bible" / "Characters",
            "locs": self.vault_path / "Story_Bible" / "Locations",
            "orgs": self.vault_path / "Story_Bible" / "Organizations",
            "systems": self.vault_path / "Story_Bible" / "Systems",
        }
        for d in self.dirs.values():
            d.mkdir(parents=True, exist_ok=True)

        self.history_file = self.vault_path / "processed_videos.json"
        self.processed_ids = self._load_history()

    def _load_history(self) -> List[str]:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f: return json.load(f)
            except: return []
        return []

    def mark_as_processed(self, video_id: str):
        if video_id not in self.processed_ids:
            self.processed_ids.append(video_id)
            with open(self.history_file, 'w') as f: json.dump(self.processed_ids, f)

    def is_processed(self, video_id: str) -> bool:
        return video_id in self.processed_ids

    def _sanitize(self, title: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '', title)[:100].strip()

    def get_existing_notes(self) -> str:
        existing = []
        for root, dirs, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(".md"): existing.append(file[:-3])
        return ", ".join(existing[:500])

    # --- 🟢 DATABASE SYNC HELPER ---
    def _sync_entity(self, name: str, type_: EntityType, desc: str, props: dict):
        """Upserts an Entity into Postgres."""
        try:
            with Session(engine) as session:
                # Check if exists
                statement = select(Entity).where(Entity.name == name)
                entity = session.exec(statement).first()

                if not entity:
                    entity = Entity(
                        name=name,
                        type=type_,
                        vault_id="00000000-0000-0000-0000-000000000000" # Default
                    )

                # Update
                entity.description = desc
                entity.properties = props
                session.add(entity)
                session.commit()
                session.refresh(entity)
                return entity.id
        except Exception as e:
            logger.error(f"❌ DB Sync Failed for {name}: {e}")
            return None

    def _sync_relationship(self, source_name: str, target_name: str, rel_type: str, details: str):
        """Syncs a relationship edge to Postgres."""
        try:
            with Session(engine) as session:
                # Get IDs
                src = session.exec(select(Entity).where(Entity.name == source_name)).first()
                tgt = session.exec(select(Entity).where(Entity.name == target_name)).first()

                if src and tgt:
                    # Check if relationship exists
                    stmt = select(Relationship).where(
                        Relationship.from_entity_id == src.id,
                        Relationship.to_entity_id == tgt.id
                    )
                    rel = session.exec(stmt).first()

                    if not rel:
                        # Map string type to Enum if possible, else default
                        try:
                            enum_type = RelationType(rel_type.lower())
                        except:
                            enum_type = RelationType.RELATED_TO

                        rel = Relationship(
                            vault_id=src.vault_id,
                            from_entity_id=src.id,
                            to_entity_id=tgt.id,
                            rel_type=enum_type,
                            description=details
                        )
                        session.add(rel)
                        session.commit()
        except Exception as e:
            logger.error(f"❌ DB Rel Sync Failed {source_name}->{target_name}: {e}")

    # --- WRITING LOGIC (Dual Write) ---

    def update_story_bible(self, story_data, source_title):
        if not story_data: return

        # 1. Characters
        for char in story_data.characters:
            # A. Write to File
            path = self.dirs['chars'] / f"{self._sanitize(char.name)}.md"
            visuals = "\n".join([f"| **{t.feature}** | {t.description} |" for t in char.visual_traits])

            mermaid_lines = []
            if char.relationships:
                for r in char.relationships:
                    target = r.target.replace(" ", "_")
                    source = char.name.replace(" ", "_")
                    # Visual Graph Logic
                    rel_type = r.rel_type.lower() if r.rel_type else "related"
                    if rel_type in ["parent", "sibling", "child", "spouse", "mother", "father"]:
                        arrow = f"{source} =={r.rel_type}==> {target}"
                    elif rel_type in ["enemy", "rival", "nemesis"]:
                        arrow = f"{source} -. {r.rel_type} .-> {target}"
                    else:
                        arrow = f"{source} --{r.rel_type}--> {target}"
                    mermaid_lines.append(f"    {arrow}")

                    # B. Sync Relationship to DB
                    self._sync_relationship(char.name, r.target, r.rel_type, r.details)

            mermaid = f"```mermaid\ngraph TD;\n" + "\n".join(mermaid_lines) + "\n```" if mermaid_lines else ""

            if not path.exists():
                template = f"""---
tags: [Character]
---
# {char.name}
> [!infobox]
> | Role | {char.role} |

## Visuals
{visuals}

## Relationships
{mermaid}

## Psychology
*(Run Psychologist)*
"""
                with open(path, 'w', encoding='utf-8') as f: f.write(template)

            # C. Sync Entity to DB
            props = {"role": char.role, "visuals": [v.dict() for v in char.visual_traits]}
            self._sync_entity(char.name, EntityType.CHARACTER, f"Role: {char.role}", props)

        # 2. Organizations
        for org in story_data.organizations:
            path = self.dirs['orgs'] / f"{self._sanitize(org.name)}.md"
            if not path.exists():
                content = f"# {org.name}\n**Type:** {org.org_type}\n**Leader:** {org.leader}"
                with open(path, 'w', encoding='utf-8') as f: f.write(content)

            # DB Sync
            self._sync_entity(org.name, EntityType.FACTION, org.ideology, {"type": org.org_type, "leader": org.leader})

    def update_navigation_data(self, nav_data, source_title):
        if not nav_data: return
        for loc in nav_data.locations:
            # ... (previous setup code) ...

            mermaid = ""
            if loc.connections:
                lines = []
                for conn in loc.connections:
                    target = self._sanitize(conn.target_location).replace(" ", "_")
                    source = safe_name.replace(" ", "_")

                    # ✅ UPDATE: Include Context in the graph label
                    # If context exists, label becomes: "3 days (Dangerous)"
                    # If not: "3 days"
                    label = conn.travel_time
                    if conn.context:
                        label += f" ({conn.context})"

                    lines.append(f"    {source} -- {label} --> {target}")

                    # DB Sync Edge (Pass context as description)
                    self._sync_relationship(
                        loc.name,
                        conn.target_location,
                        "connected_to",
                        f"{conn.travel_time} via {conn.travel_method}. {conn.context or ''}"
                    )

                if lines: mermaid = "```mermaid\ngraph LR;\n" + "\n".join(lines) + "\n```"

            # ... (rest of the method) ...

                content = f"# {loc.name}\n> Region: {loc.region}\n\n{loc.description}\n\n{mermaid}"

                if not path.exists():
                    with open(path, 'w', encoding='utf-8') as f: f.write(content)

                # DB Sync Entity
                self._sync_entity(loc.name, EntityType.LOCATION, loc.description, {"region": loc.region})

    def update_psych_profiles(self, psych_data):
        if not psych_data: return
        for profile in psych_data.profiles:
            # File Update logic
            path = self.dirs['chars'] / f"{self._sanitize(profile.name)}.md"
            lie = f"\n> **The Lie:** {profile.lie_believed}" if profile.lie_believed else ""
            truth = f"\n> **The Truth:** {profile.truth_to_learn}" if profile.truth_to_learn else ""

            psych_block = f"""
## 🧠 Psychology
> [!note] Internal State
> **Archetype:** {profile.archetype}
> **Alignment:** {profile.moral_alignment}
> **Style:** {profile.decision_making_style}
>
> **Core Desire:** {profile.core_desire}
> **Core Fear:** {profile.core_fear}
>{lie}{truth}
"""
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f: content = f.read()
                if "## 🧠 Psychology" in content:
                    parts = content.split("## 🧠 Psychology")
                    content = parts[0] + psych_block
                else:
                    content += psych_block
                with open(path, 'w', encoding='utf-8') as f: f.write(content)

            # DB Sync Fact/Entity Update
            self._sync_entity(profile.name, EntityType.CHARACTER, f"Archetype: {profile.archetype}", profile.dict())

    def update_craft_bible(self, craft_data, url, title):
        if not craft_data: return
        for c in craft_data.concepts:
            path = self.dirs['craft'] / c.genre_context / "Concepts" / f"{self._sanitize(c.name)}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"# {c.name}\n{c.definition}")

    # --- MECHANIC WRITER (Upgraded with Enum Mapping) ---
    def update_systems(self, mech_data, source_title):
        if not mech_data: return

        # ✅ MAPPING LAYER: Agent String -> Database Enum
        # This prevents crashes if the agent outputs "Biology" or "Economy"
        type_map = {
            "Magic": EntityType.MAGIC_SYSTEM,
            "Technology": EntityType.TECH_SYSTEM,
            "Biology": EntityType.TECH_SYSTEM, # Maps Bio to Tech
            "Economy": EntityType.TECH_SYSTEM  # Maps Economy to Tech
        }

        for sys in mech_data.systems:
            # 1. Write to Obsidian File
            path = self.dirs['systems'] / f"{self._sanitize(sys.name)}.md"

            # Ability Table
            ability_rows = []
            for a in sys.abilities:
                row = f"| **{a.name}** | {a.cost} | {a.limitations} |"
                ability_rows.append(row)
            ability_table = "\n".join(ability_rows)

            # Tech Tree (Mermaid)
            mermaid_lines = []
            for a in sys.abilities:
                if a.prerequisites:
                    # Clean names
                    src = self._sanitize(a.prerequisites).replace(" ", "_")
                    tgt = self._sanitize(a.name).replace(" ", "_")
                    mermaid_lines.append(f"    {src} --> {tgt}")

            tech_tree = ""
            if mermaid_lines:
                tech_tree = "### 🌳 Tech Tree\n```mermaid\ngraph TD;\n" + "\n".join(mermaid_lines) + "\n```\n"

            content = f"""---
tags: [System, Type/{sys.type}]
---
# {sys.name}

> [!summary] System Core
> **Type:** {sys.type}
> **Origin:** {sys.origin}
> **Source:** [[{source_title}]]

## 📜 Hard Rules
{chr(10).join([f"- **{r.name}**: {r.description} *(Cost: {r.consequence or 'None'})*" for r in sys.rules])}

## ⚡ Abilities
| Ability | Cost | Limits |
|---|---|---|
{ability_table}

{tech_tree}
"""
            if not path.exists():
                with open(path, 'w', encoding='utf-8') as f: f.write(content)

            # 2. Sync to Postgres (Heavy Metal)

            # ✅ USE THE MAPPING
            db_type = type_map.get(sys.type, EntityType.TECH_SYSTEM)

            # Create System Entity
            sys_id = self._sync_entity(
                sys.name,
                db_type,
                f"Origin: {sys.origin}",
                {"rules": [r.dict() for r in sys.rules]}
            )

            # Create Abilities & Edges
            if sys_id:
                for a in sys.abilities:
                    # Sync Ability Entity
                    ab_id = self._sync_entity(
                        a.name,
                        EntityType.ABILITY,
                        a.limitations,
                        {"cost": a.cost}
                    )
                    # Link System -> Ability
                    self._sync_relationship(sys.name, a.name, "has_ability", "System Grant")

                    # Link Prerequisite -> Ability (Tech Tree Edge)
                    if a.prerequisites:
                        self._sync_relationship(a.prerequisites, a.name, "requires", "Prerequisite")

            logger.info(f"   ⚙️ Updated System: {sys.name} (Mapped {sys.type} -> {db_type.value})")