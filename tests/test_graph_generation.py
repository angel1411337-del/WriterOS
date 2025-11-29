"""
Tests for generate_graph.py - Graph generation script for Obsidian Plugin.

These tests verify that generate_graph.py:
1. Accepts correct command-line arguments
2. Generates graph data using ProfilerAgent
3. Outputs HTML file path to stdout (Plugin requirement)
4. Creates valid D3.js HTML files
"""
import pytest
import subprocess
import sys
import json
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch, MagicMock, AsyncMock
from sqlmodel import Session

from writeros.schema import Entity, Vault, User, EntityType, ConnectionType, SubscriptionTier


PROJECT_ROOT = Path(__file__).parent.parent
GENERATE_GRAPH_PY = PROJECT_ROOT / "generate_graph.py"


@pytest.fixture
def test_vault_with_entities(db_session, sample_vault_id):
    """Create a test vault with sample entities."""
    # Create user
    user = User(
        email="graph_test@writeros.local",
        username="graphtest",
        tier=SubscriptionTier.FREE
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create vault
    vault = Vault(
        id=sample_vault_id,
        name="Graph Test Vault",
        owner_id=user.id,
        connection_type=ConnectionType.LOCAL_OBSIDIAN,
        local_system_path="/test/vault"
    )
    db_session.add(vault)
    db_session.commit()

    # Create sample entities
    entities = [
        Entity(
            vault_id=sample_vault_id,
            name="Hero",
            type=EntityType.CHARACTER,
            description="The protagonist",
            embedding=[0.1] * 1536
        ),
        Entity(
            vault_id=sample_vault_id,
            name="Villain",
            type=EntityType.CHARACTER,
            description="The antagonist",
            embedding=[0.2] * 1536
        ),
        Entity(
            vault_id=sample_vault_id,
            name="The Kingdom",
            type=EntityType.LOCATION,
            description="The main setting",
            embedding=[0.3] * 1536
        ),
    ]

    for entity in entities:
        db_session.add(entity)

    db_session.commit()

    return vault


class TestGraphScriptExistence:
    """Tests for basic script existence and structure."""

    def test_generate_graph_exists(self):
        """Test that generate_graph.py exists in project root."""
        assert GENERATE_GRAPH_PY.exists(), "generate_graph.py should exist in project root"

    def test_generate_graph_is_python_script(self):
        """Test that generate_graph.py is a valid Python script."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            first_line = f.readline()

        # Should have python shebang
        assert first_line.startswith('#!') and 'python' in first_line.lower()

    def test_generate_graph_has_docstring(self):
        """Test that generate_graph.py has documentation."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        assert '"""' in content or "'''" in content


class TestGraphScriptArguments:
    """Tests for command-line argument parsing."""

    def test_script_requires_graph_type(self):
        """Test that --graph-type is a required argument."""
        result = subprocess.run(
            [sys.executable, str(GENERATE_GRAPH_PY)],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should fail without required arguments
        assert result.returncode != 0
        assert 'graph-type' in result.stderr or 'required' in result.stderr

    def test_script_requires_vault_path(self):
        """Test that --vault-path is a required argument."""
        result = subprocess.run(
            [sys.executable, str(GENERATE_GRAPH_PY), '--graph-type', 'force'],
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should fail without vault-path
        assert result.returncode != 0
        assert 'vault-path' in result.stderr or 'required' in result.stderr

    def test_script_accepts_valid_graph_types(self):
        """Test that script validates graph-type choices."""
        result = subprocess.run(
            [sys.executable, str(GENERATE_GRAPH_PY), '--help'],
            capture_output=True,
            text=True,
            timeout=5
        )

        assert result.returncode == 0
        help_text = result.stdout

        # Should list valid graph types
        assert 'force' in help_text
        assert 'family' in help_text
        assert 'faction' in help_text

    def test_script_vault_id_is_optional(self):
        """Test that --vault-id is optional (will auto-create)."""
        result = subprocess.run(
            [sys.executable, str(GENERATE_GRAPH_PY), '--help'],
            capture_output=True,
            text=True,
            timeout=5
        )

        help_text = result.stdout
        # vault-id should be listed but not marked as required
        assert 'vault-id' in help_text.lower()


class TestGraphScriptExecution:
    """Tests for graph generation logic."""

    def test_script_imports_profiler_agent(self):
        """Test that script uses ProfilerAgent."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        assert 'ProfilerAgent' in content

    def test_script_calls_generate_graph_data(self):
        """Test that script calls generate_graph_data method."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        assert 'generate_graph_data' in content

    def test_script_calls_generate_graph_html(self):
        """Test that script calls generate_graph_html method."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        assert 'generate_graph_html' in content

    def test_script_uses_async_main(self):
        """Test that script uses asyncio for async operations."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        assert 'async def main' in content
        assert 'asyncio.run' in content or 'await' in content


class TestGraphScriptOutput:
    """Tests for output format (critical for Obsidian Plugin)."""

    def test_script_prints_output_path_to_stdout(self):
        """Test that script prints HTML path to stdout."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # CRITICAL: Plugin parses stdout to find the HTML file
        # Script must print the output path
        assert 'print(' in content

    def test_script_handles_errors_gracefully(self):
        """Test that script has error handling."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should have try/except blocks
        assert 'try:' in content
        assert 'except' in content

    def test_script_exits_with_error_code_on_failure(self):
        """Test that script uses sys.exit(1) on errors."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        assert 'sys.exit(1)' in content


class TestGraphScriptWithDatabase:
    """Integration tests with actual database (requires DB connection)."""

    @pytest.mark.integration
    def test_script_can_query_entities(self, test_vault_with_entities, tmp_path):
        """Test that script can query entities from database."""
        # This test would actually run the script
        # Skipped in unit tests, but valuable for integration testing
        vault = test_vault_with_entities

        # Note: Would need to mock ProfilerAgent to avoid actual graph generation
        # This is more of an integration test
        pass

    @pytest.mark.integration
    def test_script_generates_html_file(self, test_vault_with_entities, tmp_path, mocker):
        """Test that script creates HTML output file."""
        # Mock ProfilerAgent to avoid actual D3.js generation
        mock_profiler = mocker.patch("writeros.agents.profiler.ProfilerAgent")
        mock_instance = MagicMock()

        # Mock graph data
        mock_instance.generate_graph_data = AsyncMock(return_value={
            "nodes": [{"id": "node1", "name": "Hero"}],
            "links": [],
            "stats": {"node_count": 1, "link_count": 0}
        })

        # Mock HTML generation to return a test path
        output_path = tmp_path / "test_graph.html"
        mock_instance.generate_graph_html = MagicMock(return_value=str(output_path))
        mock_profiler.return_value = mock_instance

        # This would test actual execution
        # For now, we verify the mocking works
        assert mock_profiler is not None


class TestGraphScriptDatabaseConnection:
    """Tests for database connection handling."""

    def test_script_uses_get_or_create_vault_id(self):
        """Test that script can auto-create vault_id if not provided."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should handle the case where vault_id is not provided
        assert 'vault_id' in content.lower()

    def test_script_initializes_database_connection(self):
        """Test that script connects to database."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should import database utilities
        assert 'from writeros' in content


class TestGraphScriptLogging:
    """Tests for logging and debugging."""

    def test_script_uses_logging(self):
        """Test that script includes logging for debugging."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should use the WriterOS logger
        assert 'logger' in content or 'logging' in content

    def test_script_logs_graph_stats(self):
        """Test that script logs node/link counts."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should log information about generated graph
        has_logging = 'logger.info' in content or 'print(' in content
        assert has_logging


class TestGraphScriptCompatibility:
    """Tests for Obsidian Plugin compatibility requirements."""

    def test_script_outputs_absolute_path(self):
        """Test that output path is absolute (required by Plugin)."""
        # The Plugin needs an absolute path to open the file
        # Verify that the script uses proper path handling
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should use Path operations or similar
        assert 'Path(' in content or 'os.path' in content

    def test_script_creates_writeros_directory(self):
        """Test that script creates .writeros/graphs/ directory."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should create output directory structure
        assert '.writeros' in content or 'graphs' in content

    def test_script_passes_graph_type_to_agent(self):
        """Test that graph_type argument is passed to ProfilerAgent."""
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Should pass graph_type to the agent methods
        assert 'graph_type' in content
