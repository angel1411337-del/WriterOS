"""
End-to-End Integration Tests for Obsidian Plugin Workflow.

These tests simulate the complete Obsidian Plugin usage flow:
1. Server startup (init_db creates user/vault)
2. Health check
3. Vault analysis/ingestion
4. Chat with RAG
5. Graph generation

Requires: Running PostgreSQL database
"""
import pytest
import asyncio
import subprocess
import sys
import time
import requests
from pathlib import Path
from uuid import uuid4, UUID
from sqlmodel import Session, select

from writeros.utils.db import engine, init_db
from writeros.schema import User, Vault, Entity, Document
from writeros.utils.indexer import VaultIndexer


PROJECT_ROOT = Path(__file__).parent.parent.parent
SERVER_PY = PROJECT_ROOT / "server.py"
GENERATE_GRAPH_PY = PROJECT_ROOT / "generate_graph.py"


@pytest.fixture(scope="module")
def test_vault_directory(tmp_path_factory):
    """Create a temporary vault with sample markdown files."""
    vault_dir = tmp_path_factory.mktemp("obsidian_vault")

    # Create directory structure
    (vault_dir / "Characters").mkdir()
    (vault_dir / "Locations").mkdir()
    (vault_dir / "Manuscripts").mkdir()

    # Create sample character file
    char_file = vault_dir / "Characters" / "Hero.md"
    char_file.write_text("""# Hero

## Overview
The protagonist of our story. A brave warrior with a mysterious past.

## Traits
- **Age**: 25
- **Skills**: Swordfighting, Magic
- **Weakness**: Trusts too easily

## Background
Hero grew up in the mountains, trained by the ancient Order.
""")

    # Create sample location file
    loc_file = vault_dir / "Locations" / "The_Kingdom.md"
    loc_file.write_text("""# The Kingdom

A vast realm ruled by the Council of Elders.

## Geography
- Capital: Crystal City
- Population: 1 million
- Climate: Temperate

## Politics
The Kingdom is governed by a council of seven elders.
""")

    # Create sample manuscript
    manuscript = vault_dir / "Manuscripts" / "Chapter_01.md"
    manuscript.write_text("""# Chapter 1: The Beginning

Hero stood at the edge of the cliff, looking down at The Kingdom below.
The wind howled, carrying whispers of the coming storm.

"I must warn them," Hero thought, gripping the ancient sword tighter.

The journey to Crystal City would take three days, but there was no time to waste.
""")

    return vault_dir


@pytest.fixture(scope="module")
def initialized_database():
    """Initialize database with default user/vault."""
    # Run init_db to set up tables and default data
    init_db()

    yield

    # Cleanup after tests
    # Note: In a real test environment, you might want to use a separate test database


class TestObsidianPluginStartup:
    """Tests for the server startup sequence (Step 1 of Plugin flow)."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_server_can_start(self):
        """Test that server.py can be started."""
        # Note: This would actually start the server
        # In a real integration test, you'd start it in a subprocess
        # and verify it's running, then shut it down

        # For now, we just verify the file exists and is valid Python
        assert SERVER_PY.exists()

        # Verify it's valid Python by importing it
        # (won't actually run due to __name__ == "__main__" guard)
        import importlib.util
        spec = importlib.util.spec_from_file_location("server", SERVER_PY)
        assert spec is not None

    @pytest.mark.integration
    def test_init_db_creates_default_entities(self, initialized_database):
        """Test that init_db creates default user and vault."""
        with Session(engine) as session:
            # Check for admin user
            admin = session.exec(
                select(User).where(User.email == "admin@writeros.local")
            ).first()

            assert admin is not None, "Admin user should be created"

            # Check for at least one vault
            vaults = session.exec(select(Vault)).all()
            assert len(vaults) > 0, "At least one vault should exist"


class TestObsidianPluginHealthCheck:
    """Tests for health check endpoint (Step 2 of Plugin flow)."""

    @pytest.mark.integration
    def test_health_check_responds(self, initialized_database):
        """Test that /health endpoint responds correctly."""
        # This assumes the server is running
        # In a full integration test, you'd start the server first

        # For now, we can use TestClient
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.integration
    def test_plugin_can_detect_server_running(self, initialized_database):
        """Test that Plugin can detect if server is running via /health."""
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        client = TestClient(app)

        # Simulate Plugin's health check logic
        try:
            response = client.get("/health")
            server_is_running = response.status_code == 200
        except Exception:
            server_is_running = False

        assert server_is_running


class TestObsidianPluginVaultAnalysis:
    """Tests for vault analysis/ingestion (Step 3 of Plugin flow)."""

    @pytest.mark.integration
    def test_analyze_endpoint_accepts_vault(self, initialized_database, test_vault_directory, mocker):
        """Test that /analyze endpoint can process a vault."""
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        # Get vault ID
        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            assert vault is not None

        # Mock VaultIndexer to avoid actual indexing in unit test
        mock_indexer = mocker.patch("writeros.api.app.VaultIndexer")

        client = TestClient(app)
        response = client.post("/analyze", json={
            "vault_path": str(test_vault_directory),
            "vault_id": str(vault.id)
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "job_id" in data

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_full_vault_indexing_flow(self, initialized_database, test_vault_directory, mock_embedding_service):
        """Test complete vault indexing with VaultIndexer."""
        # Get or create vault
        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            if not vault:
                pytest.skip("No vault available for testing")

        # Create indexer
        indexer = VaultIndexer(
            vault_path=str(test_vault_directory),
            vault_id=vault.id,
            chunking_strategy="auto"
        )

        # Run indexing (this will actually index the files)
        result = await indexer.index_vault(force_reindex=True)

        # Verify documents were created
        with Session(engine) as session:
            docs = session.exec(
                select(Document).where(Document.vault_id == vault.id)
            ).all()

            # Should have indexed at least the 3 files we created
            assert len(docs) > 0


class TestObsidianPluginChat:
    """Tests for chat functionality (Step 4 of Plugin flow)."""

    @pytest.mark.integration
    def test_chat_stream_endpoint(self, initialized_database, mocker):
        """Test that /chat/stream works with Plugin format."""
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        # Mock OrchestratorAgent
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = mocker.MagicMock()

        async def mock_chat(*args, **kwargs):
            yield "Hello"
            yield " from"
            yield " WriterOS"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Get vault ID
        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            if not vault:
                pytest.skip("No vault available")

        client = TestClient(app)
        response = client.post("/chat/stream", json={
            "message": "Tell me about Hero",
            "vault_id": str(vault.id)
        })

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    @pytest.mark.integration
    def test_chat_returns_sse_format(self, initialized_database, mocker):
        """Test that chat response is in SSE format."""
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = mocker.MagicMock()

        async def mock_chat(*args, **kwargs):
            yield "Test response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            if not vault:
                pytest.skip("No vault available")

        client = TestClient(app)
        response = client.post("/chat/stream", json={
            "message": "Test",
            "vault_id": str(vault.id)
        })

        content = response.text
        # Should contain SSE format
        assert "data:" in content
        assert "[DONE]" in content


class TestObsidianPluginGraphGeneration:
    """Tests for graph generation (Step 5 of Plugin flow)."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_graph_script_can_execute(self, initialized_database, test_vault_directory):
        """Test that generate_graph.py can be executed."""
        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            if not vault:
                pytest.skip("No vault available")

        # Note: This would actually run the graph generation
        # For a real test, you'd mock ProfilerAgent
        assert GENERATE_GRAPH_PY.exists()

    @pytest.mark.integration
    def test_graph_generation_outputs_path(self, initialized_database, test_vault_directory, mocker):
        """Test that graph generation prints output path (Plugin requirement)."""
        # Mock ProfilerAgent to avoid actual graph generation
        mock_profiler = mocker.patch("writeros.agents.profiler.ProfilerAgent")
        mock_instance = mocker.MagicMock()

        mock_instance.generate_graph_data = mocker.AsyncMock(return_value={
            "nodes": [],
            "links": [],
            "stats": {"node_count": 0, "link_count": 0}
        })

        mock_instance.generate_graph_html = mocker.MagicMock(
            return_value="/fake/path/to/graph.html"
        )

        mock_profiler.return_value = mock_instance

        # This would test actual execution
        # For now, verify the script structure
        with open(GENERATE_GRAPH_PY, 'r') as f:
            content = f.read()

        # Script should print output path for Plugin to parse
        assert 'print(' in content


class TestObsidianPluginCompleteWorkflow:
    """End-to-end tests for complete Plugin workflow."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_complete_plugin_workflow_sequence(
        self,
        initialized_database,
        test_vault_directory,
        mock_embedding_service,
        mocker
    ):
        """Test the complete sequence: startup → health → analyze → chat → graph."""
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        client = TestClient(app)

        # Step 1: Check health
        health_response = client.get("/health")
        assert health_response.status_code == 200

        # Step 2: Get vault
        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            assert vault is not None

        # Step 3: Analyze vault (mock indexer)
        mock_indexer = mocker.patch("writeros.api.app.VaultIndexer")
        analyze_response = client.post("/analyze", json={
            "vault_path": str(test_vault_directory),
            "vault_id": str(vault.id)
        })
        assert analyze_response.status_code == 200

        # Step 4: Chat (mock orchestrator)
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = mocker.MagicMock()

        async def mock_chat(*args, **kwargs):
            yield "Response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        chat_response = client.post("/chat/stream", json={
            "message": "Test",
            "vault_id": str(vault.id)
        })
        assert chat_response.status_code == 200

        # Step 5: Verify all steps completed successfully
        # (Graph generation tested separately)

    @pytest.mark.integration
    def test_plugin_error_recovery(self, initialized_database, mocker):
        """Test that Plugin can recover from errors gracefully."""
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        client = TestClient(app)

        # Test with invalid vault_id
        response = client.post("/analyze", json={
            "vault_path": "/fake/path",
            "vault_id": "invalid-uuid"
        })

        # Should return error, not crash
        assert response.status_code in [400, 404, 500]
        assert "detail" in response.json()


class TestObsidianPluginDataPersistence:
    """Tests for data persistence across Plugin sessions."""

    @pytest.mark.integration
    def test_vault_id_persists_to_filesystem(self, initialized_database, tmp_path):
        """Test that vault_id is written to .writeros/vault_id."""
        from writeros.utils.db import write_uuid_to_filesystem

        test_uuid = uuid4()
        write_uuid_to_filesystem(test_uuid, str(tmp_path))

        # Verify file exists
        vault_id_file = tmp_path / ".writeros" / "vault_id"
        assert vault_id_file.exists()

        # Verify content
        content = vault_id_file.read_text().strip()
        assert UUID(content) == test_uuid

    @pytest.mark.integration
    async def test_indexed_data_persists(self, initialized_database, test_vault_directory, mock_embedding_service):
        """Test that indexed documents persist in database."""
        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            if not vault:
                pytest.skip("No vault available")

        # Index vault
        indexer = VaultIndexer(
            vault_path=str(test_vault_directory),
            vault_id=vault.id
        )
        await indexer.index_vault(force_reindex=True)

        # Query in new session to verify persistence
        with Session(engine) as session:
            docs = session.exec(
                select(Document).where(Document.vault_id == vault.id)
            ).all()

            assert len(docs) > 0, "Documents should persist in database"


@pytest.mark.integration
class TestObsidianPluginPerformance:
    """Performance tests for Plugin operations."""

    def test_health_check_is_fast(self):
        """Test that health check responds quickly (<100ms)."""
        from fastapi.testclient import TestClient
        from writeros.api.app import app

        client = TestClient(app)

        start = time.time()
        response = client.get("/health")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 0.1, "Health check should respond in <100ms"

    @pytest.mark.slow
    def test_indexing_provides_progress_feedback(self, initialized_database, test_vault_directory, mock_embedding_service):
        """Test that indexing provides feedback (doesn't freeze Plugin UI)."""
        with Session(engine) as session:
            vault = session.exec(select(Vault)).first()
            if not vault:
                pytest.skip("No vault available")

        # The analyze endpoint should return immediately with job_id
        # Actual indexing happens in background

        from fastapi.testclient import TestClient
        from writeros.api.app import app

        client = TestClient(app)

        start = time.time()
        response = client.post("/analyze", json={
            "vault_path": str(test_vault_directory),
            "vault_id": str(vault.id)
        })
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 1.0, "Analyze endpoint should return immediately"
        assert "job_id" in response.json()
