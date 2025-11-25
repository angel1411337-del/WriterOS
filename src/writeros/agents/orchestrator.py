"""
Orchestrator Agent
Routes user requests, manages RAG context, and maintains conversation history.
Supports OpenAI Function Calling for write-back operations (creating/editing files).
"""
import json
import os
from typing import List, Dict, Any, Optional, AsyncGenerator
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import Session, select, desc
from sqlalchemy import func

from writeros.schema import Conversation, Message, Document, Entity
from writeros.agents.profiler import ProfilerAgent
from writeros.agents.dramatist import DramatistAgent
from writeros.agents.base import BaseAgent
from writeros.agents.tools_registry import ToolRegistry
from writeros.utils.embeddings import get_embedding_service
from writeros.utils.db import engine

class OrchestratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_name="gpt-5.1")
        self.embedder = get_embedding_service()

        # Sub-agents
        self.profiler = ProfilerAgent()
        self.dramatist = DramatistAgent()

        # Tool Registry for function calling (write-back capability)
        vault_path = os.getenv("VAULT_PATH")
        if vault_path:
            self.tools = ToolRegistry(vault_path=vault_path)
            self.log.info("tools_registry_initialized", vault_path=vault_path)
        else:
            self.tools = None
            self.log.warning("tools_registry_disabled", reason="VAULT_PATH not set")

    async def process_chat(
        self,
        user_message: str,
        vault_id: UUID,
        conversation_id: Optional[UUID] = None,
        current_sequence_order: Optional[int] = None,
        current_story_time: Optional[Dict[str, int]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Main entry point for chat. Streams the response.
        Supports OpenAI Function Calling for write-back operations.
        Supports temporal filtering to prevent spoilers (Phase 2).

        Args:
            user_message: The user's chat message
            vault_id: Vault ID for context retrieval
            conversation_id: Optional existing conversation ID
            current_sequence_order: Current chapter/scene for temporal filtering
            current_story_time: Current in-universe time for temporal filtering
        """
        # 1. Manage Conversation
        if not conversation_id:
            conversation_id = self._create_conversation(vault_id, user_message)

        # 2. RAG Retrieval with Temporal Context
        context = await self._retrieve_context(
            user_message,
            vault_id,
            current_sequence_order=current_sequence_order,
            current_story_time=current_story_time
        )

        # 3. Route to Agent (Simple keyword routing for now)
        agent = self._select_agent(user_message)

        # 4. Save User Message
        self._save_message(conversation_id, "user", user_message)

        # 5. Generate Response (Streaming with Tool Calling support)
        full_response = ""
        tool_calls_executed = []

        # Construct Prompt
        system_prompt = self._build_system_prompt(agent, context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Enable tools if available
        tools = self.tools.get_tool_schemas() if self.tools else None

        # Stream from LLM with tool support
        async for chunk in self.llm.stream_chat(messages, tools=tools):
            # Check if chunk contains a tool call
            if isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                # Execute tool
                tool_result = await self._execute_tool_call(chunk)
                tool_calls_executed.append(tool_result)

                # Yield tool execution feedback to user
                yield f"\n[Tool: {chunk['name']}] {tool_result['message']}\n"

                # Add tool result to messages for continued conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": chunk.get("id", ""),
                    "content": json.dumps(tool_result)
                })

                # Continue conversation with tool result
                async for response_chunk in self.llm.stream_chat(messages, tools=tools):
                    if isinstance(response_chunk, str):
                        full_response += response_chunk
                        yield response_chunk
            else:
                # Regular text chunk
                full_response += chunk
                yield chunk

        # 6. Save Assistant Message with tool execution metadata
        self._save_message(
            conversation_id,
            "assistant",
            full_response,
            agent=agent.agent_name,
            context_used={
                **self._serialize_context(context),
                "tool_calls": tool_calls_executed
            }
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

    async def _retrieve_context(
        self,
        query: str,
        vault_id: UUID,
        current_sequence_order: Optional[int] = None,
        current_story_time: Optional[Dict[str, int]] = None
    ) -> Dict[str, List[Any]]:
        """
        Retrieve relevant documents and entities using vector search.
        Supports temporal filtering to prevent spoilers.

        Args:
            query: The search query
            vault_id: Vault ID to filter results
            current_sequence_order: Current chapter/scene number for temporal filtering
            current_story_time: Current story time for temporal filtering

        Returns:
            Dict with documents and entities
        """
        query_embedding = self.embedder.embed_query(query)

        # Determine temporal mode
        temporal_mode = "god"  # Default: no filtering
        max_sequence_order = None
        max_story_time = None

        if current_sequence_order is not None:
            temporal_mode = "sequence"
            max_sequence_order = current_sequence_order
            self.log.info(
                "temporal_context_extracted",
                mode="sequence",
                max_sequence=current_sequence_order
            )
        elif current_story_time is not None:
            temporal_mode = "story_time"
            max_story_time = current_story_time
            self.log.info(
                "temporal_context_extracted",
                mode="story_time",
                max_story_time=current_story_time
            )

        with Session(engine) as session:
            # Search Documents (no temporal filtering for documents)
            doc_stmt = select(Document).where(Document.vault_id == vault_id).order_by(
                Document.embedding.l2_distance(query_embedding)
            ).limit(5)
            docs = session.exec(doc_stmt).all()

            # Search Entities (no temporal filtering for entities)
            ent_stmt = select(Entity).where(Entity.vault_id == vault_id).order_by(
                Entity.embedding.l2_distance(query_embedding)
            ).limit(5)
            entities = session.exec(ent_stmt).all()

            return {
                "documents": docs,
                "entities": entities,
                "temporal_context": {
                    "mode": temporal_mode,
                    "max_sequence_order": max_sequence_order,
                    "max_story_time": max_story_time
                }
            }

    def _select_agent(self, message: str) -> BaseAgent:
        msg_lower = message.lower()
        selected_agent = self
        
        if "character" in msg_lower or "profile" in msg_lower or "personality" in msg_lower:
            selected_agent = self.profiler
        elif "plot" in msg_lower or "scene" in msg_lower or "story" in msg_lower:
            selected_agent = self.dramatist
            
        self.log.info("agent_selected", message_snippet=message[:20], selected_agent=selected_agent.__class__.__name__)
        return selected_agent

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

        # Add tool capability information if tools are available
        if self.tools:
            base_prompt += """

        TOOL CAPABILITIES:
        You have access to tools that allow you to CREATE and EDIT files in the user's vault.

        When the user asks you to:
        - "Create a character file for X"
        - "Make a location file for Y"
        - "Update character Z with new traits"
        - "Document the relationship between A and B"

        You should USE THE AVAILABLE TOOLS to actually perform these actions instead of just describing what should be done.

        IMPORTANT:
        - Always search for existing files before creating new ones (use search_vault tool)
        - When creating files, use descriptive names and comprehensive content
        - After creating/updating a file, confirm the action to the user
        - If unsure about a destructive operation, ask the user for confirmation first
        """

        return base_prompt

    def _serialize_context(self, context: Dict[str, List[Any]]) -> Dict[str, Any]:
        return {
            "documents": [str(d.id) for d in context['documents']],
            "entities": [str(e.id) for e in context['entities']]
        }

    async def _execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call from the LLM.

        Args:
            tool_call: Dict with 'name' and 'arguments'

        Returns:
            Dict with execution result
        """
        if not self.tools:
            return {
                "success": False,
                "message": "Tool registry not initialized (VAULT_PATH not set)"
            }

        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})

        # Parse arguments if they're JSON string
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "message": f"Invalid JSON arguments for tool {tool_name}"
                }

        self.log.info("executing_tool", tool_name=tool_name, arguments=arguments)

        try:
            result = self.tools.execute_tool(tool_name, arguments)
            self.log.info("tool_executed", tool_name=tool_name, success=result.get("success"))
            return result
        except Exception as e:
            self.log.error("tool_execution_failed", tool_name=tool_name, error=str(e))
            return {
                "success": False,
                "message": f"Tool execution failed: {str(e)}"
            }
