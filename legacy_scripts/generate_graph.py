#!/usr/bin/env python3
"""
CLI script for generating WriterOS graphs from Obsidian.
Called by the Obsidian plugin to generate graph visualizations.
"""
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.profiler import ProfilerAgent
from utils.vault_config import get_or_create_vault_id, ensure_graph_directory


async def main():
    parser = argparse.ArgumentParser(description='Generate WriterOS graph')
    parser.add_argument('--graph-type', required=True, 
                       choices=['force', 'family', 'faction', 'location'],
                       help='Type of graph to generate')
    parser.add_argument('--vault-path', required=True,
                       help='Path to the vault root directory')
    parser.add_argument('--vault-id', required=False,
                       help='Vault UUID (optional, will auto-create if not provided)')
    
    args = parser.parse_args()
    vault_path = Path(args.vault_path)
    
    # Get or create vault_id
    if args.vault_id:
        vault_id = UUID(args.vault_id)
    else:
        vault_id = get_or_create_vault_id(vault_path)
    
    print(f"Using vault_id: {vault_id}")
    
    # Generate graph
    profiler = ProfilerAgent()
    
    print(f"Generating {args.graph_type} graph...")
    
    graph_data = await profiler.generate_graph_data(
        vault_id=vault_id,
        graph_type=args.graph_type,
        max_nodes=100,
        canon_layer="primary"
    )
    
    print(f"Graph data generated: {graph_data['stats']['node_count']} nodes, {graph_data['stats']['link_count']} links")
    
    # Save to .writeros/graphs/
    output_path = profiler.generate_graph_html(
        graph_data=graph_data,
        vault_path=vault_path,
        graph_type=args.graph_type
    )
    
    # Print output path (Obsidian plugin parses this line)
    print(f"\nGraph generated successfully!")
    print(f"Graph HTML generated: {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
