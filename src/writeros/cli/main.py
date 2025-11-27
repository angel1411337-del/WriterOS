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
    vault_path: str = typer.Option(None, help="Path to vault root (required for tools)"),
    enable_tracking: bool = typer.Option(True, help="Enable execution tracking"),
    use_langgraph: bool = typer.Option(True, help="Use LangGraph orchestrator (default: True)")
):
    """Chat with the Orchestrator Agent about your vault."""
    import asyncio
    import os
    from uuid import UUID
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

        # Choose orchestrator based on flag
        if use_langgraph:
            from writeros.agents.langgraph_orchestrator import LangGraphOrchestrator
            orchestrator = LangGraphOrchestrator(enable_tracking=enable_tracking)
            logger.info("using_langgraph_orchestrator")
        else:
            from writeros.agents.orchestrator import OrchestratorAgent
            orchestrator = OrchestratorAgent(enable_tracking=enable_tracking)
            logger.info("using_original_orchestrator")

        try:
            async for chunk in orchestrator.process_chat(
                user_message=message,
                vault_id=vid
            ):
                # Handle Unicode encoding for Windows console
                try:
                    print(chunk, end="", flush=True)
                except UnicodeEncodeError:
                    # Fallback: encode with replacement for unsupported characters
                    import sys
                    safe_chunk = chunk.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
                    print(safe_chunk, end="", flush=True)
            print("\n")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(_run())


@app.command()
def tracking_stats(
    vault_id: str = typer.Option(None, help="Vault UUID (optional)"),
    hours: int = typer.Option(24, help="Time window in hours")
):
    """Show agent execution tracking statistics."""
    from uuid import UUID
    from writeros.utils.execution_analytics import ExecutionAnalytics
    from writeros.utils.db import engine
    from sqlmodel import Session, select
    from writeros.schema import Vault

    with Session(engine) as session:
        # Resolve vault_id
        vid = None
        if vault_id:
            vid = UUID(vault_id)
        else:
            vault = session.exec(select(Vault).limit(1)).first()
            if vault:
                vid = vault.id

    if not vid:
        print("No vault found.")
        return

    print(f"\n{'='*60}")
    print(f"Agent Execution Statistics (Last {hours} hours)")
    print(f"{'='*60}\n")

    # Recent executions
    recent = ExecutionAnalytics.get_recent_executions(vault_id=vid, limit=10)
    print(f"Recent Executions: {len(recent)}")
    for ex in recent[:5]:
        status_emoji = "✓" if ex.status == "success" else "✗" if ex.status == "failed" else "⊘"
        print(f"  {status_emoji} {ex.agent_name} - {ex.status} ({ex.duration_ms:.0f}ms)")

    # Failed executions
    failed = ExecutionAnalytics.get_failed_executions(vault_id=vid, hours=hours)
    print(f"\nFailed Executions: {len(failed)}")
    for ex in failed[:3]:
        print(f"  ✗ {ex.agent_name}: {ex.error_type}")

    # Response quality
    quality = ExecutionAnalytics.analyze_response_quality(vault_id=vid, hours=hours)
    if "error" not in quality:
        print(f"\nLLM Response Quality:")
        print(f"  Total Responses: {quality['total_responses']}")
        print(f"  Valid: {quality['valid_responses']} ({quality['validity_rate']*100:.1f}%)")
        print(f"  Avg Quality Score: {quality['avg_quality_score']:.2f}" if quality['avg_quality_score'] else "  Avg Quality Score: N/A")
        print(f"  Distribution:")
        for category, count in quality['quality_distribution'].items():
            print(f"    {category}: {count}")

    print(f"\n{'='*60}\n")


@app.command()
def view_execution(
    execution_id: str = typer.Argument(..., help="Execution ID to view")
):
    """View detailed execution information."""
    from uuid import UUID
    from writeros.utils.execution_analytics import ExecutionAnalytics
    import json

    exec_id = UUID(execution_id)

    details = ExecutionAnalytics.get_execution_with_logs(exec_id)

    if "error" in details:
        print(f"Error: {details['error']}")
        return

    ex = details['execution']
    logs = details['logs']

    print(f"\n{'='*60}")
    print(f"Execution Details: {execution_id}")
    print(f"{'='*60}\n")

    print(f"Agent: {ex.agent_name}")
    print(f"Method: {ex.agent_method}")
    print(f"Status: {ex.status}")
    print(f"Duration: {ex.duration_ms:.0f}ms" if ex.duration_ms else "Duration: N/A")

    if ex.relevance_score is not None:
        print(f"\nRelevance:")
        print(f"  Score: {ex.relevance_score}")
        print(f"  Reasoning: {ex.relevance_reasoning}")

    if ex.llm_model:
        print(f"\nLLM:")
        print(f"  Model: {ex.llm_model}")
        print(f"  Tokens: {ex.llm_tokens_used}")
        print(f"  Latency: {ex.llm_latency_ms:.0f}ms" if ex.llm_latency_ms else "  Latency: N/A")

    if ex.response_quality_score is not None:
        print(f"\nResponse Quality:")
        print(f"  Valid: {ex.response_valid}")
        print(f"  Score: {ex.response_quality_score:.2f}")
        if ex.response_validation_errors:
            print(f"  Errors: {', '.join(ex.response_validation_errors)}")
        if ex.response_warnings:
            print(f"  Warnings: {', '.join(ex.response_warnings)}")

    if ex.error_message:
        print(f"\nError:")
        print(f"  Type: {ex.error_type}")
        print(f"  Message: {ex.error_message}")

    print(f"\nStage Timeline:")
    for log in logs:
        duration = f"({log.duration_ms:.0f}ms)" if log.duration_ms else ""
        print(f"  [{log.stage.value}] {log.message} {duration}")

    print(f"\n{'='*60}\n")


@app.command()
def poor_responses(
    vault_id: str = typer.Option(None, help="Vault UUID (optional)"),
    threshold: float = typer.Option(0.7, help="Quality threshold"),
    hours: int = typer.Option(24, help="Time window in hours"),
    limit: int = typer.Option(10, help="Max results")
):
    """Show LLM responses with quality issues."""
    from uuid import UUID
    from writeros.utils.execution_analytics import ExecutionAnalytics
    from writeros.utils.db import engine
    from sqlmodel import Session, select
    from writeros.schema import Vault

    with Session(engine) as session:
        # Resolve vault_id
        vid = None
        if vault_id:
            vid = UUID(vault_id)
        else:
            vault = session.exec(select(Vault).limit(1)).first()
            if vault:
                vid = vault.id

    poor = ExecutionAnalytics.get_poor_quality_responses(
        vault_id=vid,
        quality_threshold=threshold,
        hours=hours,
        limit=limit
    )

    print(f"\n{'='*60}")
    print(f"Poor Quality LLM Responses (Score < {threshold})")
    print(f"{'='*60}\n")

    if not poor:
        print("No poor quality responses found.")
    else:
        for ex in poor:
            print(f"Execution: {ex['execution_id']}")
            print(f"  Agent: {ex['agent_name']}")
            print(f"  Model: {ex['llm_model']}")
            print(f"  Quality Score: {ex['quality_score']:.2f}")
            if ex['validation_errors']:
                print(f"  Errors: {', '.join(ex['validation_errors'])}")
            if ex['warnings']:
                print(f"  Warnings: {', '.join(ex['warnings'])}")
            print()

    print(f"{'='*60}\n")


@app.command()
def debug_agent(
    agent_name: str = typer.Argument(..., help="Agent name (e.g., PsychologistAgent)"),
    conversation_id: str = typer.Option(None, help="Conversation ID"),
    vault_id: str = typer.Option(None, help="Vault UUID (optional)")
):
    """Debug why an agent didn't fire."""
    from uuid import UUID
    from writeros.utils.execution_analytics import ExecutionAnalytics
    from writeros.utils.db import engine
    from sqlmodel import Session, select
    from writeros.schema import Vault

    with Session(engine) as session:
        # Resolve vault_id
        vid = None
        if vault_id:
            vid = UUID(vault_id)
        else:
            vault = session.exec(select(Vault).limit(1)).first()
            if vault:
                vid = vault.id

    if not conversation_id or not vid:
        print("Error: conversation_id and vault_id are required")
        return

    conv_id = UUID(conversation_id)

    result = ExecutionAnalytics.debug_why_agent_didnt_fire(
        agent_name=agent_name,
        conversation_id=conv_id,
        vault_id=vid
    )

    print(f"\n{'='*60}")
    print(f"Debug: {agent_name}")
    print(f"{'='*60}\n")

    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}\n")

    if 'possible_reasons' in result:
        print("Possible Reasons:")
        for reason in result['possible_reasons']:
            print(f"  - {reason}")

    if 'executions' in result:
        print(f"\nExecution Details:")
        for ex in result['executions']:
            print(f"  Execution ID: {ex.get('execution_id', 'N/A')}")
            if 'relevance_score' in ex:
                print(f"    Relevance: {ex['relevance_score']}")
                print(f"    Reasoning: {ex['relevance_reasoning']}")
            if 'error_type' in ex:
                print(f"    Error: {ex['error_type']} - {ex['error_message']}")

    print(f"\n{'='*60}\n")



@app.command()
def inspect_retrieval(
    query: str = typer.Argument(..., help="The search query"),
    vault_id: str = typer.Option(None, help="Vault UUID (optional)"),
    limit: int = typer.Option(5, help="Results per type"),
    metric: str = typer.Option("cosine", help="Distance metric: cosine or l2")
):
    """Debug RAG retrieval by showing raw results and scores."""
    import asyncio
    from uuid import UUID
    from writeros.rag.retriever import RAGRetriever
    from writeros.utils.db import engine
    from sqlmodel import Session, select
    from writeros.schema import Vault, Document, Entity, Fact, Event

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
        
        if not vid:
            print("Error: No vault found. Run 'ingest' first.")
            return

        # Helper for Windows Unicode support
        def safe_print(text, end="\n"):
            try:
                print(text, end=end)
            except UnicodeEncodeError:
                import sys
                encoding = sys.stdout.encoding or 'utf-8'
                safe_text = text.encode(encoding, errors='replace').decode(encoding)
                print(safe_text, end=end)

        print(f"\n{'='*60}")
        print(f"RAG Inspection: '{query}'")
        print(f"Vault: {vid}")
        print(f"{'='*60}\n")

        retriever = RAGRetriever()
        
        results = await retriever.retrieve(
            query=query,
            vault_id=vid,
            limit=limit,
            distance_metric=metric
        )

        # Helper to print section
        def print_section(title, items, icon):
            if not items:
                return
            safe_print(f"\n{icon} {title} ({len(items)})")
            safe_print("-" * 40)
            for item in items:
                content = ""
                name = "Unknown"
                kind = ""
                source = None

                if isinstance(item, Document):
                    content = item.content
                    name = item.title
                    kind = item.doc_type
                    # Document.source is a relationship, avoid accessing it
                elif isinstance(item, Entity):
                    content = item.description or ""
                    name = item.name
                    kind = item.type
                elif isinstance(item, Fact):
                    content = item.content
                    name = "Fact"
                    kind = item.fact_type
                    source = item.source # Fact.source is a string
                elif isinstance(item, Event):
                    content = item.description or ""
                    name = item.name
                    # Event doesn't have a type field, use "event"
                    kind = "event"
                
                if len(content) > 150:
                    content = content[:150] + "..."
                
                safe_print(f"• [{kind}] {name}")
                safe_print(f"  \"{content}\"")
                
                if source:
                    safe_print(f"  Source: {source}")
                
                safe_print("")
        
        print_section("DOCUMENTS", results.documents, "📄")
        print_section("ENTITIES", results.entities, "👤")
        print_section("FACTS", results.facts, "📌")
        print_section("EVENTS", results.events, "📅")

        print(f"{'='*60}\n")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
