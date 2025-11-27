"""
Tool Registry for WriterOS Function Calling.

Defines the tools (functions) that the AI can call to take actions in the vault.
Uses OpenAI Function Calling format.
"""
from typing import Dict, List, Any, Callable
from pathlib import Path
from uuid import UUID
import os

from writeros.utils.writer import ObsidianWriter
from writeros.core.logging import get_logger
from writeros.schema import EntityType

logger = get_logger(__name__)


class ToolRegistry:
    """
    Manages available tools for function calling.

    Each tool has:
    - Schema: OpenAI function calling format
    - Handler: Python function that executes the action
    """

    def __init__(self, vault_path: str):
        """
        Initialize the tool registry.

        Args:
            vault_path: Path to the Obsidian vault
        """
        self.vault_path = vault_path
        self.writer = ObsidianWriter(Path(vault_path))

        # Map tool names to handler functions
        self.handlers: Dict[str, Callable] = {
            "create_character_file": self._create_character_file,
            "create_location_file": self._create_location_file,
            "create_organization_file": self._create_organization_file,
            "update_character": self._update_character,
            "create_relationship": self._create_relationship,
            "create_scene_file": self._create_scene_file,
            "search_vault": self._search_vault,
        }

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get OpenAI function calling schemas for all available tools.

        Returns:
            List of tool schemas in OpenAI format
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_character_file",
                    "description": "Create a new character file in the Story Bible. Use this when the user asks to create a character profile or document a new character.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The character's name (e.g., 'Jon Snow', 'Aria Winters')"
                            },
                            "role": {
                                "type": "string",
                                "description": "Character's role in the story",
                                "enum": ["protagonist", "antagonist", "supporting", "minor"]
                            },
                            "description": {
                                "type": "string",
                                "description": "A detailed description of the character's appearance, personality, and background"
                            },
                            "traits": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of character traits (e.g., ['brave', 'loyal', 'impulsive'])"
                            },
                            "backstory": {
                                "type": "string",
                                "description": "Character's backstory and history"
                            }
                        },
                        "required": ["name", "description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_location_file",
                    "description": "Create a new location file in the Story Bible. Use this when documenting a new place in the story world.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The location's name (e.g., 'Winterfell', 'The Kingdom')"
                            },
                            "type": {
                                "type": "string",
                                "description": "Type of location",
                                "enum": ["city", "building", "region", "natural", "other"]
                            },
                            "description": {
                                "type": "string",
                                "description": "Detailed description of the location's appearance, atmosphere, and significance"
                            },
                            "geography": {
                                "type": "string",
                                "description": "Geographic details (climate, terrain, etc.)"
                            },
                            "history": {
                                "type": "string",
                                "description": "Historical background of the location"
                            }
                        },
                        "required": ["name", "description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_organization_file",
                    "description": "Create a new organization/faction file. Use this for guilds, kingdoms, companies, or any organized groups.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The organization's name"
                            },
                            "type": {
                                "type": "string",
                                "description": "Type of organization",
                                "enum": ["guild", "kingdom", "faction", "company", "religion", "military"]
                            },
                            "description": {
                                "type": "string",
                                "description": "Description of the organization's purpose and structure"
                            },
                            "leader": {
                                "type": "string",
                                "description": "Name of the organization's leader"
                            },
                            "goals": {
                                "type": "string",
                                "description": "The organization's goals and motivations"
                            }
                        },
                        "required": ["name", "description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_character",
                    "description": "Update an existing character file with new information. Use this to add details to a character that already exists.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The character's name (must match existing file)"
                            },
                            "field": {
                                "type": "string",
                                "description": "Which field to update",
                                "enum": ["description", "traits", "backstory", "relationships"]
                            },
                            "content": {
                                "type": "string",
                                "description": "The new content to add or update"
                            }
                        },
                        "required": ["name", "field", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_relationship",
                    "description": "Document a relationship between two characters or entities. Use this when the user mentions connections between characters.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Name of the first character/entity"
                            },
                            "target": {
                                "type": "string",
                                "description": "Name of the second character/entity"
                            },
                            "relationship_type": {
                                "type": "string",
                                "description": "Type of relationship",
                                "enum": ["family", "ally", "enemy", "romantic", "mentor", "friend"]
                            },
                            "description": {
                                "type": "string",
                                "description": "Details about the relationship"
                            }
                        },
                        "required": ["source", "target", "relationship_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_scene_file",
                    "description": "Create a new scene or chapter file in the Manuscripts folder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title of the scene or chapter"
                            },
                            "content": {
                                "type": "string",
                                "description": "The actual scene content (narrative text)"
                            },
                            "chapter_number": {
                                "type": "integer",
                                "description": "Chapter number (if applicable)"
                            }
                        },
                        "required": ["title", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_vault",
                    "description": "Search for existing files in the vault. Use this before creating new files to avoid duplicates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search term (character name, location name, etc.)"
                            },
                            "type": {
                                "type": "string",
                                "description": "Type of content to search for",
                                "enum": ["character", "location", "organization", "scene", "all"]
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given arguments.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments as dict

        Returns:
            Result dict with 'success', 'message', and optional 'file_path'
        """
        if tool_name not in self.handlers:
            return {
                "success": False,
                "message": f"Unknown tool: {tool_name}",
                "error": "UNKNOWN_TOOL"
            }

        try:
            handler = self.handlers[tool_name]
            result = handler(**arguments)

            logger.info(
                "tool_executed",
                tool=tool_name,
                arguments=arguments,
                success=result.get("success", False)
            )

            return result

        except Exception as e:
            logger.error(
                "tool_execution_failed",
                tool=tool_name,
                arguments=arguments,
                error=str(e)
            )

            return {
                "success": False,
                "message": f"Tool execution failed: {str(e)}",
                "error": "EXECUTION_ERROR"
            }

    # ========================================
    # TOOL HANDLERS (Implementation)
    # ========================================

    def _create_character_file(
        self,
        name: str,
        description: str,
        role: str = "supporting",
        traits: List[str] = None,
        backstory: str = None
    ) -> Dict[str, Any]:
        """Create a character file in Story_Bible/Characters/."""
        try:
            file_path = self.writer.dirs["chars"] / f"{self.writer._sanitize(name)}.md"

            # Check if file already exists
            if file_path.exists():
                return {
                    "success": False,
                    "message": f"Character file for '{name}' already exists. Use update_character to modify it.",
                    "file_path": str(file_path)
                }

            # Build frontmatter
            frontmatter = f"""---
type: character
name: {name}
role: {role}
tags: [character]
---

# {name}

## Overview
{description}

## Traits
"""
            if traits:
                for trait in traits:
                    frontmatter += f"- {trait}\n"
            else:
                frontmatter += "- (Add traits here)\n"

            if backstory:
                frontmatter += f"\n## Backstory\n{backstory}\n"

            frontmatter += "\n## Relationships\n(Add relationships here)\n"

            # Write file
            file_path.write_text(frontmatter, encoding='utf-8')

            # Sync to database
            self.writer._sync_entity(
                name=name,
                type_=EntityType.CHARACTER,
                desc=description,
                props={"role": role, "traits": traits or []}
            )

            return {
                "success": True,
                "message": f"Created character file for '{name}'",
                "file_path": str(file_path)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create character file: {str(e)}"
            }

    def _create_location_file(
        self,
        name: str,
        description: str,
        type: str = "other",
        geography: str = None,
        history: str = None
    ) -> Dict[str, Any]:
        """Create a location file in Story_Bible/Locations/."""
        try:
            file_path = self.writer.dirs["locs"] / f"{self.writer._sanitize(name)}.md"

            if file_path.exists():
                return {
                    "success": False,
                    "message": f"Location file for '{name}' already exists.",
                    "file_path": str(file_path)
                }

            content = f"""---
type: location
name: {name}
location_type: {type}
tags: [location]
---

# {name}

## Description
{description}
"""
            if geography:
                content += f"\n## Geography\n{geography}\n"

            if history:
                content += f"\n## History\n{history}\n"

            file_path.write_text(content, encoding='utf-8')

            # Sync to database
            self.writer._sync_entity(
                name=name,
                type_=EntityType.LOCATION,
                desc=description,
                props={"location_type": type}
            )

            return {
                "success": True,
                "message": f"Created location file for '{name}'",
                "file_path": str(file_path)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create location file: {str(e)}"
            }

    def _create_organization_file(
        self,
        name: str,
        description: str,
        type: str = "faction",
        leader: str = None,
        goals: str = None
    ) -> Dict[str, Any]:
        """Create an organization file in Story_Bible/Organizations/."""
        try:
            file_path = self.writer.dirs["orgs"] / f"{self.writer._sanitize(name)}.md"

            if file_path.exists():
                return {
                    "success": False,
                    "message": f"Organization file for '{name}' already exists.",
                    "file_path": str(file_path)
                }

            content = f"""---
type: organization
name: {name}
org_type: {type}
tags: [organization, {type}]
---

# {name}

## Overview
{description}
"""
            if leader:
                content += f"\n## Leadership\n**Leader**: {leader}\n"

            if goals:
                content += f"\n## Goals & Motivations\n{goals}\n"

            file_path.write_text(content, encoding='utf-8')

            # Sync to database
            self.writer._sync_entity(
                name=name,
                type_=EntityType.FACTION,
                desc=description,
                props={"org_type": type, "leader": leader}
            )

            return {
                "success": True,
                "message": f"Created organization file for '{name}'",
                "file_path": str(file_path)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create organization file: {str(e)}"
            }

    def _update_character(
        self,
        name: str,
        field: str,
        content: str
    ) -> Dict[str, Any]:
        """Update an existing character file."""
        try:
            file_path = self.writer.dirs["chars"] / f"{self.writer._sanitize(name)}.md"

            if not file_path.exists():
                return {
                    "success": False,
                    "message": f"Character file for '{name}' not found. Create it first."
                }

            # Read existing content
            existing_content = file_path.read_text(encoding='utf-8')

            # Simple append strategy (more sophisticated merging could be added)
            section_map = {
                "description": "## Overview",
                "traits": "## Traits",
                "backstory": "## Backstory",
                "relationships": "## Relationships"
            }

            section_header = section_map.get(field, f"## {field.title()}")

            if section_header in existing_content:
                # Append to existing section
                updated_content = existing_content.replace(
                    section_header,
                    f"{section_header}\n{content}\n"
                )
            else:
                # Add new section
                updated_content = existing_content + f"\n\n{section_header}\n{content}\n"

            file_path.write_text(updated_content, encoding='utf-8')

            return {
                "success": True,
                "message": f"Updated {field} for '{name}'",
                "file_path": str(file_path)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to update character: {str(e)}"
            }

    def _create_relationship(
        self,
        source: str,
        target: str,
        relationship_type: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """Document a relationship between entities."""
        try:
            # Sync to database
            self.writer._sync_relationship(
                source_name=source,
                target_name=target,
                rel_type=relationship_type,
                details=description
            )

            return {
                "success": True,
                "message": f"Created {relationship_type} relationship: {source} -> {target}"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create relationship: {str(e)}"
            }

    def _create_scene_file(
        self,
        title: str,
        content: str,
        chapter_number: int = None
    ) -> Dict[str, Any]:
        """Create a scene/chapter file in Manuscripts/."""
        try:
            manuscripts_dir = self.writer.vault_path / "Manuscripts"
            manuscripts_dir.mkdir(exist_ok=True)

            if chapter_number:
                filename = f"Chapter_{chapter_number:02d}_{self.writer._sanitize(title)}.md"
            else:
                filename = f"{self.writer._sanitize(title)}.md"

            file_path = manuscripts_dir / filename

            if file_path.exists():
                return {
                    "success": False,
                    "message": f"Scene file already exists: {filename}",
                    "file_path": str(file_path)
                }

            scene_content = f"""# {title}

{content}
"""
            file_path.write_text(scene_content, encoding='utf-8')

            return {
                "success": True,
                "message": f"Created scene file: {filename}",
                "file_path": str(file_path)
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create scene file: {str(e)}"
            }

    def _search_vault(
        self,
        query: str,
        type: str = "all"
    ) -> Dict[str, Any]:
        """Search for existing files in the vault."""
        try:
            results = []
            search_dirs = []

            if type in ["character", "all"]:
                search_dirs.append(("character", self.writer.dirs["chars"]))
            if type in ["location", "all"]:
                search_dirs.append(("location", self.writer.dirs["locs"]))
            if type in ["organization", "all"]:
                search_dirs.append(("organization", self.writer.dirs["orgs"]))

            for entity_type, dir_path in search_dirs:
                if dir_path.exists():
                    for file_path in dir_path.glob("*.md"):
                        name = file_path.stem
                        if query.lower() in name.lower():
                            results.append({
                                "type": entity_type,
                                "name": name,
                                "path": str(file_path)
                            })

            return {
                "success": True,
                "message": f"Found {len(results)} results for '{query}'",
                "results": results
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Search failed: {str(e)}",
                "results": []
            }
