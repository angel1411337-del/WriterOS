import typer
from writeros.core.logging import setup_logging, get_logger

# Initialize logging before anything else
setup_logging()
logger = get_logger(__name__)

app = typer.Typer()

@app.command()
def serve():
    """Start the API server."""
    import uvicorn
    logger.info("starting_api_server")
    uvicorn.run("writeros.api.app:app", host="0.0.0.0", port=8000, reload=True)

@app.command()
def version():
    """Show version."""
    from writeros import __version__
    print(f"WriterOS v{__version__}")

if __name__ == "__main__":
    app()

@app.command()
def generate_graph(
    vault_path: str = typer.Option(..., help="Path to the vault root directory"),
    graph_type: str = typer.Option("force", help="Type of graph: force, family, faction, location"),
    vault_id: str = typer.Option(None, help="Vault UUID (optional)")
):
    """Generate a D3.js graph visualization for the vault."""
    import asyncio
    from pathlib import Path
    from uuid import UUID
    from writeros.agents.profiler import ProfilerAgent
    from writeros.utils.db import get_or_create_vault_id # We might need to move this or import it
    
    # Quick fix for get_or_create_vault_id if it's not in utils.db yet
    # It was in utils.vault_config in the legacy script.
    # We'll implement a simple version here or find it.
    
    async def _run():
        logger.info("generating_graph_cli", graph_type=graph_type, vault_path=vault_path)
        
        path_obj = Path(vault_path)
        if not path_obj.exists():
            logger.error("vault_path_not_found", path=vault_path)
            raise FileNotFoundError(f"Vault path not found: {vault_path}")
            
        # Resolve vault_id
        vid = None
        if vault_id:
            vid = UUID(vault_id)
        else:
            # Simple logic to read .writeros/vault_id or create one
            # Ideally this should be a utility function
            config_path = path_obj / ".writeros" / "vault_id"
            if config_path.exists():
                vid = UUID(config_path.read_text().strip())
            else:
                vid = UUID(int=0) # Placeholder or generate new
                logger.warning("using_placeholder_vault_id", id=str(vid))

        profiler = ProfilerAgent()
        
        graph_data = await profiler.generate_graph_data(
            vault_id=vid,
            graph_type=graph_type,
            max_nodes=100,
            canon_layer="primary"
        )
        
        output_path = profiler.generate_graph_html(
            graph_data=graph_data,
            vault_path=path_obj,
            graph_type=graph_type
        )
        
        print(f"Graph generated successfully!")
        print(f"Graph HTML generated: {output_path}")

    asyncio.run(_run())
