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
from writeros.schema.provenance import ContentDependency
from writeros.schema.agent_execution import ExecutionStage, AgentCitation
from writeros.rag.retriever import RAGRetriever
from writeros.agents.profiler import ProfilerAgent
from writeros.agents.dramatist import DramatistAgent
from writeros.agents.architect import ArchitectAgent
from writeros.agents.chronologist import ChronologistAgent
from writeros.agents.mechanic import MechanicAgent
from writeros.agents.navigator import NavigatorAgent
from writeros.agents.producer import ProducerAgent
from writeros.agents.psychologist import PsychologistAgent
from writeros.agents.stylist import StylistAgent
from writeros.agents.theorist import TheoristAgent
from writeros.agents.base import BaseAgent
from writeros.agents.tools_registry import ToolRegistry
from writeros.utils.embeddings import get_embedding_service
from writeros.utils.db import engine
from writeros.services.provenance import ProvenanceService
from pydantic import BaseModel

class OrchestratorAgent(BaseAgent):
    def __init__(self, enable_tracking=True):
        super().__init__(model_name="gpt-5.1", enable_tracking=enable_tracking)
        self.embedder = get_embedding_service()
        self.retriever = RAGRetriever()

        # Sub-agents
        self.profiler = ProfilerAgent()
        self.dramatist = DramatistAgent()
        self.architect = ArchitectAgent()
        self.chronologist = ChronologistAgent()
        self.mechanic = MechanicAgent()
        self.navigator = NavigatorAgent()
        self.producer = ProducerAgent()
        self.psychologist = PsychologistAgent()
        self.stylist = StylistAgent()
        self.theorist = TheoristAgent()

        # Tool Registry for function calling (write-back capability)
        vault_path = os.getenv("VAULT_PATH")
        if vault_path:
            self.tools = ToolRegistry(vault_path=vault_path)
            self.log.info("tools_registry_initialized", vault_path=vault_path)
        else:
            self.tools = None
            self.log.warning("tools_registry_disabled", reason="VAULT_PATH not set")
            
        # Agent registry for broadcast
        self.agents = {
            "architect": self.architect,
            "chronologist": self.chronologist,
            "dramatist": self.dramatist,
            "mechanic": self.mechanic,
            "navigator": self.navigator,
            "producer": self.producer,
            "profiler": self.profiler,
            "psychologist": self.psychologist,
            "stylist": self.stylist,
            "theorist": self.theorist
        }

    async def process_chat(
        self,
        user_message: str,
        vault_id: UUID,
        conversation_id: Optional[UUID] = None,
        current_sequence_order: Optional[int] = None,
        current_story_time: Optional[Dict[str, int]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Main entry point for chat.
        Uses Iterative RAG -> Agent Broadcast -> Response Synthesis.
        """
        # Create execution tracker
        tracker = self.create_tracker(vault_id=vault_id, conversation_id=conversation_id)

        async with tracker.track_execution(
            method="process_chat",
            input_data={"user_message": user_message[:500]}  # Truncate for storage
        ):
            # 1. Manage Conversation
            if not conversation_id:
                conversation_id = self._create_conversation(vault_id, user_message)
                tracker.conversation_id = conversation_id  # Update tracker

            # 2. Iterative RAG Retrieval (10 hops)
            await tracker.track_stage(ExecutionStage.PRE_PROCESS, "Starting iterative RAG retrieval")
            self.log.info("starting_iterative_rag", query=user_message)
            rag_result = await self.retriever.retrieve_iterative(
                initial_query=user_message,
                max_hops=10,
                limit_per_hop=3
            )
            await tracker.complete_stage(ExecutionStage.PRE_PROCESS)

            # Log RAG results
            await tracker.log_event(
                f"RAG retrieved {len(rag_result.documents)} docs, {len(rag_result.entities)} entities",
                level="info"
            )

            # Format context for agents
            context_str = self.retriever.format_results(rag_result)

            # 3. Broadcast to Agents (Autonomy Check)
            await tracker.track_stage(ExecutionStage.POST_PROCESS, "Broadcasting to specialized agents")
            agent_results = await self._execute_agents_with_autonomy(
                list(self.agents.keys()),
                user_message,
                context_str
            )
            await tracker.complete_stage(ExecutionStage.POST_PROCESS)

            # Log which agents responded
            responding_agents = [
                name for name, result in agent_results.items()
                if not (isinstance(result, dict) and result.get("skipped"))
            ]
            await tracker.log_event(
                f"{len(responding_agents)} agents responded: {', '.join(responding_agents)}",
                level="info",
                data={"agents": responding_agents}
            )

            # 4. Build Structured Summary FIRST (preserves analytical data)
            await tracker.track_stage(ExecutionStage.COMPLETE, "Building structured output")
            structured_summary = self._build_structured_summary(agent_results)

            # 5. Synthesize Narrative Response
            synthesis = await self._synthesize_response(user_message, agent_results, context_str)
            
            # Extract and log citations
            if tracker.execution_id:
                await self._extract_and_log_citations(synthesis, tracker.execution_id)
                
            await tracker.complete_stage(ExecutionStage.COMPLETE)

            # 6. Save User Message
            self._save_message(conversation_id, "user", user_message)

            # 7. Stream Outputs
            # Yield structured analysis first (if available)
            if structured_summary:
                yield structured_summary
                yield "\n\n"

            # Then yield narrative summary
            yield "## 💬 NARRATIVE SUMMARY\n\n"
            yield synthesis

            # 8. Save Assistant Message (combine both outputs)
            full_response = ""
            if structured_summary:
                full_response += structured_summary + "\n\n"
            full_response += "## 💬 NARRATIVE SUMMARY\n\n" + synthesis

            self._save_message(
                conversation_id,
                "assistant",
                full_response,
                agent="Orchestrator",
                context_used={"rag_stats": f"{len(rag_result.documents)} docs, {len(rag_result.entities)} entities"}
            )

            # Set tracker output
            tracker.set_output({
                "responding_agents": responding_agents,
                "structured_summary_generated": bool(structured_summary),
                "synthesis_length": len(synthesis)
            })

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
        docs_text = "\n".join([f"- [ID: {d.id}] {d.content}" for d in context['documents']])
        ents_text = "\n".join([f"- [ID: {e.id}] {e.name}: {e.description}" for e in context['entities']])

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
    async def _execute_agents_with_autonomy(
        self,
        agent_names: List[str],
        user_message: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Executes agents with autonomy check - agents can opt-out if query is irrelevant.
        """
        import asyncio
        
        # Phase 1: Check agent willingness (in parallel)
        self.log.info("checking_agent_relevance", agent_count=len(agent_names))
        relevance_tasks = []
        valid_agents = []
        
        for name in agent_names:
            agent_key = name.lower()
            if agent_key in self.agents:
                agent = self.agents[agent_key]
                relevance_tasks.append(agent.should_respond(user_message, context))
                valid_agents.append((agent_key, agent))
            else:
                self.log.warning("unknown_agent_requested", agent=agent_key)
        
        # Get all relevance checks
        relevance_results = await asyncio.gather(*relevance_tasks, return_exceptions=True)
        
        # Phase 2: Execute only willing agents
        execution_tasks = []
        active_agents = []
        results = {}
        
        for (agent_key, agent), relevance_result in zip(valid_agents, relevance_results):
            if isinstance(relevance_result, Exception):
                self.log.error("relevance_check_failed", agent=agent_key, error=str(relevance_result))
                should_respond, confidence, reason = (True, 1.0, "Relevance check failed")
            else:
                should_respond, confidence, reason = relevance_result
            
            if should_respond or confidence >= 0.5:
                self.log.info("agent_responding", agent=agent_key, confidence=confidence)
                execution_tasks.append(agent.run(
                    full_text=user_message,
                    existing_notes=context,
                    title="User Query"
                ))
                active_agents.append(agent_key)
            else:
                self.log.info("agent_skipped", agent=agent_key, reason=reason)
                results[agent_key] = {
                    "skipped": True,
                    "confidence": confidence,
                    "reason": reason
                }
        
        if not execution_tasks:
            self.log.warning("no_agents_willing_to_respond")
            return results
        
        # Execute willing agents in parallel
        self.log.info("executing_agents", agent_count=len(active_agents))
        results_list = await asyncio.gather(*execution_tasks, return_exceptions=True)
        
        for agent_key, result in zip(active_agents, results_list):
            if isinstance(result, Exception):
                self.log.error("agent_execution_failed", agent=agent_key, error=str(result))
                results[agent_key] = {"error": str(result)}
            else:
                results[agent_key] = result
                
        return results

    async def _synthesize_response(self, query: str, agent_results: Dict[str, Any], context_str: str = "") -> str:
        """
        Synthesizes multiple agent responses into one coherent natural language answer.
        """
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        
        # Filter to only responding agents (not skipped)
        responding_agents = {
                name: result for name, result in agent_results.items()
                if not (isinstance(result, dict) and result.get("skipped"))
            }
            
        if not responding_agents:
            return "No agents had relevant information for this query."
            
        # Build structured summary
        agent_summaries = []
        for agent_name, result in responding_agents.items():
                summary = f"**{agent_name.capitalize()}**: {str(result)[:500]}"
                agent_summaries.append(summary)
            
        # Synthesis prompt
        synthesis_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are synthesizing multiple expert analyses into one coherent answer.

    Your goal: Provide a natural, conversational response that integrates all expert insights and CITES SOURCES.

    Rules:
    1. Write in 2nd person ("You can...", "This would take...") 
    2. Integrate facts from all agents naturally
    3. If agents contradict, acknowledge both perspectives
    4. If data is missing, state what's needed
    5. Keep it concise (2-3 paragraphs max)
    6. CITATION REQUIREMENT:
       - You have access to the original RAG context below.
       - When you state a fact from the context, you MUST cite it using XML tags: <cite id="UUID" type="document">quote</cite>
       - Use the ID provided in the context.
       - The quote should be a short snippet (3-5 words) verifying the fact.
       - Example: "Jon Snow is a Targaryen <cite id="123-abc" type="document">dragon must have three heads</cite>."
    """),
                ("user", """User Query: {query}

    Original RAG Context:
    {context_str}

    Agent Analyses:
    {agent_summaries}

    Synthesize these into one natural, helpful answer with citations:""")
            ])
            
        chain = synthesis_prompt | self.llm.client | StrOutputParser()
        synthesis = await chain.ainvoke({
            "query": query,
            "agent_summaries": "\n".join(agent_summaries),
            "context_str": context_str
        })
        return synthesis

    def _build_structured_summary(self, agent_results: Dict[str, Any]) -> str:
        """
        Builds a structured summary preserving agent-specific outputs.

        This method extracts systematic metrics from agent responses and formats them
        into a readable structured output that preserves the analytical nature of the data.

        Args:
            agent_results: Dictionary mapping agent names to their outputs

        Returns:
            Formatted string with structured analysis sections
        """
        summary_sections = []

        # Chronologist: Timeline analysis
        if "chronologist" in agent_results:
            chrono = agent_results["chronologist"]
            if isinstance(chrono, BaseModel):
                chrono_dict = chrono.model_dump()
                events = chrono_dict.get("events", [])
                continuity = chrono_dict.get("continuity_notes")

                if events or continuity:
                    section = ["### ⏱️ TIMELINE ANALYSIS"]
                    if events:
                        section.append(f"**Events Identified:** {len(events)}")
                        for i, event in enumerate(events[:5], 1):  # Show first 5
                            section.append(f"{i}. **{event.get('title', 'Event')}** (Order: {event.get('order', 'N/A')})")
                            section.append(f"   {event.get('summary', '')}")
                    if continuity:
                        section.append(f"\n**⚠️ Continuity Notes:** {continuity}")
                    summary_sections.append("\n".join(section))

        # Psychologist: Character analysis
        if "psychologist" in agent_results:
            psych = agent_results["psychologist"]
            if isinstance(psych, BaseModel):
                psych_dict = psych.model_dump()
                profiles = psych_dict.get("profiles", [])

                if profiles:
                    section = ["### 🧠 PSYCHOLOGICAL ANALYSIS"]
                    section.append(f"**Characters Analyzed:** {len(profiles)}")
                    for profile in profiles[:3]:  # Show first 3
                        name = profile.get("name", "Unknown")
                        archetype = profile.get("archetype", "N/A")
                        desire = profile.get("core_desire", "N/A")
                        fear = profile.get("core_fear", "N/A")
                        section.append(f"\n**{name}**")
                        section.append(f"- Archetype: {archetype}")
                        section.append(f"- Core Desire: {desire}")
                        section.append(f"- Core Fear: {fear}")
                    summary_sections.append("\n".join(section))

        # Navigator: Distance/travel calculations
        if "navigator" in agent_results:
            nav = agent_results["navigator"]
            if isinstance(nav, dict):
                if "distance_km" in nav or "travel_time" in nav:
                    section = ["### 🗺️ TRAVEL ANALYSIS"]
                    if "distance_km" in nav:
                        section.append(f"**Distance:** {nav['distance_km']} km")
                    if "travel_time" in nav:
                        section.append(f"**Travel Time:** {nav['travel_time']}")
                    if "method" in nav:
                        section.append(f"**Method:** {nav['method']}")
                    summary_sections.append("\n".join(section))

        # Architect: Plot structure analysis
        if "architect" in agent_results:
            arch = agent_results["architect"]
            if isinstance(arch, dict):
                if "chapters_affected" in arch or "plot_conflicts" in arch:
                    section = ["### 🏛️ STRUCTURAL ANALYSIS"]
                    if "chapters_affected" in arch:
                        chapters = arch["chapters_affected"]
                        section.append(f"**Chapters Affected:** {', '.join(map(str, chapters)) if isinstance(chapters, list) else chapters}")
                    if "plot_conflicts" in arch:
                        conflicts = arch["plot_conflicts"]
                        if isinstance(conflicts, list) and conflicts:
                            section.append(f"\n**⚠️ Plot Conflicts Detected:** {len(conflicts)}")
                            for i, conflict in enumerate(conflicts[:3], 1):
                                section.append(f"{i}. {conflict}")
                    summary_sections.append("\n".join(section))

        # Mechanic: World-building consistency
        if "mechanic" in agent_results:
            mech = agent_results["mechanic"]
            if isinstance(mech, BaseModel):
                mech_dict = mech.model_dump()
                if "violations" in mech_dict or "rules" in mech_dict:
                    section = ["### ⚙️ WORLD-BUILDING ANALYSIS"]
                    violations = mech_dict.get("violations", [])
                    if violations:
                        section.append(f"**⚠️ Consistency Violations:** {len(violations)}")
                        for i, v in enumerate(violations[:3], 1):
                            section.append(f"{i}. {v}")
                    summary_sections.append("\n".join(section))

        if not summary_sections:
            return ""

        # Add header
        header = "## 📊 SYSTEMATIC ANALYSIS\n"
        return header + "\n\n".join(summary_sections)

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

    async def _extract_and_log_citations(self, response: str, execution_id: UUID):
        """
        Parses <cite> tags from response and saves them to AgentCitation table.
        """
        import re
        from writeros.schema.agent_execution import AgentCitation
        
        # Regex to find <cite id="..." type="...">quote</cite>
        # Handles attributes in any order and optional quotes
        pattern = r'<cite\s+id="([^"]+)"\s+type="([^"]+)">([^<]+)</cite>'
        matches = re.findall(pattern, response)
        
        if not matches:
            return
            
        self.log.info("citations_found", count=len(matches), execution_id=str(execution_id))
        
        with Session(engine) as session:
            for source_id, source_type, quote in matches:
                try:
                    citation = AgentCitation(
                        execution_id=execution_id,
                        source_id=UUID(source_id),
                        source_type=source_type,
                        quote=quote.strip()
                    )
                    session.add(citation)
                except ValueError:
                    self.log.warning("invalid_citation_uuid", uuid=source_id)
                    continue
                except Exception as e:
                    self.log.error("citation_save_failed", error=str(e))
                    continue
            
            session.commit()
