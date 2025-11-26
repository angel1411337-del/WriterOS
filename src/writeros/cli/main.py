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


@app.command()
def ingest(
    vault_path: str = typer.Option(..., help="Path to the vault root directory"),
    vault_id: str = typer.Option(None, help="Vault UUID (optional)"),
    include_pdfs: bool = typer.Option(True, help="Include PDF files in ingestion"),
    force_reindex: bool = typer.Option(False, help="Force re-indexing of all files")
):
    """Ingest a vault, processing Markdown and PDF files."""
    import asyncio
    from pathlib import Path
    from uuid import UUID
    from writeros.utils.indexer import VaultIndexer
    from writeros.utils.db import init_db, engine
    from sqlmodel import Session, select
    from writeros.schema import Vault

    async def _run():
        logger.info("ingestion_cli_started", vault_path=vault_path)
        
        path_obj = Path(vault_path)
        if not path_obj.exists():
            logger.error("vault_path_not_found", path=vault_path)
            raise FileNotFoundError(f"Vault path not found: {vault_path}")

        # Initialize DB if needed
        init_db()

        # Resolve vault_id
        vid = None
        if vault_id:
            vid = UUID(vault_id)
        else:
            # Try to find existing vault or create default
            with Session(engine) as session:
                vault = session.exec(select(Vault).limit(1)).first()
                if vault:
                    vid = vault.id
                    logger.info("using_existing_vault", vault_id=str(vid), name=vault.name)
                else:
                    # Create default vault
                    vault = Vault(
                        name="Default Vault",
                        local_system_path=vault_path,
                        connection_type="obsidian_local"
                    )
                    session.add(vault)
                    session.commit()
                    session.refresh(vault)
                    vid = vault.id
                    logger.info("created_default_vault", vault_id=str(vid))

        indexer = VaultIndexer(
            vault_path=vault_path,
            vault_id=vid,
            chunking_strategy="auto"
        )

        logger.info("indexing_started", include_pdfs=include_pdfs)
        results = await indexer.index_vault(
            include_pdfs=include_pdfs,
            force_reindex=force_reindex,
            directories=["."]  # Scan entire vault recursively
        )
        
        print(f"\nIngestion Complete!")
        print(f"Documents Indexed: {results.get('documents_indexed', 0)}")
        print(f"PDFs Processed: {results.get('pdfs_processed', 0)}")
        print(f"Chunks Created: {results.get('chunks_created', 0)}")

    asyncio.run(_run())


@app.command()
def stats(
    vault_id: str = typer.Option(None, help="Vault UUID (optional)")
):
    """Show database statistics."""
    from writeros.utils.db import engine
    from sqlmodel import Session, select, func
    from writeros.schema import Document, Entity, Vault

    with Session(engine) as session:
        # Get vault
        if vault_id:
            vault = session.get(Vault, vault_id)
        else:
            vault = session.exec(select(Vault).limit(1)).first()
        
        if not vault:
            print("No vault found in database.")
            return

        print(f"\nVault: {vault.name} ({vault.id})")
        print("-" * 40)

        # Document stats
        doc_count = session.exec(
            select(func.count(Document.id)).where(Document.vault_id == vault.id)
        ).one()
        print(f"Total Documents/Chunks: {doc_count}")

        # PDF specific stats
        pdf_chunks = session.exec(
            select(func.count(Document.id)).where(
                Document.vault_id == vault.id,
                Document.doc_type == "pdf"
            )
        ).one()
        print(f"PDF Chunks: {pdf_chunks}")

        # Entity stats
        entity_count = session.exec(
            select(func.count(Entity.id)).where(Entity.vault_id == vault.id)
        ).one()
        print(f"Total Entities: {entity_count}")
        print("-" * 40)


@app.command()
def chat(
    message: str = typer.Argument(..., help="The message to send to the agent"),
    vault_id: str = typer.Option(None, help="Vault UUID (optional)"),
    vault_path: str = typer.Option(None, help="Path to vault root (required for tools)")
):
    """Chat with the Orchestrator Agent about your vault."""
    import asyncio
    import os
    from uuid import UUID
    from writeros.agents.orchestrator import OrchestratorAgent
    from writeros.utils.db import engine
    from sqlmodel import Session, select
    from writeros.schema import Vault

    # Set VAULT_PATH env var if provided (for tools)
    if vault_path:
        os.environ["VAULT_PATH"] = vault_path

    async def _run():
        # Resolve vault_id
        vid = None
        if vault_id:
            vid = UUID(vault_id)
        else:
            with Session(engine) as session:
                vault = session.exec(select(Vault).limit(1)).first()
                if vault:
                    vid = vault.id
                else:
                    print("Error: No vault found. Run 'ingest' first.")
                    return

        print(f"\nThinking...\n")
        
        orchestrator = OrchestratorAgent()
        
        try:
            async for chunk in orchestrator.process_chat(
                user_message=message,
                vault_id=vid
            ):
                print(chunk, end="", flush=True)
            print("\n")
        except Exception as e:
            print(f"\nError: {e}")

    asyncio.run(_run())

if __name__ == "__main__":
    app()
