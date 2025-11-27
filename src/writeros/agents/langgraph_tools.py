"""
LangGraph Tools for WriterOS Agents

This module defines tools that agents can call autonomously using @tool decorator.
These tools are bound to agents in the LangGraph workflow for autonomous actions.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from pathlib import Path
from langchain_core.tools import tool
from sqlmodel import Session, select
from writeros.schema import Document, Entity, Fact, Relationship, Vault
from writeros.utils.db import engine
from writeros.rag.retriever import RAGRetriever
from writeros.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# SEARCH TOOLS
# ============================================================================

@tool
async def search_vault(query: str, vault_id: str, limit: int = 5) -> str:
    """
    Search the vault for relevant documents, entities, facts, and events.

    Use this when you need to find specific information in the vault.

    Args:
        query: The search query (e.g., "Elara's motivations", "magic system rules")
        vault_id: UUID of the vault to search
        limit: Maximum number of results per category (default: 5)

    Returns:
        Formatted search results with documents, entities, facts, and events
    """
    logger.info("tool_search_vault_called", query=query, vault_id=vault_id)

    try:
        retriever = RAGRetriever()
        results = await retriever.retrieve(
            query=query,
            vault_id=UUID(vault_id),
            limit=limit
        )

        # Format results
        output_parts = []

        if results.documents:
            output_parts.append(f"### Documents ({len(results.documents)})")
            for doc in results.documents[:limit]:
                content_preview = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                output_parts.append(f"- {doc.title}: {content_preview}")

        if results.entities:
            output_parts.append(f"\n### Entities ({len(results.entities)})")
            for entity in results.entities[:limit]:
                desc = entity.description[:100] + "..." if entity.description and len(entity.description) > 100 else entity.description or ""
                output_parts.append(f"- {entity.name} ({entity.type}): {desc}")

        if results.facts:
            output_parts.append(f"\n### Facts ({len(results.facts)})")
            for fact in results.facts[:limit]:
                output_parts.append(f"- {fact.content}")

        if not output_parts:
            return f"No results found for query: {query}"

        return "\n".join(output_parts)

    except Exception as e:
        logger.error("tool_search_vault_failed", error=str(e))
        return f"Error searching vault: {str(e)}"


@tool
async def get_entity_details(entity_name: str, vault_id: str) -> str:
    """
    Get detailed information about a specific entity (character, location, concept).

    Use this when you need comprehensive info about a known entity.

    Args:
        entity_name: Name of the entity (e.g., "Elara", "Winterfell")
        vault_id: UUID of the vault

    Returns:
        Detailed entity information including relationships and facts
    """
    logger.info("tool_get_entity_details_called", entity_name=entity_name)

    try:
        with Session(engine) as session:
            # Find entity
            entity = session.exec(
                select(Entity).where(
                    Entity.vault_id == UUID(vault_id),
                    Entity.name.ilike(f"%{entity_name}%")
                ).limit(1)
            ).first()

            if not entity:
                return f"Entity not found: {entity_name}"

            # Format output
            output = [
                f"## {entity.name}",
                f"**Type:** {entity.type}",
                f"**Description:** {entity.description or 'No description available'}",
            ]

            # Get relationships
            relationships = session.exec(
                select(Relationship).where(
                    (Relationship.source_id == entity.id) |
                    (Relationship.target_id == entity.id)
                ).limit(10)
            ).all()

            if relationships:
                output.append("\n**Relationships:**")
                for rel in relationships:
                    source = session.get(Entity, rel.source_id)
                    target = session.get(Entity, rel.target_id)
                    if source and target:
                        output.append(f"- {source.name} → {rel.relationship_type.value} → {target.name}")

            return "\n".join(output)

    except Exception as e:
        logger.error("tool_get_entity_details_failed", error=str(e))
        return f"Error getting entity details: {str(e)}"


# ============================================================================
# FILE OPERATIONS
# ============================================================================

@tool
def create_note(title: str, content: str, vault_path: str, folder: str = "") -> str:
    """
    Create a new markdown note in the vault.

    Use this when you need to create documentation, character sheets, or notes.

    Args:
        title: Note title (will be sanitized for filename)
        content: Markdown content of the note
        vault_path: Path to the vault root directory
        folder: Optional subfolder within vault (e.g., "Characters", "Locations")

    Returns:
        Success message with file path or error message
    """
    logger.info("tool_create_note_called", title=title, folder=folder)

    try:
        # Sanitize title for filename
        filename = title.replace("/", "-").replace("\\", "-").replace(":", "-")
        filename = f"{filename}.md"

        # Build path
        vault_root = Path(vault_path)
        if folder:
            target_dir = vault_root / folder
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = vault_root

        file_path = target_dir / filename

        # Check if file exists
        if file_path.exists():
            return f"Error: File already exists: {file_path}"

        # Write file
        file_path.write_text(content, encoding="utf-8")

        logger.info("tool_create_note_success", file_path=str(file_path))
        return f"Note created successfully: {file_path}"

    except Exception as e:
        logger.error("tool_create_note_failed", error=str(e))
        return f"Error creating note: {str(e)}"


@tool
def read_note(file_path: str) -> str:
    """
    Read the contents of a markdown note.

    Use this when you need to check existing note content.

    Args:
        file_path: Full path to the note file

    Returns:
        Note content or error message
    """
    logger.info("tool_read_note_called", file_path=file_path)

    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"

        content = path.read_text(encoding="utf-8")
        return content

    except Exception as e:
        logger.error("tool_read_note_failed", error=str(e))
        return f"Error reading note: {str(e)}"


@tool
def append_to_note(file_path: str, content: str) -> str:
    """
    Append content to an existing markdown note.

    Use this when you need to add to existing notes.

    Args:
        file_path: Full path to the note file
        content: Content to append (will add newlines before)

    Returns:
        Success message or error
    """
    logger.info("tool_append_to_note_called", file_path=file_path)

    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"

        # Read existing content
        existing = path.read_text(encoding="utf-8")

        # Append new content
        updated = existing + "\n\n" + content
        path.write_text(updated, encoding="utf-8")

        logger.info("tool_append_to_note_success", file_path=file_path)
        return f"Content appended to: {file_path}"

    except Exception as e:
        logger.error("tool_append_to_note_failed", error=str(e))
        return f"Error appending to note: {str(e)}"


# ============================================================================
# VAULT METADATA
# ============================================================================

@tool
def list_vault_entities(vault_id: str, entity_type: Optional[str] = None, limit: int = 20) -> str:
    """
    List all entities in the vault, optionally filtered by type.

    Use this to explore what's in the vault.

    Args:
        vault_id: UUID of the vault
        entity_type: Optional filter by type (e.g., "CHARACTER", "LOCATION")
        limit: Maximum number of entities to return (default: 20)

    Returns:
        List of entities with types and descriptions
    """
    logger.info("tool_list_vault_entities_called", vault_id=vault_id, entity_type=entity_type)

    try:
        with Session(engine) as session:
            query = select(Entity).where(Entity.vault_id == UUID(vault_id))

            if entity_type:
                query = query.where(Entity.type == entity_type)

            query = query.limit(limit)
            entities = session.exec(query).all()

            if not entities:
                return "No entities found in vault"

            output = [f"## Entities ({len(entities)})"]
            for entity in entities:
                desc = entity.description[:80] + "..." if entity.description and len(entity.description) > 80 else entity.description or ""
                output.append(f"- **{entity.name}** ({entity.type}): {desc}")

            return "\n".join(output)

    except Exception as e:
        logger.error("tool_list_vault_entities_failed", error=str(e))
        return f"Error listing entities: {str(e)}"


# ============================================================================
# TOOL REGISTRY
# ============================================================================

# All tools available for binding to agents
ALL_TOOLS = [
    search_vault,
    get_entity_details,
    create_note,
    read_note,
    append_to_note,
    list_vault_entities
]

# Tools grouped by category
SEARCH_TOOLS = [search_vault, get_entity_details, list_vault_entities]
FILE_TOOLS = [create_note, read_note, append_to_note]
PRODUCER_TOOLS = ALL_TOOLS  # Producer gets all tools
