#!/usr/bin/env python3
"""
Generates AI_CONTEXT.md by concatenating files from the .context/ directory.
This ensures LLMs always have the latest architecture decisions.
"""
import os
from pathlib import Path

def generate_context():
    """
    Generates AI_CONTEXT.md by concatenating files from the .context/ directory.
    This ensures LLMs always have the latest architecture decisions.
    """
    root_dir = Path(__file__).parent.parent
    context_dir = root_dir / ".context"
    output_file = root_dir / "AI_CONTEXT.md"
    
    if not context_dir.exists():
        print(f"Error: {context_dir} does not exist.")
        return

    content = ["# WriterOS AI Context\n"]
    content.append("> **Auto-Generated Context File** - Update source files in `.context/`\n")
    
    # Order matters for AI understanding
    file_order = [
        "PROJECT.md",
        "ARCHITECTURE.md",
        "CONVENTIONS.md",
        "MODELS.md",
        "STATUS.md",
        "DECISIONS.md"
    ]

    for filename in file_order:
        file_path = context_dir / filename
        if file_path.exists():
            content.append(f"\n## {filename.replace('.md', '')}\n")
            content.append(file_path.read_text(encoding="utf-8"))
            content.append("\n---")

    output_file.write_text("\n".join(content), encoding="utf-8")
    print(f"✅ Generated {output_file}")

if __name__ == "__main__":
    generate_context()
