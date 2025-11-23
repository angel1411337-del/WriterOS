"""
WriterOS API Server
FastAPI server for handling chat, RAG, and vault analysis.
"""
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
import json
import asyncio

from agents.orchestrator import OrchestratorAgent
from utils.indexer import VaultIndexer
from utils.db import init_db

app = FastAPI(title="WriterOS API")

# Global Agent Instance (Lazy loaded)
orchestrator: Optional[OrchestratorAgent] = None

class ChatRequest(BaseModel):
    message: str
    vault_id: UUID
    conversation_id: Optional[UUID] = None

class AnalyzeRequest(BaseModel):
    vault_path: str
    vault_id: UUID

@app.on_event("startup")
async def startup_event():
    global orchestrator
    print("Initializing Database...")
    init_db()
    print("Loading Orchestrator Agent...")
    orchestrator = OrchestratorAgent()
    print("WriterOS Server Ready!")

@app.get("/health")
async def health_check():
    """
    Health check endpoint for Obsidian plugin discovery.
    """
    return {
        "status": "ok", 
        "agents_loaded": orchestrator is not None,
        "service": "writeros"
    }

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat response using Server-Sent Events (SSE).
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Agents not initialized")

    async def generate():
        try:
            async for chunk in orchestrator.process_chat(
                user_message=request.message,
                vault_id=request.vault_id,
                conversation_id=request.conversation_id
            ):
                # SSE format: data: <json>\n\n
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )

@app.post("/analyze")
async def analyze_vault(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Trigger vault indexing in background.
    """
    indexer = VaultIndexer(
        vault_path=request.vault_path,
        vault_id=request.vault_id
    )
    
    # Run indexing in background
    background_tasks.add_task(indexer.index_vault)
    
    return {"status": "accepted", "message": "Vault analysis started in background"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)