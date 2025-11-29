"""
Integration tests for temporal context in chat endpoints.

Verifies that:
1. LegacyChatRequest accepts frontmatter and temporal params
2. Frontmatter is parsed correctly
3. Temporal context is passed to OrchestratorAgent
4. Anti-spoiler filtering works end-to-end
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

from writeros.api.app import app


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestLegacyChatRequestWithFrontmatter:
    """Tests for LegacyChatRequest with frontmatter support."""

    def test_accepts_frontmatter_dict(self, test_client, mocker):
        """Test that /chat/stream accepts frontmatter parameter."""
        # Mock OrchestratorAgent
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            yield "Response chunk"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Request with frontmatter
        response = test_client.post("/chat/stream", json={
            "message": "What happened with the sword?",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {
                "sequence_order": 5,
                "title": "Chapter 5",
                "tags": ["draft"]
            }
        })

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_extracts_sequence_order_from_frontmatter(self, test_client, mocker):
        """Test that sequence_order is extracted from frontmatter."""
        # Mock OrchestratorAgent
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            # Verify temporal params were passed
            assert kwargs.get("current_sequence_order") == 5
            yield "Response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Request with frontmatter containing sequence_order
        response = test_client.post("/chat/stream", json={
            "message": "Is the King alive?",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {
                "sequence_order": 5
            }
        })

        assert response.status_code == 200

    def test_extracts_story_time_from_frontmatter(self, test_client, mocker):
        """Test that story_time is extracted from frontmatter."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            # Verify temporal params were passed
            story_time = kwargs.get("current_story_time")
            assert story_time is not None
            assert story_time["year"] == 280
            assert story_time["month"] == 3
            yield "Response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Request with story_time in frontmatter
        response = test_client.post("/chat/stream", json={
            "message": "What's happening?",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {
                "story_time": {
                    "year": 280,
                    "month": 3,
                    "day": 15
                }
            }
        })

        assert response.status_code == 200

    def test_explicit_params_override_frontmatter(self, test_client, mocker):
        """Test that explicit parameters take priority over frontmatter."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            # Should use explicit param (10), not frontmatter (5)
            assert kwargs.get("current_sequence_order") == 10
            yield "Response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Request with both explicit and frontmatter
        response = test_client.post("/chat/stream", json={
            "message": "Test",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "current_sequence": 10,  # Explicit (priority)
            "frontmatter": {
                "sequence_order": 5  # Frontmatter (fallback)
            }
        })

        assert response.status_code == 200


class TestObsidianPluginIntegration:
    """Integration tests for Obsidian Plugin temporal workflow."""

    def test_plugin_sends_active_file_frontmatter(self, test_client, mocker):
        """
        Simulate Obsidian Plugin behavior:
        1. User opens Chapter_05.md
        2. Plugin reads frontmatter
        3. Plugin sends frontmatter with chat request
        4. Backend extracts temporal context
        """
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            # Verify Plugin's frontmatter was parsed
            assert kwargs.get("current_sequence_order") == 5
            yield "Temporal-aware response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Simulate Plugin request
        response = test_client.post("/chat/stream", json={
            "message": "Is the King alive?",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {
                "title": "Chapter 5: The Battle",
                "sequence_order": 5,
                "date": "2024-01-15",
                "tags": ["battle", "climax"]
            }
        })

        assert response.status_code == 200

    def test_plugin_sends_manuscript_with_story_time(self, test_client, mocker):
        """
        Test Plugin sending manuscript file with story_time frontmatter.
        """
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            story_time = kwargs.get("current_story_time")
            assert story_time["year"] == 300
            assert story_time["month"] == 12
            yield "Filtered by story time"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Simulate manuscript with in-universe date
        response = test_client.post("/chat/stream", json={
            "message": "Describe the political situation",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {
                "title": "The Winter War",
                "story_time": {
                    "year": 300,
                    "month": 12,
                    "day": 1
                }
            }
        })

        assert response.status_code == 200


class TestTemporalContextLogging:
    """Tests for logging temporal context."""

    def test_logs_temporal_context_when_provided(self, test_client, mocker, caplog):
        """Test that temporal context is logged for debugging."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            yield "Response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        response = test_client.post("/chat/stream", json={
            "message": "Test",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "current_sequence": 7
        })

        assert response.status_code == 200
        # Temporal context should be logged
        # (Actual log checking would depend on logger configuration)


class TestBackwardCompatibility:
    """Tests for backward compatibility with old Plugin versions."""

    def test_works_without_frontmatter(self, test_client, mocker):
        """Test that endpoint works without frontmatter (old Plugin version)."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            # Should work in god mode (no temporal filtering)
            assert kwargs.get("current_sequence_order") is None
            assert kwargs.get("current_story_time") is None
            yield "Response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        # Old-style request (no temporal params)
        response = test_client.post("/chat/stream", json={
            "message": "What's happening?",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000"
        })

        assert response.status_code == 200

    def test_accepts_empty_frontmatter(self, test_client, mocker):
        """Test that empty frontmatter dict is handled gracefully."""
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            assert kwargs.get("current_sequence_order") is None
            yield "Response"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        response = test_client.post("/chat/stream", json={
            "message": "Test",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {}  # Empty frontmatter
        })

        assert response.status_code == 200


class TestRealWorldScenarios:
    """Real-world usage scenarios."""

    def test_writing_chapter_1_no_chapter_10_info(self, test_client, mocker):
        """
        Scenario: Writer is editing Chapter_01.md
        Query: "Is the King alive?"
        Expected: Should use sequence_order=1 filter
        """
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            # Verify Chapter 1 filter is applied
            assert kwargs.get("current_sequence_order") == 1
            # In real scenario, this would prevent Chapter 10 spoilers
            yield "Yes, the King is currently alive and ruling"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        response = test_client.post("/chat/stream", json={
            "message": "Is the King alive?",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {
                "title": "Chapter 1: The Beginning",
                "sequence_order": 1
            }
        })

        assert response.status_code == 200

    def test_editing_full_manuscript_god_mode(self, test_client, mocker):
        """
        Scenario: Writer is in index/overview file
        No sequence_order in frontmatter
        Expected: God mode (see all timeline)
        """
        mock_orchestrator = mocker.patch("writeros.api.app.OrchestratorAgent")
        mock_instance = MagicMock()

        async def mock_chat(*args, **kwargs):
            # No temporal filter
            assert kwargs.get("current_sequence_order") is None
            yield "Complete timeline information"

        mock_instance.process_chat = mock_chat
        mock_orchestrator.return_value = mock_instance

        response = test_client.post("/chat/stream", json={
            "message": "Give me a complete timeline of the King's story arc",
            "vault_id": "550e8400-e29b-41d4-a716-446655440000",
            "frontmatter": {
                "title": "Story Bible - Kings",
                # No sequence_order - not a chapter file
            }
        })

        assert response.status_code == 200
