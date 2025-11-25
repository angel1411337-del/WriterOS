# Tool Calling Implementation - WriterOS v2.5

## Overview

**Implemented**: 2025-11-25
**Status**: ✅ **COMPLETE**

This document describes the implementation of OpenAI Function Calling (Tool Calling) in WriterOS v2.5, which enables the AI to physically create and edit Markdown files in the vault instead of just talking about actions.

## Problem Solved

**Before**: When a user said "Make a file for Jon Snow," the AI would only respond with text describing what should be done, but wouldn't actually create the file.

**After**: The AI can now execute real actions:
- Create character files in `Story_Bible/Characters/`
- Create location files in `Story_Bible/Locations/`
- Create organization files in `Story_Bible/Organizations/`
- Update existing character files
- Document relationships between entities
- Create scene/chapter files
- Search for existing files to avoid duplicates

## Architecture

### Components Created

1. **LLMClient** (`src/writeros/utils/llm_client.py`)
   - Wrapper around LangChain's ChatOpenAI
   - Supports streaming with function calling
   - Detects and parses tool calls from LLM responses
   - Converts between OpenAI and LangChain tool formats

2. **ToolRegistry** (`src/writeros/agents/tools_registry.py`)
   - Manages 7 available tools
   - Defines OpenAI function schemas
   - Implements tool handlers
   - Provides safety checks (duplicate prevention, file existence validation)

3. **Updated OrchestratorAgent** (`src/writeros/agents/orchestrator.py`)
   - Integrates ToolRegistry
   - Executes tool calls during chat
   - Provides feedback to user about tool execution
   - Continues conversation with tool results

4. **Updated BaseAgent** (`src/writeros/agents/base.py`)
   - Uses LLMClient instead of raw ChatOpenAI
   - Provides access to `with_structured_output` for backward compatibility

## Available Tools

### 1. create_character_file
Creates a new character file with frontmatter.

**Schema**:
```json
{
  "name": "create_character_file",
  "parameters": {
    "name": "string (required)",
    "description": "string (required)",
    "role": "enum: protagonist|antagonist|supporting|minor",
    "traits": ["array of strings"],
    "backstory": "string"
  }
}
```

**Output**: Markdown file in `Story_Bible/Characters/Name.md` with YAML frontmatter

**Safety**: Returns error if file already exists

### 2. create_location_file
Creates a new location file.

**Schema**:
```json
{
  "name": "create_location_file",
  "parameters": {
    "name": "string (required)",
    "description": "string (required)",
    "type": "string (e.g., 'castle', 'city')",
    "geography": "string",
    "history": "string"
  }
}
```

**Output**: Markdown file in `Story_Bible/Locations/Name.md`

### 3. create_organization_file
Creates a new organization/faction file.

**Schema**:
```json
{
  "name": "create_organization_file",
  "parameters": {
    "name": "string (required)",
    "description": "string (required)",
    "type": "string (default: 'faction')",
    "leader": "string",
    "goals": "string"
  }
}
```

**Output**: Markdown file in `Story_Bible/Organizations/Name.md`

### 4. update_character
Updates an existing character file by appending content to a section.

**Schema**:
```json
{
  "name": "update_character",
  "parameters": {
    "name": "string (required)",
    "field": "enum: description|traits|backstory|relationships",
    "content": "string (required)"
  }
}
```

**Safety**: Returns error if character file doesn't exist

### 5. create_relationship
Documents a relationship between entities in the database.

**Schema**:
```json
{
  "name": "create_relationship",
  "parameters": {
    "source": "string (required)",
    "target": "string (required)",
    "relationship_type": "string (required, e.g., 'sibling', 'enemy')",
    "description": "string"
  }
}
```

**Output**: Syncs to database via `ObsidianWriter._sync_relationship()`

### 6. create_scene_file
Creates a scene or chapter file in the manuscript.

**Schema**:
```json
{
  "name": "create_scene_file",
  "parameters": {
    "title": "string (required)",
    "content": "string (required)",
    "chapter_number": "integer (optional)"
  }
}
```

**Output**: Markdown file in `Manuscripts/` with optional chapter numbering

### 7. search_vault
Searches for existing files to avoid duplicates.

**Schema**:
```json
{
  "name": "search_vault",
  "parameters": {
    "query": "string (required)",
    "type": "enum: all|character|location|organization"
  }
}
```

**Output**: List of matching files with paths

## How It Works

### 1. User Request Flow

```
User: "Create a character file for Jon Snow, a brave warrior"
  |
  v
OrchestratorAgent.process_chat()
  |
  v
LLMClient.stream_chat(messages, tools=tool_schemas)
  |
  v
LLM decides to call create_character_file
  |
  v
OrchestratorAgent._execute_tool_call()
  |
  v
ToolRegistry.execute_tool("create_character_file", {...})
  |
  v
File created: Story_Bible/Characters/Jon_Snow.md
  |
  v
Tool result returned to LLM
  |
  v
LLM: "I've created the character file for Jon Snow at Story_Bible/Characters/Jon_Snow.md"
```

### 2. Tool Execution Workflow

```python
# 1. LLM returns tool call
{
    "type": "tool_call",
    "id": "call_abc123",
    "name": "create_character_file",
    "arguments": {
        "name": "Jon Snow",
        "description": "A brave warrior from the North",
        "role": "protagonist"
    }
}

# 2. Orchestrator executes tool
result = await orchestrator._execute_tool_call(tool_call)
# result = {"success": True, "message": "Created character file...", "file_path": "..."}

# 3. User sees feedback
yield f"\n[Tool: create_character_file] {result['message']}\n"

# 4. Tool result added to conversation context
messages.append({
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": json.dumps(result)
})

# 5. LLM continues with tool result
async for chunk in llm.stream_chat(messages, tools):
    yield chunk
```

## Safety Mechanisms

### 1. Duplicate Prevention
All `create_*` tools check if a file already exists:
```python
if file_path.exists():
    return {
        "success": False,
        "message": f"Character file for '{name}' already exists"
    }
```

### 2. File Existence Validation
`update_character` requires the file to exist:
```python
if not file_path.exists():
    return {
        "success": False,
        "message": f"Character file for '{name}' not found"
    }
```

### 3. Search Before Create
System prompt instructs LLM to:
- Always search for existing files before creating new ones
- Use `search_vault` tool to check for duplicates

### 4. Error Handling
All tools wrapped in try/except:
```python
try:
    # Tool logic
    return {"success": True, "message": "..."}
except Exception as e:
    return {"success": False, "message": f"Failed: {str(e)}"}
```

## System Prompt Integration

The OrchestratorAgent's system prompt includes:

```
TOOL CAPABILITIES:
You have access to tools that allow you to CREATE and EDIT files in the user's vault.

When the user asks you to:
- "Create a character file for X"
- "Make a location file for Y"
- "Update character Z with new traits"
- "Document the relationship between A and B"

You should USE THE AVAILABLE TOOLS to actually perform these actions instead of just describing what should be done.

IMPORTANT:
- Always search for existing files before creating new ones (use search_vault tool)
- When creating files, use descriptive names and comprehensive content
- After creating/updating a file, confirm the action to the user
- If unsure about a destructive operation, ask the user for confirmation first
```

## Testing

**Test Suite**: `tests/agents/test_tool_calling.py`
**Tests**: 21 total, 16 passing (5 integration tests skipped in unit mode)

### Test Categories

1. **ToolRegistry Tests** (3 tests)
   - Registry initialization
   - Schema format validation
   - Unknown tool handling

2. **Create Character Tool Tests** (3 tests)
   - Successful creation
   - Duplicate prevention
   - Minimal arguments

3. **Create Location Tool Tests** (1 test)
   - Successful creation with all fields

4. **Update Character Tool Tests** (2 tests)
   - Successful update
   - Nonexistent file error

5. **Search Vault Tool Tests** (3 tests)
   - Find matches
   - Multiple results
   - No results

6. **Create Relationship Tool Tests** (1 test)
   - Database sync

7. **Orchestrator Integration Tests** (4 tests - require mocking)
   - Tool initialization
   - Schema access
   - Tool execution
   - Invalid arguments handling

8. **End-to-End Tests** (1 test - integration)
   - Complete workflow from chat to file creation

9. **Safety Tests** (3 tests)
   - Duplicate prevention
   - Update requirements
   - Search-before-create workflow

### Running Tests

```bash
# All tool tests (unit mode - fast)
pytest tests/agents/test_tool_calling.py -v -k "not Orchestrator and not EndToEnd"

# With coverage
pytest tests/agents/test_tool_calling.py --cov=src/writeros/agents/tools_registry --cov-report=html
```

**Current Results**: 16/16 unit tests passing ✅

## File Structure

```
src/writeros/
├── utils/
│   └── llm_client.py                 # NEW - LLM wrapper with function calling
├── agents/
│   ├── base.py                       # UPDATED - Uses LLMClient
│   ├── tools_registry.py             # NEW - Tool definitions and handlers
│   └── orchestrator.py               # UPDATED - Tool integration
tests/
└── agents/
    └── test_tool_calling.py          # NEW - Comprehensive test suite
```

## Usage Example

### User Interaction

```
User: Create a character file for Gandalf, a wise wizard

[Tool: create_character_file] Created character file for 'Gandalf'