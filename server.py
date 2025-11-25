#!/usr/bin/env python3
"""
WriterOS Server Launcher
Launches the FastAPI server for Obsidian Plugin integration.

This script is called by the Obsidian Plugin's "Start Server" button.
It forces LOCAL mode and ensures the database is initialized on startup.
"""
import uvicorn
import os
import sys
from pathlib import Path

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent / "src"))

if __name__ == "__main__":
    # Force Local Mode for Obsidian usage
    os.environ["WRITEROS_MODE"] = "local"

    print("=" * 60)
    print("WriterOS Server Launcher")
    print("=" * 60)
    print(f"Mode: LOCAL (Obsidian Integration)")
    print(f"Port: 8000")
    print(f"Host: 127.0.0.1 (localhost only)")
    print("=" * 60)
    print()
    print("Starting server... (Press CTRL+C to stop)")
    print()

    try:
        uvicorn.run(
            "writeros.api.app:app",
            host="127.0.0.1",
            port=8000,
            reload=False,  # Disable reload for Obsidian plugin (stability)
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped gracefully")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nServer failed to start: {e}")
        sys.exit(1)
