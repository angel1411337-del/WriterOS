import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from dotenv import load_dotenv

from agents import AgentSwarm
from utils.vault_reader import VaultRegistry
from utils.writer import ObsidianWriter

load_dotenv()
app = FastAPI(title="WriterOS v3.0 API")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", "./output"))
swarm = None
vault = None
writer = None

# --- Models ---
class ChapterDraft(BaseModel):
    text: str
    chapter_title: Optional[str] = "Untitled"

class CritiqueResponse(BaseModel):
    critique: str
    context_used: List[str]

class UpdateResponse(BaseModel):
    status: str
    updates_made: List[str]

class ProducerQuery(BaseModel):
    query: str
    mode: str = "local" # local, global, drift, sql, traversal
    # Optional params for advanced modes
    sql_params: Optional[Dict[str, str]] = None
    traversal_nodes: Optional[List[str]] = None

# --- Lifecycle ---
@app.on_event("startup")
async def startup_event():
    global swarm, vault, writer
    print("🚀 WriterOS Server Starting...")

    swarm = AgentSwarm()
    print("🤖 Swarm Active.")

    vault = VaultRegistry(str(VAULT_PATH))
    print("🧠 Super Fan Context Loaded.")

    writer = ObsidianWriter(VAULT_PATH)
    print("✍️ Obsidian Writer Ready.")

@app.get("/")
def health_check():
    return {"status": "WriterOS is online", "phase": "Execution Mode"}

@app.post("/refresh")
async def refresh_vault():
    vault.refresh_index()
    return {"status": "Vault Index Refreshed"}

# --- ENDPOINT 1: ARCHITECT (Story/Plot) ---
@app.post("/analyze/chapter", response_model=CritiqueResponse)
async def analyze_chapter(draft: ChapterDraft):
    if not swarm or not vault: raise HTTPException(503, "Initializing...")

    context_str = vault.get_relevant_context(draft.text)
    result = await swarm.architect.critique_draft(draft.text, context_str)

    return {
        "critique": result,
        "context_used": list(vault.entities.keys())
    }

# --- ENDPOINT 2: STYLIST (Prose/Line Edit) ---
@app.post("/analyze/style", response_model=CritiqueResponse)
async def analyze_style(draft: ChapterDraft):
    if not swarm: raise HTTPException(503, "Initializing...")

    craft_str = vault.get_craft_context()
    result = await swarm.stylist.critique_prose(draft.text, craft_str)

    return {
        "critique": result,
        "context_used": []
    }

# --- ENDPOINT 3: STATE UPDATER (Chapter Digester) ---
@app.post("/update/state", response_model=UpdateResponse)
async def update_state(draft: ChapterDraft):
    if not swarm or not writer: raise HTTPException(503, "Initializing...")

    print(f"🔄 Processing State Update for: {draft.chapter_title}")
    updates = []

    context_str = vault.get_relevant_context(draft.text)

    # 1. Run Profiler
    try:
        lore_data = await swarm.profiler.run(draft.text, context_str, draft.chapter_title)
        if lore_data:
            writer.update_story_bible(lore_data, draft.chapter_title)
            updates.append(f"Profiler: Extracted {len(lore_data.characters)} characters")
    except Exception as e:
        print(f"❌ Profiler Error: {e}")

    # 2. Run Navigator
    try:
        nav_data = await swarm.navigator.run(draft.text, context_str, draft.chapter_title)
        if nav_data:
            writer.update_navigation_data(nav_data, draft.chapter_title)
            updates.append(f"Navigator: Extracted {len(nav_data.locations)} locations")
    except Exception as e:
        print(f"❌ Navigator Error: {e}")

    # 3. Run Psychologist
    try:
        psych_data = await swarm.psychologist.run(draft.text, context_str, draft.chapter_title)
        if psych_data:
            writer.update_psych_profiles(psych_data)
            updates.append(f"Psychologist: Analyzed {len(psych_data.profiles)} profiles")
    except Exception as e:
        print(f"❌ Psychologist Error: {e}")

    vault.refresh_index()

    return {
        "status": "Success",
        "updates_made": updates
    }

# --- ENDPOINT 4: PRODUCER (Chat/Drift/SQL) ---
@app.post("/consult/producer")
async def consult_producer(request: ProducerQuery):
    if not swarm: raise HTTPException(503, "Initializing...")

    response = ""

    if request.mode == "sql":
        if not request.sql_params: return {"response": "Error: Missing sql_params"}
        response = await swarm.producer.structured_query(request.sql_params, vault)

    elif request.mode == "traversal":
        if not request.traversal_nodes or len(request.traversal_nodes) != 2:
            return {"response": "Error: Traversal requires [start, end]."}
        response = await swarm.producer.agentic_traversal(
            request.traversal_nodes[0], request.traversal_nodes[1], vault
        )

    elif request.mode == "global":
        context = vault.get_global_context()
        response = await swarm.producer.global_view(request.query, context)

    elif request.mode == "drift":
        context = vault.get_local_context(request.query)
        response = await swarm.producer.drift_search(request.query, context)

    else:
        # Standard Chat
        context = vault.get_local_context(request.query)
        response = await swarm.producer.consult(request.query, context)

    return {"response": response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)