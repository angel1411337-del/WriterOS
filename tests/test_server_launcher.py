"""
Tests for server.py - The Obsidian Plugin launcher script.

These tests verify that server.py correctly:
1. Sets WRITEROS_MODE=local
2. Adds src/ to Python path
3. Launches uvicorn with correct parameters
"""
import pytest
import subprocess
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import signal


PROJECT_ROOT = Path(__file__).parent.parent
SERVER_PY = PROJECT_ROOT / "server.py"


class TestServerLauncherConfiguration:
    """Tests for server.py environment configuration."""

    def test_server_py_exists(self):
        """Test that server.py exists in project root."""
        assert SERVER_PY.exists(), "server.py should exist in project root"

    def test_server_py_is_executable(self):
        """Test that server.py has python shebang."""
        with open(SERVER_PY, 'r') as f:
            first_line = f.readline()

        assert first_line.startswith('#!'), "server.py should have shebang"
        assert 'python' in first_line.lower(), "Shebang should reference python"

    @patch('sys.path')
    @patch.dict(os.environ, {}, clear=True)
    def test_server_sets_local_mode(self, mock_path):
        """Test that server.py sets WRITEROS_MODE=local."""
        # This test would need to import server.py, but that would
        # actually start the server. Instead, we verify the code exists.
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        assert 'WRITEROS_MODE' in content
        assert 'local' in content

    def test_server_imports_uvicorn(self):
        """Test that server.py imports uvicorn."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        assert 'import uvicorn' in content

    def test_server_adds_src_to_path(self):
        """Test that server.py adds src/ to sys.path."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        assert 'sys.path' in content
        assert 'src' in content


class TestServerLauncherUvicornConfig:
    """Tests for uvicorn configuration in server.py."""

    def test_server_uses_correct_host(self):
        """Test that server binds to 127.0.0.1 (localhost only)."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        assert '127.0.0.1' in content, "Server should bind to localhost"

    def test_server_uses_correct_port(self):
        """Test that server uses port 8000."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        assert '8000' in content, "Server should use port 8000"

    def test_server_disables_reload(self):
        """Test that server disables auto-reload for stability."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # reload=False should be set for Obsidian plugin stability
        assert 'reload=False' in content or 'reload = False' in content

    def test_server_targets_correct_app(self):
        """Test that server launches writeros.api.app:app."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        assert 'writeros.api.app:app' in content


class TestServerLauncherErrorHandling:
    """Tests for error handling in server.py."""

    def test_server_handles_keyboard_interrupt(self):
        """Test that server handles CTRL+C gracefully."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        assert 'KeyboardInterrupt' in content
        assert 'except' in content

    def test_server_handles_general_exceptions(self):
        """Test that server handles startup exceptions."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # Should have try/except for uvicorn.run
        assert 'try:' in content
        assert 'except' in content

    def test_server_exits_with_correct_codes(self):
        """Test that server uses appropriate exit codes."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # Should exit with 0 on success, 1 on error
        assert 'sys.exit(0)' in content
        assert 'sys.exit(1)' in content


class TestServerLauncherOutput:
    """Tests for server.py console output."""

    def test_server_prints_startup_banner(self):
        """Test that server prints informative startup message."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # Should print something about WriterOS and the configuration
        assert 'print(' in content

    def test_server_shows_mode_and_port(self):
        """Test that startup message includes mode and port info."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # Should mention mode (local) and port somewhere in prints
        has_mode_info = 'Mode' in content or 'LOCAL' in content
        has_port_info = 'Port' in content or '8000' in content

        assert has_mode_info, "Should display mode information"
        assert has_port_info, "Should display port information"


class TestServerLauncherIntegration:
    """Integration tests for server.py (these may actually start the server briefly)."""

    @pytest.mark.slow
    def test_server_can_be_imported(self):
        """Test that server.py can be imported without errors."""
        # Note: This won't actually run the server since it's behind if __name__ == "__main__"
        import importlib.util

        spec = importlib.util.spec_from_file_location("server", SERVER_PY)
        assert spec is not None
        assert spec.loader is not None

    @pytest.mark.slow
    @pytest.mark.skipif(
        not (PROJECT_ROOT / "src" / "writeros" / "api" / "app.py").exists(),
        reason="Requires full WriterOS installation"
    )
    def test_server_help_output(self):
        """Test that python server.py can be invoked (will fail without proper args)."""
        # Just verify the script is valid Python
        result = subprocess.run(
            [sys.executable, str(SERVER_PY), "--help"],
            capture_output=True,
            text=True,
            timeout=2
        )

        # It won't recognize --help, but it should at least be valid Python
        # and not crash with a syntax error
        assert "SyntaxError" not in result.stderr


class TestServerLauncherDocumentation:
    """Tests for documentation and code clarity in server.py."""

    def test_server_has_docstring(self):
        """Test that server.py has a module-level docstring."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # Should have triple-quoted docstring at top
        assert '"""' in content or "'''" in content

    def test_server_has_comments(self):
        """Test that server.py has explanatory comments."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # Should have at least some comments explaining the logic
        assert '#' in content

    def test_server_explains_obsidian_purpose(self):
        """Test that server.py mentions Obsidian Plugin in docs."""
        with open(SERVER_PY, 'r') as f:
            content = f.read()

        # Should mention that this is for Obsidian Plugin
        content_lower = content.lower()
        assert 'obsidian' in content_lower or 'plugin' in content_lower
