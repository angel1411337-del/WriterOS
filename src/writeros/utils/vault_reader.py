import os
import re
from pathlib import Path
from typing import Dict, List, Set

class VaultRegistry:
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.story_bible = self.vault_path / "Story_Bible"
        self.writing_bible = self.vault_path / "Writing_Bible"
        self.project_bible = self.vault_path / "00_Project_Bible" # <--- NEW: Project Management

        # Memory Cache
        self.entities: Dict[str, str] = {} # Story Context
        self.craft_rules: Dict[str, str] = {} # Writing Advice
        self.aliases: Dict[str, str] = {}

        self.refresh_index()

    def refresh_index(self):
        """Scans Story Bible, Writing Bible, and Project Bible."""
        print("📖 Vault Registry: Reading files...")

        # Clear cache to ensure fresh state on reload
        self.entities = {}
        self.craft_rules = {}
        self.aliases = {}

        # 1. Index Story Bible (The Lore)
        # Added "Timeline" to the list
        if self.story_bible.exists():
            for category in ["Characters", "Locations", "Organizations", "Systems", "Timeline"]:
                folder = self.story_bible / category
                if folder.exists():
                    for file in folder.glob("*.md"):
                        self._index_entity(file, category)

        # 2. Index Writing Bible (The Rules)
        if self.writing_bible.exists():
            for file in self.writing_bible.rglob("*.md"):
                self._index_craft(file)

        print(f"✅ Indexed {len(self.entities)} lore items and {len(self.craft_rules)} craft rules.")

    def _index_entity(self, file_path: Path, category: str):
        try:
            content = file_path.read_text(encoding="utf-8")
            name = file_path.stem
            self.entities[name] = f"[{category}] {content}"

            # Alias extraction
            alias_match = re.search(r"aliases:\s*\[(.*?)\]", content)
            if alias_match:
                for alias in alias_match.group(1).split(","):
                    clean = alias.strip()
                    if clean: self.aliases[clean] = name
        except Exception as e:
            print(f"❌ Error reading entity {file_path}: {e}")

    def _index_craft(self, file_path: Path):
        try:
            content = file_path.read_text(encoding="utf-8")
            self.craft_rules[file_path.stem] = content
        except Exception as e:
            print(f"❌ Error reading craft rule {file_path}: {e}")

    # --- RETRIEVAL METHODS ---

    def get_relevant_context(self, draft_text: str) -> str:
        """
        ARCHITECT USE: Scans a full chapter draft for any mentioned entities.
        (Previously called 'get_local_context' in the new design, kept as 'relevant' for compatibility)
        """
        relevant = []
        found = set()

        # Direct Match & Alias Match
        for name, content in self.entities.items():
            # Regex boundary match to avoid partial words (e.g. "Sam" inside "Sample")
            if re.search(r'\b' + re.escape(name) + r'\b', draft_text, re.IGNORECASE):
                if name not in found:
                    relevant.append(content)
                    found.add(name)

        for alias, real_name in self.aliases.items():
            if re.search(r'\b' + re.escape(alias) + r'\b', draft_text, re.IGNORECASE):
                if real_name not in found and real_name in self.entities:
                    relevant.append(self.entities[real_name])
                    found.add(real_name)

        if not relevant: return "No specific Story Bible entities detected."
        return "\n---\n".join(relevant)

    def get_local_context(self, query: str) -> str:
        """
        PRODUCER USE: Same logic as relevant_context, but semantic alias for chat queries.
        """
        return self.get_relevant_context(query)

    def get_craft_context(self) -> str:
        """STYLIST USE: Returns list of available writing rules."""
        if not self.craft_rules:
            return "No custom writing rules found. Use general best practices."
        rules_list = list(self.craft_rules.keys())
        return f"The user has studied the following concepts: {', '.join(rules_list)}. Reference these if applicable."

    def get_global_context(self) -> str:
        """
        PRODUCER USE: High-level overview of the project state.
        Reads the Project Bible files and lists Entity stats.
        """
        context = "--- GLOBAL PROJECT STATE ---\n"

        # 1. Project Bible (Roadmap/Backlog)
        if self.project_bible.exists():
            for file in self.project_bible.glob("*.md"):
                context += f"\n### File: {file.name}\n{file.read_text(encoding='utf-8')}\n"
        else:
            context += "(No Project Bible folder found at '00_Project_Bible')\n"

        # 2. Story Bible Stats (Table of Contents)
        context += "\n--- STORY BIBLE INDEX ---\n"
        context += f"Total Entities: {len(self.entities)}\n"
        # List a few examples to give the agent context on what exists
        chars = [n for n in self.entities if '[Characters]' in self.entities[n]]
        locs = [n for n in self.entities if '[Locations]' in self.entities[n]]
        context += f"Characters ({len(chars)}): {', '.join(chars[:10])}...\n"
        context += f"Locations ({len(locs)}): {', '.join(locs[:10])}...\n"

        return context

    # --- NEW: AGENTIC TRAVERSAL HELPERS ---

    def execute_structured_query(self, entity_type: str, key: str, value: str) -> List[str]:
        """
        Simulates SQL WHERE clause on Markdown files.
        Usage: execute_structured_query("Character", "Role", "Villain")
        """
        results = []

        for name, content in self.entities.items():
            # 1. Check Type (e.g. [Character])
            if entity_type and f"[{entity_type}]" not in content:
                continue

            # 2. Check Property (Regex for "**Key:** Value")
            # This is a fuzzy check for V2. In V3/Postgres this becomes a real DB query.
            if key and value:
                if value.lower() in content.lower():
                    results.append(name)
            elif entity_type:
                results.append(name)

        return results

    def get_neighbors(self, entity_name: str) -> List[str]:
        """
        Finds all WikiLinks [[Target]] inside a file.
        Used by the Producer to 'walk' the graph.
        """
        if entity_name not in self.entities:
            return []

        content = self.entities[entity_name]
        links = re.findall(r'\[\[(.*?)\]\]', content)
        # Clean aliases [[Name|Text]] -> Name
        clean_links = [link.split('|')[0] for link in links]
        # Remove duplicates
        return list(set(clean_links))