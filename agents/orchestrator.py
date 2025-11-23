"""
Orchestrator Agent
Routes user requests, manages RAG context, and maintains conversation history.
"""
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import Session, select, desc
from sqlalchemy import func

from src.writeros.schema import Conversation, Message, Document, Entity
from agents.profiler import ProfilerAgent
from agents.dramatist import DramatistAgent
from agents.base import BaseAgent
from utils.embeddings import EmbeddingService
from utils.db import engine

class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_name="gpt-5.1")
        self.embedder = EmbeddingService()
        
        # Sub-agents
        self.profiler = ProfilerAgent()
        self.dramatist = DramatistAgent()

    async def process_chat(
        self, 
        user_message: str, 
        vault_id: UUID, 
        conversation_id: Optional[UUID] = None
    ) -> AsyncGenerator[str, None]:
        """
        Main entry point for chat. Streams the response.
        """
        # 1. Manage Conversation
        if not conversation_id:
            conversation_id = self._create_conversation(vault_id, user_message)
        
        # 2. RAG Retrieval
        context = await self._retrieve_context(user_message, vault_id)
        
        # 3. Route to Agent (Simple keyword routing for now)
        agent = self._select_agent(user_message)
        
        # 4. Save User Message
        self._save_message(conversation_id, "user", user_message)
        
        # 5. Generate Response (Streaming)
        full_response = ""
        
        # Construct Prompt
        system_prompt = self._build_system_prompt(agent, context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Stream from LLM
        async for chunk in self.llm.stream_chat(messages):
            full_response += chunk
            yield chunk
            
        # 6. Save Assistant Message
        self._save_message(
            conversation_id, 
            "assistant", 
            full_response, 
            agent=agent.agent_name,
            context_used=self._serialize_context(context)
        )

    def _create_conversation(self, vault_id: UUID, first_message: str) -> UUID:
        with Session(engine) as session:
            title = first_message[:50] + "..."
            conv = Conversation(vault_id=vault_id, title=title)
            session.add(conv)
            session.commit()
            session.refresh(conv)
            return conv.id

    def _save_message(self, conversation_id: UUID, role: str, content: str, agent: str = None, context_used: Dict = None):
        with Session(engine) as session:
            msg = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                agent=agent,
                context_used=context_used or {}
            )
            session.add(msg)
            session.commit()

    async def _retrieve_context(self, query: str, vault_id: UUID) -> Dict[str, List[Any]]:
        """
        Retrieve relevant documents and entities using vector search.
        """
        query_embedding = await self.embedder.get_embedding(query)
        
        with Session(engine) as session:
            # Search Documents
            doc_stmt = select(Document).where(Document.vault_id == vault_id).order_by(
                Document.embedding.l2_distance(query_embedding)
            ).limit(5)
            docs = session.exec(doc_stmt).all()
            
            # Search Entities
            ent_stmt = select(Entity).where(Entity.vault_id == vault_id).order_by(
                Entity.embedding.l2_distance(query_embedding)
            ).limit(5)
            entities = session.exec(ent_stmt).all()
            
            return {
                "documents": docs,
                "entities": entities
            }

    def _select_agent(self, message: str) -> BaseAgent:
        msg_lower = message.lower()
        if "character" in msg_lower or "profile" in msg_lower or "personality" in msg_lower:
            return self.profiler
        elif "plot" in msg_lower or "scene" in msg_lower or "story" in msg_lower:
            return self.dramatist
        else:
            return self # Default to Orchestrator (general chat)

    def _build_system_prompt(self, agent: BaseAgent, context: Dict[str, List[Any]]) -> str:
        docs_text = "\n".join([f"- {d.content}" for d in context['documents']])
        ents_text = "\n".join([f"- {e.name}: {e.description}" for e in context['entities']])
        
        base_prompt = f"""You are {agent.agent_name}, an AI assistant for creative writing.
        
        CONTEXT FROM VAULT:
        Documents:
        {docs_text}
        
        Entities:
        {ents_text}
        
        Use this context to answer the user's request. If the answer is not in the context, use your general knowledge but mention that it's not in the vault.
        """
        return base_prompt

    def _serialize_context(self, context: Dict[str, List[Any]]) -> Dict[str, Any]:
        return {
            "documents": [str(d.id) for d in context['documents']],
            "entities": [str(e.id) for e in context['entities']]
        }
