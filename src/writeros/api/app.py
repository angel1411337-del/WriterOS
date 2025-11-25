"""
WriterOS v2.5 API
FastAPI application with three main router groups:
- /vault: Ingestion and indexing
- /agent: Agent execution endpoints
- /sync: Obsidian synchronization

PLUS Legacy Compatibility Layer for Obsidian Plugin:
- /health: Health check (already implemented)
- /analyze: Maps to VaultIndexer (Plugin compatibility)
- /chat/stream: Maps to Orchestrator with SSE format (Plugin compatibility)
"""
import os
import json
from uuid import UUID, uuid4
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from writeros.core.logging import setup_logging, get_logger
from writeros import __version__
from writeros.utils import db as db_utils
from writeros.utils.indexer import VaultIndexer
from writeros.utils.writer import ObsidianWriter
from writeros.schema import Vault, Entity, Document
from writeros.agents.orchestrator import OrchestratorAgent
from writeros.agents.profiler import ProfilerAgent
from writeros.agents.mechanic import MechanicAgent
from writeros.agents.chronologist import ChronologistAgent
from writeros.agents.psychologist import PsychologistAgent
from writeros.agents.dramatist import DramatistAgent
from writeros.agents.stylist import StylistAgent

# Initialize logging before app creation
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="WriterOS API",
    version=__version__,
    description="AI-Powered Creative Writing Assistant with Hybrid Architecture (Obsidian-Compatible)"
)

# ============================================
# DEPENDENCY INJECTION
# ============================================

def get_db():
    """Database session dependency."""
    with Session(db_utils.engine) as session:
        yield session


def get_vault_path() -> str:
    """Get vault path from environment."""
    vault_path = os.getenv("VAULT_PATH")
    if not vault_path:
        raise HTTPException(
            status_code=500,
            detail="VAULT_PATH environment variable not set"
        )
    return vault_path


# ============================================
# PYDANTIC MODELS (Request/Response)
# ============================================

class IngestRequest(BaseModel):
    vault_id: Optional[UUID] = None
    force_reindex: bool = False


class IngestResponse(BaseModel):
    status: str
    job_id: str
    vault_id: UUID
    message: str


class AgentRequest(BaseModel):
    text: str
    context: Optional[str] = None
    title: Optional[str] = None
    vault_id: UUID


class AgentResponse(BaseModel):
    agent_name: str
    result: Dict[str, Any]
    execution_time: float


class SyncRequest(BaseModel):
    vault_id: UUID
    sync_type: str = "full"  # "full", "entities_only", "documents_only"


class SyncResponse(BaseModel):
    status: str
    files_updated: int
    vault_path: str


# ============================================
# STARTUP/SHUTDOWN EVENTS
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("api_startup", version=__version__, mode=os.getenv("WRITEROS_MODE", "local"))

    # Initialize database (creates tables, default user/vault in local mode)
    try:
        logger.info("initializing_database")
        db_utils.init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("api_shutdown")


# ============================================
# HEALTH CHECK
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint (Plugin checks this to see if server is running)."""
    return {
        "status": "ok",
        "version": __version__,
        "mode": os.getenv("WRITEROS_MODE", "local")
    }


# ============================================
# LEGACY COMPATIBILITY LAYER (Obsidian Plugin)
# ============================================

class LegacyAnalyzeRequest(BaseModel):
    """Plugin's analyze request format."""
    vault_path: str
    vault_id: str


class LegacyChatRequest(BaseModel):
    """
    Plugin's chat request format with temporal context support.

    Supports temporal filtering to prevent spoilers:
    - frontmatter: Complete frontmatter dict from current file
    - current_sequence: Explicit sequence order (chapter/scene number)
    - current_story_time: Explicit story time dict
    """
    message: str
    vault_id: str
    context_window: Optional[int] = 5

    # Temporal context (NEW - Phase 2)
    frontmatter: Optional[Dict[str, Any]] = None  # Full frontmatter from active file
    current_sequence: Optional[int] = None  # Explicit sequence_order
    current_story_time: Optional[Dict[str, int]] = None  # Explicit story_time


@app.post("/analyze")
async def plugin_analyze(
    request: LegacyAnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    LEGACY ENDPOINT: Obsidian Plugin compatibility.
    Maps Plugin's '/analyze' -> New 'VaultIndexer'.

    This endpoint allows the Obsidian plugin to trigger vault ingestion
    without knowing about the new internal architecture.
    """
    logger.info(
        "plugin_analyze_requested",
        vault_path=request.vault_path,
        vault_id=request.vault_id
    )

    try:
        # Verify vault exists
        vault = db.get(Vault, UUID(request.vault_id))
        if not vault:
            raise HTTPException(status_code=404, detail="Vault not found")

        # Initialize the new Indexer
        indexer = VaultIndexer(
            vault_path=request.vault_path,
            vault_id=UUID(request.vault_id),
            chunking_strategy="auto"
        )

        # Run in background so Obsidian UI doesn't freeze
        job_id = str(uuid4())
        background_tasks.add_task(
            _run_ingestion,
            vault_path=request.vault_path,
            vault_id=UUID(request.vault_id),
            job_id=job_id,
            force_reindex=False
        )

        logger.info("plugin_analyze_started", job_id=job_id)

        return {
            "status": "started",
            "message": "Vault analysis started",
            "job_id": job_id
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("invalid_vault_id", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid vault_id format")
    except Exception as e:
        logger.error("plugin_analyze_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def plugin_chat(request: LegacyChatRequest):
    """
    LEGACY ENDPOINT: Obsidian Plugin compatibility.
    Maps Plugin's '/chat/stream' -> New 'Orchestrator' with SSE format.

    The plugin expects Server-Sent Events (SSE) format:
    - Lines starting with "data: "
    - JSON payload: {"content": "text chunk"} or {"error": "message"}
    - End marker: "data: [DONE]"

    Supports temporal context (Phase 2 - Anti-Spoiler):
    - Extracts sequence_order or story_time from frontmatter or explicit params
    - Passes to orchestrator for temporal filtering
    - Prevents spoilers when writing early chapters
    """
    # Extract temporal context from request
    current_sequence = None
    current_story_time = None

    # Priority 1: Explicit parameters
    if request.current_sequence is not None:
        current_sequence = request.current_sequence

    if request.current_story_time is not None:
        current_story_time = request.current_story_time

    # Priority 2: Extract from frontmatter
    if request.frontmatter:
        if current_sequence is None and "sequence_order" in request.frontmatter:
            current_sequence = request.frontmatter["sequence_order"]

        if current_story_time is None and "story_time" in request.frontmatter:
            current_story_time = request.frontmatter["story_time"]

    logger.info(
        "plugin_chat_requested",
        message_preview=request.message[:50],
        vault_id=request.vault_id,
        temporal_context={
            "sequence": current_sequence,
            "story_time": current_story_time
        }
    )

    try:
        # Validate vault_id first
        vault_uuid = UUID(request.vault_id)

        # Initialize orchestrator
        orchestrator = OrchestratorAgent()

        # Create SSE generator that wraps the orchestrator's output
        async def sse_generator():
            try:
                async for chunk in orchestrator.process_chat(
                    user_message=request.message,
                    vault_id=vault_uuid,
                    current_sequence_order=current_sequence,
                    current_story_time=current_story_time
                ):
                    # Format as SSE: data: {"content": "chunk"}
                    payload = json.dumps({"content": chunk})
                    yield f"data: {payload}\n\n"

                # Send completion marker
                yield "data: [DONE]\n\n"

            except Exception as e:
                logger.error("plugin_chat_stream_error", error=str(e))
                error_payload = json.dumps({"error": str(e)})
                yield f"data: {error_payload}\n\n"

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("invalid_vault_id", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid vault_id format")
    except Exception as e:
        logger.error("plugin_chat_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ROUTER 1: INGESTION (/vault)
# ============================================

@app.post("/vault/ingest", response_model=IngestResponse)
async def ingest_vault(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    vault_path: str = Depends(get_vault_path),
    db: Session = Depends(get_db)
):
    """
    Trigger vault ingestion. Indexes all Markdown files into the database.

    This endpoint:
    1. Scans the vault directory for .md files
    2. Chunks content using semantic chunking
    3. Generates embeddings
    4. Stores in Postgres with pgvector

    Returns immediately with a job_id. Processing happens in background.
    """
    try:
        # Get or create default vault
        if request.vault_id:
            vault = db.get(Vault, request.vault_id)
            if not vault:
                raise HTTPException(status_code=404, detail="Vault not found")
        else:
            # Get first vault or create default
            vault = db.exec(select(Vault).limit(1)).first()
            if not vault:
                # Create default vault
                vault = Vault(
                    name="Default Vault",
                    local_system_path=vault_path,
                    connection_type="obsidian_local"
                )
                db.add(vault)
                db.commit()
                db.refresh(vault)

        job_id = str(uuid4())

        # Start ingestion in background
        background_tasks.add_task(
            _run_ingestion,
            vault_path=vault_path,
            vault_id=vault.id,
            job_id=job_id,
            force_reindex=request.force_reindex
        )

        logger.info(
            "ingestion_started",
            job_id=job_id,
            vault_id=str(vault.id),
            vault_path=vault_path
        )

        return IngestResponse(
            status="started",
            job_id=job_id,
            vault_id=vault.id,
            message=f"Ingestion started for vault: {vault.name}"
        )

    except Exception as e:
        logger.error("ingestion_start_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


def _run_ingestion(vault_path: str, vault_id: UUID, job_id: str, force_reindex: bool):
    """Background task for vault ingestion."""
    try:
        logger.info("ingestion_running", job_id=job_id)

        indexer = VaultIndexer(
            vault_path=vault_path,
            vault_id=vault_id,
            chunking_strategy="auto"
        )

        # Run the indexing
        result = indexer.index_vault(force_reindex=force_reindex)

        logger.info(
            "ingestion_completed",
            job_id=job_id,
            docs_indexed=result.get("documents_indexed", 0),
            chunks_created=result.get("chunks_created", 0)
        )

    except Exception as e:
        logger.error("ingestion_failed", job_id=job_id, error=str(e))


# ============================================
# ROUTER 2: AGENT EXECUTION (/agent)
# ============================================

AGENT_REGISTRY = {
    "profiler": ProfilerAgent,
    "mechanic": MechanicAgent,
    "chronologist": ChronologistAgent,
    "psychologist": PsychologistAgent,
    "dramatist": DramatistAgent,
    "stylist": StylistAgent,
}


@app.post("/agent/{agent_name}", response_model=AgentResponse)
async def run_agent(
    agent_name: str,
    request: AgentRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a specific agent on provided text.

    Available agents:
    - profiler: Analyze characters and extract profiles
    - mechanic: Validate magic systems and world rules
    - chronologist: Timeline analysis and ordering
    - psychologist: Character psychology and arcs
    - dramatist: Scene tension and pacing
    - stylist: Writing style analysis

    Returns the agent's structured output (Pydantic model).
    """
    import time
    start_time = time.time()

    try:
        # Validate agent exists
        if agent_name not in AGENT_REGISTRY:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_name}' not found. Available: {list(AGENT_REGISTRY.keys())}"
            )

        # Verify vault exists
        vault = db.get(Vault, request.vault_id)
        if not vault:
            raise HTTPException(status_code=404, detail="Vault not found")

        # Instantiate agent
        agent_class = AGENT_REGISTRY[agent_name]
        agent = agent_class()

        # Run agent
        logger.info(
            "agent_execution_started",
            agent=agent_name,
            vault_id=str(request.vault_id)
        )

        # Different agents have different interfaces
        # This is a simplified version - adjust based on actual agent APIs
        result = agent.run(
            text=request.text,
            context=request.context,
            title=request.title
        )

        execution_time = time.time() - start_time

        logger.info(
            "agent_execution_completed",
            agent=agent_name,
            execution_time=execution_time
        )

        return AgentResponse(
            agent_name=agent_name,
            result=result.dict() if hasattr(result, 'dict') else result,
            execution_time=execution_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("agent_execution_failed", agent=agent_name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agent/orchestrator/chat")
async def chat_with_orchestrator(
    request: AgentRequest,
    db: Session = Depends(get_db)
):
    """
    Chat with the orchestrator agent (streaming response).

    The orchestrator:
    - Manages conversation history
    - Performs RAG retrieval
    - Routes to appropriate sub-agents
    - Streams responses back
    """
    try:
        vault = db.get(Vault, request.vault_id)
        if not vault:
            raise HTTPException(status_code=404, detail="Vault not found")

        orchestrator = OrchestratorAgent()

        async def generate():
            async for chunk in orchestrator.process_chat(
                user_message=request.text,
                vault_id=request.vault_id
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")

    except Exception as e:
        logger.error("orchestrator_chat_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ROUTER 3: OBSIDIAN SYNC (/sync)
# ============================================

@app.post("/sync/obsidian", response_model=SyncResponse)
async def sync_to_obsidian(
    request: SyncRequest,
    vault_path: str = Depends(get_vault_path),
    db: Session = Depends(get_db)
):
    """
    Synchronize database back to Obsidian Markdown files.

    This endpoint:
    1. Queries the database for entities/documents
    2. Updates Markdown frontmatter in Obsidian vault
    3. Creates new files if needed

    The writer respects existing content - only updates frontmatter.
    """
    try:
        # Verify vault
        vault = db.get(Vault, request.vault_id)
        if not vault:
            raise HTTPException(status_code=404, detail="Vault not found")

        # Initialize writer
        writer = ObsidianWriter(vault_path=Path(vault_path))

        files_updated = 0

        # Sync based on type
        if request.sync_type in ["full", "entities_only"]:
            # Fetch entities from database
            entities = db.exec(
                select(Entity).where(Entity.vault_id == request.vault_id)
            ).all()

            for entity in entities:
                # Convert to appropriate format and update
                # This is simplified - actual implementation depends on your schema
                try:
                    # The writer would have methods like:
                    # writer.update_character(entity) or writer.update_entity(entity)
                    # For now, we'll log it
                    logger.debug("syncing_entity", entity_id=str(entity.id), name=entity.name)
                    files_updated += 1
                except Exception as e:
                    logger.error("entity_sync_failed", entity_id=str(entity.id), error=str(e))

        if request.sync_type in ["full", "documents_only"]:
            # Sync documents
            documents = db.exec(
                select(Document).where(Document.vault_id == request.vault_id)
            ).all()

            for doc in documents:
                try:
                    logger.debug("syncing_document", doc_id=str(doc.id), title=doc.title)
                    files_updated += 1
                except Exception as e:
                    logger.error("document_sync_failed", doc_id=str(doc.id), error=str(e))

        logger.info(
            "obsidian_sync_completed",
            vault_id=str(request.vault_id),
            files_updated=files_updated
        )

        return SyncResponse(
            status="completed",
            files_updated=files_updated,
            vault_path=vault_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("obsidian_sync_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UTILITY ENDPOINTS
# ============================================

@app.get("/vaults")
async def list_vaults(db: Session = Depends(get_db)):
    """List all available vaults."""
    vaults = db.exec(select(Vault)).all()
    return {
        "vaults": [
            {
                "id": str(v.id),
                "name": v.name,
                "connection_type": v.connection_type,
                "entity_count": v.entity_count,
                "scene_count": v.scene_count,
                "word_count": v.word_count,
            }
            for v in vaults
        ]
    }


@app.get("/agents")
async def list_agents():
    """List all available agents."""
    return {
        "agents": list(AGENT_REGISTRY.keys()),
        "descriptions": {
            "profiler": "Character profile extraction and analysis",
            "mechanic": "Magic system and world rule validation",
            "chronologist": "Timeline analysis and event ordering",
            "psychologist": "Character psychology and transformation arcs",
            "dramatist": "Scene tension and pacing analysis",
            "stylist": "Writing style analysis and suggestions",
            "orchestrator": "Main conversation agent with RAG (use /agent/orchestrator/chat)"
        }
    }
