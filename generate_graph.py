#!/usr/bin/env python3
"""
Graph generation script for WriterOS.
Generates D3.js visualizations of vault data.
"""
import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

async def main():
    from src.writeros.core.logging import setup_logging, get_logger
    from src.writeros.agents.profiler import ProfilerAgent
    from src.writeros.utils.db import get_or_create_vault_id
    from uuid import UUID
    import argparse
    
    setup_logging()
    logger = get_logger(__name__)
    
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
        vault_id = get_or_create_vault_id(str(vault_path))
    
    logger.info("generating_graph", vault_id=str(vault_id), graph_type=args.graph_type)
    
    # Generate graph
    profiler = ProfilerAgent()
    
    graph_data = await profiler.generate_graph_data(
        vault_id=vault_id,
        graph_type=args.graph_type,
        max_nodes=100,
        canon_layer="primary"
    )
    
    logger.info("graph_data_generated", 
                nodes=graph_data.get('stats', {}).get('node_count', len(graph_data.get('nodes', []))), 
                links=graph_data.get('stats', {}).get('link_count', len(graph_data.get('links', []))))
    
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
        import traceback
        traceback.print_exc()
        sys.exit(1)
