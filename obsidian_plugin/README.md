# WriterOS Obsidian Plugin

This plugin integrates WriterOS with Obsidian, allowing you to generate interactive relationship graphs, family trees, and faction networks directly from your vault.

## Installation

1. **Prerequisites**:
   - Node.js and npm installed.
   - Python 3.8+ installed.
   - The WriterOS Python backend set up (see main project README).

2. **Build the Plugin**:
   
   **Bash**:
   ```bash
   cd obsidian_plugin
   npm install
   npm run build
   ```

   **PowerShell**:
   ```powershell
   cd obsidian_plugin
   .\build.ps1
   ```


3. **Install in Obsidian**:
   - Create a folder named `writeros` inside your vault's `.obsidian/plugins/` directory.
   - Copy `main.js`, `manifest.json`, and `styles.css` (if any) to that folder.
   - Enable the plugin in Obsidian Settings > Community Plugins.

## Configuration

1. Go to **Settings > WriterOS**.
2. **Python Interpreter Path**: Set the path to your Python executable (e.g., `python` or `/usr/bin/python3` or `C:\Path\To\venv\Scripts\python.exe`).
3. **Generator Script Path**: Set the absolute path to the `generate_graph.py` script in the WriterOS project directory (e.g., `C:\Users\rahme\IdeaProjects\YouTube Transcript Agent\generate_graph.py`).

## Usage

- Open the **Command Palette** (Ctrl/Cmd + P) and search for "WriterOS".
- Choose one of the graph types:
  - **Open Relationship Graph**: Force-directed graph of all entities.
  - **Open Family Tree**: Hierarchical view of family connections.
  - **Open Faction Network**: Radial view of factions and their members.
  - **Open Location Map**: Geographic view of locations.

The graph will be generated and opened in your default web browser.
