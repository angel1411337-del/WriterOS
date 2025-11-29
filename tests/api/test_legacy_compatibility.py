"""
Tests for Obsidian Plugin Legacy Compatibility Layer.

Tests the /health, /analyze, and /chat/stream endpoints that
the Obsidian Plugin depends on.
"""
import pytest
import json
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlmodel import Session

from writeros.api.app import app
from writeros.schema import Vault, User, ConnectionType, SubscriptionTier


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_init_db(mocker):
    """Mock init_db to avoid actual database initialization."""
    return mocker.patch("writeros.utils.db.init_db")


@pytest.fixture
def test_vault(db_session, sample_vault_id):
    """Create a test vault in the database."""
    # Create user first
    user = User(
        email="test@writeros.local",
        username="testuser",
        tier=SubscriptionTier.FREE
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create vault
    vault = Vault(
        id=sample_vault_id,
        name="Test Vault",
        owner_id=user.id,
        connection_type=ConnectionType.LOCAL_OBSIDIAN,
        local_system_path="C:\\test\\vault"
    )
    db_session.add(vault)
    db_session.commit()
    db_session.refresh(vault)

    return vault


class TestHealthEndpoint:
    """Tests for /health endpoint (Plugin compatibility)."""

    def test_health_check_returns_ok(self, test_client, mock_init_db):
        """Test that health check returns OK status."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "mode" in data

    def test_health_check_includes_version(self, test_client, mock_init_db):
        """Test that health check includes version info."""
        response = test_client.get("/health")
        data = response.json()

        assert "version" in data
        # Version should be a string like "0.1.0"
        assert isinstance(data["version"], str)

    def test_health_check_includes_mode(self, test_client, mock_init_db):
        """Test that health check includes mode (local/saas)."""
        response = test_client.get("/health")
        data = response.json()

        assert "mode" in data
        # Mode should be "local" or similar
        assert isinstance(data["mode"], str)


class TestAnalyzeEndpoint:
    """Tests for /analyze endpoint (Plugin compatibility)."""

    def test_analyze_accepts_plugin_format(self, test_client, mock_init_db, test_vault, db_session, mocker):
        """Test that /analyze accepts the plugin's request format."""
        # Mock VaultIndexer
        mock_indexer = mocker.patch("writeros.api.app.VaultIndexer")

        # Mock get_db dependency
        def override_get_db():
            yield db_session

        from writeros.api.app import get_db
        app.dependency_overrides[get_db] = override_get_db

        request_data = {
            "vault_path": "C:\\test\\vault",
            "vault_id": str(test_vault.id)
        }

        response = test_client.post("/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "job_id" in data
        assert "message" in data

    def test_analyze_rejects_invalid_vault_id(self, test_client, mock_init_db):
        """Test that /analyze rejects invalid vault_id format."""
        request_data = {
            "vault_path": "C:\\test\\vault",
            "vault_id": "not-a-valid-uuid"
        }

        response = test_client.post("/analyze", json=request_data)

        assert response.status_code == 400
        assert "Invalid vault_id" in response.json()["detail"]

    def test_analyze_returns_404_for_nonexistent_vault(self, test_client, mock_init_db, db_session, mocker):
        """Test that /analyze returns 404 for non-existent vault."""
        fake_vault_id = str(uuid4())

        request_data = {
            "vault_path": "C:\\test\\vault",
            "vault_id": fake_vault_id
        }

        # Mock get_db dependency
        def override_get_db():
            yield db_session

        from writeros.api.app import get_db
        app.dependency_overrides[get_db] = override_get_db

        response = test_client.post("/analyze", json=request_data)

        assert response.status_code == 404
        assert "Vault not found" in response.json()["detail"]

    def test_analyze_triggers_background_task(self, test_client, mock_init_db, test_vault, db_session, mocker):
        """Test that /analyze triggers background indexing."""
        mock_indexer = mocker.patch("writeros.api.app.VaultIndexer")
        mock_background_tasks = mocker.MagicMock()

        request_data = {
            "vault_path": "C:\\test\\vault",
            "vault_id": str(test_vault.id)
        }

        # Mock get_db dependency
        def override_get_db():
            yield db_session

        from writeros.api.app import get_db
        app.dependency_overrides[get_db] = override_get_db

        with patch("writeros.api.app.BackgroundTasks", return_value=mock_background_tasks):
            response = test_client.post("/analyze", json=request_data)

        assert response.status_code == 200
        # Verify that VaultIndexer was instantiated (at least once)
        assert mock_indexer.called


class TestChatStreamEndpoint:
    """Tests for /chat/stream endpoint (Plugin compatibility)."""

    def test_chat_stream_accepts_plugin_format(self, test_client, mock_init_db, mocker):
        """Test that /chat/stream accepts the plugin's request format."""
        # Mock OrchestratorAgent
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        # Mock the async generator
        async def mock_process_chat(*args, **kwargs):
            yield "Hello"
            yield " world"
            yield "!"

        mock_instance.process_chat = mock_process_chat
        mock_orchestrator.return_value = mock_instance

        request_data = {
            "message": "Who is the main character?",
            "vault_id": str(uuid4()),
            "context_window": 5
        }

        response = test_client.post("/chat/stream", json=request_data)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_chat_stream_returns_sse_format(self, test_client, mock_init_db, mocker):
        """Test that /chat/stream returns Server-Sent Events format."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_process_chat(*args, **kwargs):
            yield "Test"
            yield " chunk"

        mock_instance.process_chat = mock_process_chat
        mock_orchestrator.return_value = mock_instance

        request_data = {
            "message": "Test message",
            "vault_id": str(uuid4())
        }

        response = test_client.post("/chat/stream", json=request_data)

        # Check that response contains SSE-formatted data
        content = response.text
        assert "data:" in content
        assert "[DONE]" in content

    def test_chat_stream_formats_chunks_as_json(self, test_client, mock_init_db, mocker):
        """Test that chunks are formatted as JSON payloads."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_process_chat(*args, **kwargs):
            yield "chunk1"

        mock_instance.process_chat = mock_process_chat
        mock_orchestrator.return_value = mock_instance

        request_data = {
            "message": "Test",
            "vault_id": str(uuid4())
        }

        response = test_client.post("/chat/stream", json=request_data)
        content = response.text

        # Should contain data: {"content": "chunk1"}
        assert 'data: {"content": "chunk1"}' in content

    def test_chat_stream_sends_done_marker(self, test_client, mock_init_db, mocker):
        """Test that stream ends with [DONE] marker."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_process_chat(*args, **kwargs):
            yield "test"

        mock_instance.process_chat = mock_process_chat
        mock_orchestrator.return_value = mock_instance

        request_data = {
            "message": "Test",
            "vault_id": str(uuid4())
        }

        response = test_client.post("/chat/stream", json=request_data)
        content = response.text

        # Should end with data: [DONE]
        assert "data: [DONE]" in content

    def test_chat_stream_handles_errors_gracefully(self, test_client, mock_init_db, mocker):
        """Test that errors during streaming are handled."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_process_chat(*args, **kwargs):
            yield "chunk1"
            raise Exception("Test error")

        mock_instance.process_chat = mock_process_chat
        mock_orchestrator.return_value = mock_instance

        request_data = {
            "message": "Test",
            "vault_id": str(uuid4())
        }

        response = test_client.post("/chat/stream", json=request_data)
        content = response.text

        # Should contain error in SSE format
        assert '"error"' in content

    def test_chat_stream_rejects_invalid_vault_id(self, test_client, mock_init_db):
        """Test that /chat/stream rejects invalid vault_id."""
        request_data = {
            "message": "Test",
            "vault_id": "invalid-uuid"
        }

        response = test_client.post("/chat/stream", json=request_data)

        assert response.status_code == 400


class TestPluginIntegration:
    """Integration tests simulating the Obsidian Plugin's workflow."""

    def test_plugin_startup_sequence(self, test_client, mock_init_db):
        """Test the sequence: health check -> analyze -> chat."""
        # Step 1: Plugin checks health
        health_response = test_client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"

    def test_plugin_can_discover_endpoints(self, test_client, mock_init_db):
        """Test that all required Plugin endpoints are available."""
        # Test OpenAPI schema includes legacy routes
        response = test_client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema["paths"]

        # Verify legacy endpoints exist
        assert "/health" in paths
        assert "/analyze" in paths
        assert "/chat/stream" in paths
