"""
Tests for Tool Calling Functionality

Tests the complete function calling workflow:
1. ToolRegistry schemas and handlers
2. OrchestratorAgent tool integration
3. End-to-end tool execution
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

from writeros.agents.tools_registry import ToolRegistry
from writeros.agents.orchestrator import OrchestratorAgent
from writeros.schema import EntityType


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    @pytest.fixture
    def tool_registry(self, tmp_path):
        """Create ToolRegistry with temporary vault."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        # Create Story Bible structure
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)
        (vault_path / "Story_Bible" / "Locations").mkdir(parents=True)
        (vault_path / "Story_Bible" / "Organizations").mkdir(parents=True)

        return ToolRegistry(str(vault_path))

    def test_tool_registry_initialization(self, tool_registry):
        """Test that ToolRegistry initializes correctly."""
        assert tool_registry.vault_path is not None
        assert tool_registry.writer is not None
        assert len(tool_registry.handlers) == 7

    def test_get_tool_schemas(self, tool_registry):
        """Test that tool schemas are in OpenAI format."""
        schemas = tool_registry.get_tool_schemas()

        assert len(schemas) == 7
        assert all(s.get("type") == "function" for s in schemas)
        assert all("function" in s for s in schemas)
        assert all("name" in s["function"] for s in schemas)
        assert all("description" in s["function"] for s in schemas)

        # Verify specific tools exist
        tool_names = [s["function"]["name"] for s in schemas]
        assert "create_character_file" in tool_names
        assert "create_location_file" in tool_names
        assert "search_vault" in tool_names

    def test_execute_unknown_tool(self, tool_registry):
        """Test that executing an unknown tool returns error."""
        result = tool_registry.execute_tool("unknown_tool", {})

        assert result["success"] is False
        assert "Unknown tool" in result["message"]
        assert result["error"] == "UNKNOWN_TOOL"


class TestCreateCharacterTool:
    """Tests for create_character_file tool."""

    @pytest.fixture
    def tool_registry(self, tmp_path):
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)
        return ToolRegistry(str(vault_path))

    def test_create_character_success(self, tool_registry):
        """Test creating a new character file."""
        result = tool_registry.execute_tool("create_character_file", {
            "name": "Jon Snow",
            "description": "The bastard son of Eddard Stark",
            "role": "protagonist",
            "traits": ["honorable", "brave", "brooding"],
            "backstory": "Raised at Winterfell as Ned Stark's bastard son."
        })

        assert result["success"] is True
        assert "Created character file" in result["message"]
        assert "file_path" in result

        # Verify file was created
        file_path = Path(result["file_path"])
        assert file_path.exists()

        # Verify content
        content = file_path.read_text(encoding='utf-8')
        assert "# Jon Snow" in content
        assert "protagonist" in content
        assert "honorable" in content

    def test_create_character_duplicate(self, tool_registry):
        """Test that creating duplicate character returns error."""
        # Create first time
        tool_registry.execute_tool("create_character_file", {
            "name": "Arya Stark",
            "description": "A young noble girl"
        })

        # Try to create again
        result = tool_registry.execute_tool("create_character_file", {
            "name": "Arya Stark",
            "description": "A young noble girl"
        })

        assert result["success"] is False
        assert "already exists" in result["message"]

    def test_create_character_minimal_args(self, tool_registry):
        """Test creating character with only required arguments."""
        result = tool_registry.execute_tool("create_character_file", {
            "name": "Minimal Character",
            "description": "A character with minimal info"
        })

        assert result["success"] is True
        file_path = Path(result["file_path"])
        assert file_path.exists()


class TestCreateLocationTool:
    """Tests for create_location_file tool."""

    @pytest.fixture
    def tool_registry(self, tmp_path):
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Locations").mkdir(parents=True)
        return ToolRegistry(str(vault_path))

    def test_create_location_success(self, tool_registry):
        """Test creating a new location file."""
        result = tool_registry.execute_tool("create_location_file", {
            "name": "Winterfell",
            "description": "The ancestral home of House Stark",
            "type": "castle",
            "geography": "Located in the North, surrounded by walls",
            "history": "Built thousands of years ago"
        })

        assert result["success"] is True
        assert "Created location file" in result["message"]

        file_path = Path(result["file_path"])
        assert file_path.exists()

        content = file_path.read_text(encoding='utf-8')
        assert "# Winterfell" in content
        assert "castle" in content
        assert "Geography" in content


class TestUpdateCharacterTool:
    """Tests for update_character tool."""

    @pytest.fixture
    def tool_registry(self, tmp_path):
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)

        # Create initial character
        registry = ToolRegistry(str(vault_path))
        registry.execute_tool("create_character_file", {
            "name": "Test Character",
            "description": "A test character"
        })

        return registry

    def test_update_character_success(self, tool_registry):
        """Test updating an existing character."""
        result = tool_registry.execute_tool("update_character", {
            "name": "Test Character",
            "field": "traits",
            "content": "- New trait 1\n- New trait 2"
        })

        assert result["success"] is True
        assert "Updated" in result["message"]

        file_path = Path(result["file_path"])
        content = file_path.read_text(encoding='utf-8')
        assert "New trait 1" in content

    def test_update_nonexistent_character(self, tool_registry):
        """Test updating a character that doesn't exist."""
        result = tool_registry.execute_tool("update_character", {
            "name": "Nonexistent Character",
            "field": "traits",
            "content": "New content"
        })

        assert result["success"] is False
        assert "not found" in result["message"]


class TestSearchVaultTool:
    """Tests for search_vault tool."""

    @pytest.fixture
    def tool_registry(self, tmp_path):
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)
        (vault_path / "Story_Bible" / "Locations").mkdir(parents=True)

        registry = ToolRegistry(str(vault_path))

        # Create sample files
        registry.execute_tool("create_character_file", {
            "name": "Jon Snow",
            "description": "Test"
        })
        registry.execute_tool("create_character_file", {
            "name": "Arya Stark",
            "description": "Test"
        })
        registry.execute_tool("create_location_file", {
            "name": "Winterfell",
            "description": "Test"
        })

        return registry

    def test_search_vault_finds_matches(self, tool_registry):
        """Test searching for existing files."""
        result = tool_registry.execute_tool("search_vault", {
            "query": "Jon",
            "type": "all"
        })

        assert result["success"] is True
        assert len(result["results"]) == 1
        # File name is sanitized (spaces become underscores)
        assert "Jon" in result["results"][0]["name"]

    def test_search_vault_multiple_results(self, tool_registry):
        """Test search returns multiple results."""
        result = tool_registry.execute_tool("search_vault", {
            "query": "Stark",
            "type": "character"
        })

        assert result["success"] is True
        assert len(result["results"]) == 1
        assert "Stark" in result["results"][0]["name"]

    def test_search_vault_no_results(self, tool_registry):
        """Test search with no matches."""
        result = tool_registry.execute_tool("search_vault", {
            "query": "Nonexistent",
            "type": "all"
        })

        assert result["success"] is True
        assert len(result["results"]) == 0


class TestCreateRelationshipTool:
    """Tests for create_relationship tool."""

    @pytest.fixture
    def tool_registry(self, tmp_path):
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)
        return ToolRegistry(str(vault_path))

    def test_create_relationship(self, tool_registry, mocker):
        """Test creating a relationship between entities."""
        # Mock the _sync_relationship method
        mock_sync = mocker.patch.object(tool_registry.writer, '_sync_relationship')

        result = tool_registry.execute_tool("create_relationship", {
            "source": "Jon Snow",
            "target": "Arya Stark",
            "relationship_type": "sibling",
            "description": "They are siblings"
        })

        assert result["success"] is True
        assert "sibling" in result["message"]
        mock_sync.assert_called_once()


class TestOrchestratorToolIntegration:
    """Tests for OrchestratorAgent tool integration."""

    @pytest.fixture
    def orchestrator(self, tmp_path, mocker):
        """Create OrchestratorAgent with mocked dependencies."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)

        # Mock environment
        mocker.patch.dict('os.environ', {"VAULT_PATH": str(vault_path)})

        # Mock embedding service
        mocker.patch('writeros.agents.orchestrator.get_embedding_service')

        # Create orchestrator
        orchestrator = OrchestratorAgent()

        return orchestrator

    def test_orchestrator_has_tools(self, orchestrator):
        """Test that orchestrator initializes with tools."""
        assert orchestrator.tools is not None
        assert isinstance(orchestrator.tools, ToolRegistry)

    def test_orchestrator_get_tool_schemas(self, orchestrator):
        """Test that orchestrator can access tool schemas."""
        schemas = orchestrator.tools.get_tool_schemas()
        assert len(schemas) > 0

    @pytest.mark.asyncio
    async def test_execute_tool_call(self, orchestrator, tmp_path):
        """Test tool execution through orchestrator."""
        tool_call = {
            "name": "create_character_file",
            "arguments": {
                "name": "Test Hero",
                "description": "A brave hero"
            }
        }

        result = await orchestrator._execute_tool_call(tool_call)

        assert result["success"] is True
        assert "Created character file" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_tool_with_invalid_args(self, orchestrator):
        """Test tool execution with invalid JSON arguments."""
        tool_call = {
            "name": "create_character_file",
            "arguments": "invalid json"
        }

        result = await orchestrator._execute_tool_call(tool_call)

        assert result["success"] is False
        assert "Invalid JSON" in result["message"]


class TestEndToEndToolCalling:
    """End-to-end integration tests for tool calling."""

    @pytest.fixture
    def setup_environment(self, tmp_path, mocker):
        """Set up complete environment for E2E testing."""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)
        (vault_path / "Story_Bible" / "Locations").mkdir(parents=True)

        mocker.patch.dict('os.environ', {"VAULT_PATH": str(vault_path)})

        return vault_path

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_workflow_create_character(
        self,
        setup_environment,
        mocker,
        db_session,
        sample_vault_id
    ):
        """Test complete workflow of creating a character via tool calling."""
        # Mock embedding service
        mock_embedder = mocker.patch('writeros.agents.orchestrator.get_embedding_service')
        mock_embedder.return_value.embed_query.return_value = [0.1] * 1536

        # Mock LLM to return a tool call
        mock_llm = mocker.patch('writeros.utils.llm_client.LLMClient')
        mock_instance = mock_llm.return_value

        async def mock_stream(*args, **kwargs):
            # The client expects a chunk with tool_calls
            # We need to mock the structure that the LLMClient expects
            
            # 1. Chunk with tool call
            yield MagicMock(
                choices=[MagicMock(delta=MagicMock(tool_calls=[
                    MagicMock(
                        id="call_123",
                        function=MagicMock(
                            name="create_character_file",
                            arguments='{"name": "Gandalf", "description": "A wise wizard", "role": "supporting"}'
                        )
                    )
                ]))]
            )
            
            # 2. Chunk with content (after tool execution)
            # In a real flow, this would be a separate call, but here we are mocking stream_chat
            # which yields content. 
            # Wait, LLMClient.stream_chat yields strings or dicts (for tools).
            # The error comes from the *internal* call to OpenAI client.
            # We are mocking LLMClient, so we should yield what LLMClient yields.
            
            yield {
                "type": "tool_call",
                "id": "call_123",
                "name": "create_character_file",
                "arguments": {
                    "name": "Gandalf",
                    "description": "A wise wizard",
                    "role": "supporting"
                }
            }
            yield "I've created the character file for Gandalf."

        # We need to patch the LLMClient instance on the orchestrator, not just the class
        # But Orchestrator instantiates LLMClient in __init__.
        # So we need to patch LLMClient class *before* Orchestrator is initialized.
        # The test does `mock_llm = mocker.patch('writeros.utils.llm_client.LLMClient')`
        # This mocks the class. `mock_instance = mock_llm.return_value` is the instance.
        # `mock_instance.stream_chat = mock_stream` sets the method.
        
        # The error `openai.BadRequestError` suggests that the REAL OpenAI client is being used somewhere
        # or the mock is not taking effect.
        # Ah, `OrchestratorAgent` inherits from `BaseAgent`. `BaseAgent` imports `LLMClient` from `writeros.utils.llm_client`.
        # The test patches `writeros.utils.llm_client.LLMClient`.
        # This should work IF `BaseAgent` imports `LLMClient` at module level.
        # Let's check `writeros/agents/base.py`.
        
        # If the error persists, it means `stream_chat` is NOT mocked and it's calling the real `ainvoke` -> `client.astream`.
        # And since we didn't set an API key or the messages are wrong, it fails.
        # Wait, the error is "Invalid parameter: messages with role 'tool' must be a response..."
        # This validation happens on the OpenAI server side (or library side).
        # This confirms the REAL client is being called.
        
        # WHY is the real client being called if we patched `LLMClient`?
        # Maybe `OrchestratorAgent` imports `LLMClient` differently?
        # Or `BaseAgent` does?
        
        # I will enforce the mock on the instance AFTER initialization to be sure.
        orchestrator = OrchestratorAgent()
        orchestrator.llm = mock_instance

        # Mock database queries
        mocker.patch.object(orchestrator, '_create_conversation', return_value=uuid4())
        mocker.patch.object(orchestrator, '_save_message')
        mocker.patch.object(orchestrator, '_retrieve_context', return_value={
            "documents": [],
            "entities": []
        })

        # Execute chat
        full_response = ""
        async for chunk in orchestrator.process_chat(
            "Create a character file for Gandalf, a wise wizard",
            sample_vault_id
        ):
            full_response += chunk

        # Verify character file was created
        char_file = setup_environment / "Story_Bible" / "Characters" / "Gandalf.md"
        assert char_file.exists()

        content = char_file.read_text(encoding='utf-8')
        assert "Gandalf" in content
        assert "wizard" in content


class TestToolSafety:
    """Tests for tool safety mechanisms."""

    @pytest.fixture
    def tool_registry(self, tmp_path):
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()
        (vault_path / "Story_Bible" / "Characters").mkdir(parents=True)
        return ToolRegistry(str(vault_path))

    def test_prevents_duplicate_creation(self, tool_registry):
        """Test that tools prevent duplicate file creation."""
        # Create character
        tool_registry.execute_tool("create_character_file", {
            "name": "Duplicate Test",
            "description": "Test character"
        })

        # Try to create again
        result = tool_registry.execute_tool("create_character_file", {
            "name": "Duplicate Test",
            "description": "Test character"
        })

        assert result["success"] is False
        assert "already exists" in result["message"]

    def test_update_requires_existing_file(self, tool_registry):
        """Test that update_character requires existing file."""
        result = tool_registry.execute_tool("update_character", {
            "name": "Nonexistent",
            "field": "traits",
            "content": "New content"
        })

        assert result["success"] is False
        assert "not found" in result["message"]

    def test_search_before_create_workflow(self, tool_registry):
        """Test recommended workflow: search before creating."""
        # Search first (should find nothing)
        search_result = tool_registry.execute_tool("search_vault", {
            "query": "New Character",
            "type": "character"
        })

        assert len(search_result["results"]) == 0

        # Create character
        create_result = tool_registry.execute_tool("create_character_file", {
            "name": "New Character",
            "description": "A brand new character"
        })

        assert create_result["success"] is True

        # Search again (should find it)
        search_result = tool_registry.execute_tool("search_vault", {
            "query": "New Character",
            "type": "character"
        })

        assert len(search_result["results"]) == 1
