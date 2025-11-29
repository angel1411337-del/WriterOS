"""
LangGraph-Powered Orchestrator Agent

This is the next-generation orchestrator using LangGraph for:
- State management with TypedDict
- Parallel agent execution
- Conditional routing
- Checkpointing and resumability
- Automatic tracing with LangSmith
"""
import asyncio
from typing import TypedDict, Annotated, List, Dict, Any, Optional, Sequence
from operator import add
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from writeros.agents.base import BaseAgent
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
from writeros.agents.formatters import AgentResponseFormatter
from writeros.rag.retriever import RAGRetriever
from writeros.utils.langsmith_config import configure_langsmith, get_langsmith_url
from writeros.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# AGENT ROUTING MODELS
# ============================================================================

class AgentRelevanceScores(BaseModel):
    """
    Relevance scores for all agents (0.0-1.0).
    Used by smart router to filter agents before execution.
    """
    profiler: float = Field(ge=0, le=1, description="Character/entity profiling relevance")
    psychologist: float = Field(ge=0, le=1, description="Character psychology/motivation relevance")
    chronologist: float = Field(ge=0, le=1, description="Timeline/chronology relevance")
    architect: float = Field(ge=0, le=1, description="Plot structure/narrative arc relevance")
    dramatist: float = Field(ge=0, le=1, description="Tension/conflict/drama relevance")
    mechanic: float = Field(ge=0, le=1, description="World rules/magic system relevance")
    navigator: float = Field(ge=0, le=1, description="Travel/geography/distance relevance")
    stylist: float = Field(ge=0, le=1, description="Prose style/voice/tone relevance")
    theorist: float = Field(ge=0, le=1, description="Themes/symbolism/meaning relevance")
    producer: float = Field(ge=0, le=1, description="Project planning/goals relevance")


# ============================================================================
# STATE DEFINITION
# ============================================================================

class OrchestratorState(TypedDict):
    """
    State for the LangGraph orchestrator workflow.

    The state flows through these nodes:
    1. rag_retrieval: Populate rag_documents and rag_entities
    2. agent_router: Determine which agents to invoke
    3. parallel_agents: Execute agents in parallel, populate agent_responses
    4. build_structured: Create structured_summary from agent responses
    5. synthesize_narrative: Create narrative_summary
    """
    # Input
    user_message: str
    vault_id: UUID
    conversation_id: Optional[UUID]

    # RAG Context (accumulated with add operator)
    rag_documents: Annotated[List[Dict[str, Any]], add]
    rag_entities: Annotated[List[Dict[str, Any]], add]
    context_str: str

    # Agent Execution
    selected_agents: List[str]  # Which agents to invoke
    agent_responses: Dict[str, Any]  # Agent name -> response

    # Structured Analysis (from individual agents)
    timeline_analysis: Optional[Any]  # chronologist
    psychology_analysis: Optional[Any]  # psychologist
    profiler_analysis: Optional[Any]  # profiler
    architect_analysis: Optional[Any]  # architect
    dramatist_analysis: Optional[Any]  # dramatist
    mechanic_analysis: Optional[Any]  # mechanic
    theorist_analysis: Optional[Any]  # theorist
    navigator_analysis: Optional[Any]  # navigator
    chronologist_analysis: Optional[Any]  # chronologist (alias)
    stylist_analysis: Optional[Any]  # stylist

    # Output
    structured_summary: str  # Formatted structured analysis
    narrative_summary: str  # Natural language synthesis
    final_output: str  # Combined output

    # Metadata
    messages: Annotated[Sequence[BaseMessage], add]
    error: Optional[str]


# ============================================================================
# LANGGRAPH ORCHESTRATOR
# ============================================================================

class LangGraphOrchestrator(BaseAgent):
    """
    LangGraph-powered orchestrator with state management and checkpointing.
    """

    def __init__(
        self,
        enable_tracking: bool = True,
        checkpoint_dir: str = "./checkpoints",
        use_graph_enhanced_retrieval: bool = False
    ):
        super().__init__(model_name="gpt-5.1", enable_tracking=enable_tracking)

        # Configure LangSmith tracing
        langsmith_enabled = configure_langsmith()
        if langsmith_enabled:
            logger.info("langsmith_tracing_active", url=get_langsmith_url())

        # Initialize retriever
        self.retriever = RAGRetriever()
        self.use_graph_enhanced_retrieval = use_graph_enhanced_retrieval

        # Initialize all agents
        self.agents = {
            "architect": ArchitectAgent(),
            "chronologist": ChronologistAgent(),
            "dramatist": DramatistAgent(),
            "mechanic": MechanicAgent(),
            "navigator": NavigatorAgent(),
            "producer": ProducerAgent(enable_tools=True),  # Enable tool calling
            "profiler": ProfilerAgent(),
            "psychologist": PsychologistAgent(),
            "stylist": StylistAgent(),
            "theorist": TheoristAgent()
        }

        # Build the workflow graph
        self.workflow = self._build_workflow()

        # Initialize checkpointer (use MemorySaver for now, can upgrade to SqliteSaver later)
        from langgraph.checkpoint.memory import MemorySaver
        self.checkpointer = MemorySaver()

        # Compile the graph with checkpointing
        self.app = self.workflow.compile(checkpointer=self.checkpointer)

        logger.info(
            "langgraph_orchestrator_initialized",
            num_agents=len(self.agents),
            checkpoint_dir=checkpoint_dir
        )

    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow for multi-agent orchestration.

        Workflow:
        START -> rag_retrieval -> agent_router -> parallel_agents ->
        build_structured -> synthesize_narrative -> END
        """
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("rag_retrieval", self._rag_retrieval_node)
        workflow.add_node("agent_router", self._agent_router_node)
        workflow.add_node("parallel_agents", self._parallel_agents_node)
        workflow.add_node("build_structured", self._build_structured_node)
        workflow.add_node("synthesize_narrative", self._synthesize_narrative_node)

        # Define edges
        workflow.set_entry_point("rag_retrieval")
        workflow.add_edge("rag_retrieval", "agent_router")
        workflow.add_edge("agent_router", "parallel_agents")
        workflow.add_edge("parallel_agents", "build_structured")
        workflow.add_edge("build_structured", "synthesize_narrative")
        workflow.add_edge("synthesize_narrative", END)

        return workflow

    # ========================================================================
    # WORKFLOW NODES
    # ========================================================================

    async def _rag_retrieval_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node 1: Perform iterative RAG retrieval.

        Updates state with:
        - rag_documents
        - rag_entities
        - context_str
        """
        logger.info(
            "rag_retrieval_node_start",
            query=state["user_message"][:100],
            graph_enhanced=self.use_graph_enhanced_retrieval
        )

        if self.use_graph_enhanced_retrieval and state.get("vault_id"):
            # Use graph-enhanced retrieval for improved relevance
            logger.info("using_graph_enhanced_retrieval")
            rag_result = await self.retriever.retrieve_with_graph_enhancement(
                query=state["user_message"],
                vault_id=state["vault_id"],
                k=15,  # Number of results per type
                expand_graph=True,
                entity_boost_direct=0.3,
                entity_boost_indirect=0.1,
                return_chunks=True  # Use chunk-level retrieval
            )
        else:
            # Standard iterative RAG with deeper search
            # 15 hops x 15 docs/hop = up to 225 documents (convergence usually stops earlier)
            rag_result = await self.retriever.retrieve_iterative(
                initial_query=state["user_message"],
                vault_id=state.get("vault_id"),
                max_hops=15,
                limit_per_hop=15
            )

        # Format context
        context_str = self.retriever.format_results(rag_result)

        logger.info(
            "rag_retrieval_complete",
            num_docs=len(rag_result.documents),
            num_entities=len(rag_result.entities),
            graph_enhanced=self.use_graph_enhanced_retrieval
        )

        # Eagerly access attributes to avoid detached instance errors
        rag_documents = []
        for doc in rag_result.documents:
            rag_documents.append({
                "content": str(doc.content) if hasattr(doc, 'content') else "",
                "source": str(doc.file_path) if hasattr(doc, 'file_path') else "unknown"
            })

        rag_entities = []
        for e in rag_result.entities:
            rag_entities.append({
                "name": str(e.name) if hasattr(e, 'name') else "",
                "type": str(e.type) if hasattr(e, 'type') else ""
            })

        return {
            "rag_documents": rag_documents,
            "rag_entities": rag_entities,
            "context_str": context_str
        }

    async def _agent_router_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node 2: Determine which agents should respond using smart LLM-based routing.

        Uses a single fast LLM call to score all agents (0.0-1.0) and selects
        agents with score >= 0.5. This replaces 10 separate autonomy checks.

        Updates state with:
        - selected_agents
        """
        user_message = state["user_message"]
        context = state.get("rag_context", "")

        # Use a small, fast model for routing (gpt-4o-mini or similar)
        from langchain_openai import ChatOpenAI
        router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # Create structured output extractor
        scoring_llm = router_llm.with_structured_output(AgentRelevanceScores)

        # Build routing prompt
        routing_prompt = f"""You are an agent router for a multi-agent fiction writing system.

Score each agent's relevance to the user query on a scale of 0.0 to 1.0:
- 0.0 = Completely irrelevant, should not run
- 0.5 = Somewhat relevant, borderline
- 1.0 = Highly relevant, definitely should run

**User Query**: {user_message}

**Retrieved Context** (first 500 chars): {context[:500] if context else "No context available"}

**Agent Descriptions**:
- profiler: Identifies and profiles characters, entities, relationships
- psychologist: Analyzes character psychology, motivations, emotional arcs
- chronologist: Tracks timelines, event sequences, chronology
- architect: Analyzes plot structure, narrative arcs, story architecture
- dramatist: Evaluates tension, conflict, drama, stakes
- mechanic: Checks world-building rules, magic systems, internal consistency
- navigator: Handles travel logistics, geography, distances, routes
- stylist: Analyzes prose style, voice, tone, writing quality
- theorist: Examines themes, symbolism, deeper meanings
- producer: Manages project planning, goals, objectives

Provide a relevance score (0.0-1.0) for EACH agent."""

        try:
            # Get scores in a single LLM call
            scores: AgentRelevanceScores = await scoring_llm.ainvoke(routing_prompt)

            # Filter agents by score threshold (>= 0.5)
            threshold = 0.5
            selected_agents = []
            scores_dict = scores.model_dump()

            for agent_name, score in scores_dict.items():
                if score >= threshold:
                    selected_agents.append(agent_name)

            logger.info("smart_routing_complete",
                       threshold=threshold,
                       scores=scores_dict,
                       selected_agents=selected_agents,
                       num_selected=len(selected_agents))

            # Fallback: If no agents selected, run profiler as default
            if not selected_agents:
                logger.warning("no_agents_selected",
                             message="No agents met threshold, defaulting to profiler")
                selected_agents = ["profiler"]

        except Exception as e:
            logger.error("routing_failed", error=str(e))
            # Fallback: Run all agents if routing fails
            selected_agents = list(self.agents.keys())
            logger.warning("routing_fallback",
                         message="Routing failed, running all agents",
                         agents=selected_agents)

        return {"selected_agents": selected_agents}

    async def _parallel_agents_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node 3: Execute selected agents in parallel.

        This is where LangGraph shines - it automatically parallelizes
        independent async operations.

        Updates state with:
        - agent_responses
        - timeline_analysis (if chronologist responded)
        - psychology_analysis (if psychologist responded)
        - etc.
        """
        logger.info("parallel_agents_start", num_agents=len(state["selected_agents"]))

        # Execute agents in parallel
        tasks = {}
        for agent_name in state["selected_agents"]:
            agent = self.agents[agent_name]
            # Each agent gets the user message, RAG context, and vault_id
            task = self._execute_single_agent(
                agent_name,
                agent,
                state["user_message"],
                state["context_str"],
                vault_id=state.get("vault_id")
            )
            tasks[agent_name] = task

        # Wait for all agents to complete
        results = {}
        for agent_name, task in tasks.items():
            try:
                results[agent_name] = await task
            except Exception as e:
                logger.error("agent_execution_failed", agent=agent_name, error=str(e))
                results[agent_name] = {"error": str(e), "skipped": True}

        # Extract structured analyses from all agents
        timeline_analysis = results.get("chronologist", {}).get("analysis")
        psychology_analysis = results.get("psychologist", {}).get("analysis")
        profiler_analysis = results.get("profiler", {}).get("analysis")
        architect_analysis = results.get("architect", {}).get("analysis")
        dramatist_analysis = results.get("dramatist", {}).get("analysis")
        mechanic_analysis = results.get("mechanic", {}).get("analysis")
        theorist_analysis = results.get("theorist", {}).get("analysis")
        navigator_analysis = results.get("navigator", {}).get("analysis")
        stylist_analysis = results.get("stylist", {}).get("analysis")

        logger.info(
            "parallel_agents_complete",
            responses_count=len([r for r in results.values() if not r.get("skipped")])
        )

        return {
            "agent_responses": results,
            "timeline_analysis": timeline_analysis,
            "chronologist_analysis": timeline_analysis,  # Alias for clarity
            "psychology_analysis": psychology_analysis,
            "profiler_analysis": profiler_analysis,
            "architect_analysis": architect_analysis,
            "dramatist_analysis": dramatist_analysis,
            "mechanic_analysis": mechanic_analysis,
            "theorist_analysis": theorist_analysis,
            "navigator_analysis": navigator_analysis,
            "stylist_analysis": stylist_analysis,
        }

    async def _execute_single_agent(
        self,
        agent_name: str,
        agent: BaseAgent,
        user_message: str,
        context: str,
        vault_id: UUID = None
    ) -> Dict[str, Any]:
        """
        Execute a single agent (already filtered by smart router).

        The smart router has already determined this agent is relevant,
        so we skip the autonomy check.

        Returns:
            Dict with agent response
        """
        # Agent has already been selected by smart router, no autonomy check needed

        # Agent wants to respond - execute it
        try:
            # ProducerAgent with tool support
            if agent_name == "producer" and hasattr(agent, "run_with_tools"):
                result = await agent.run_with_tools(
                    user_message=user_message,
                    context=context,
                    vault_id=str(vault_id) if vault_id else ""
                )
                return {
                    "analysis": result.get("analysis", ""),
                    "type": "producer",
                    "tool_calls": result.get("tool_calls", []),
                    "wants_tools": result.get("wants_tools", False)
                }

            # Chronologist with LCEL
            elif agent_name == "chronologist":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "timeline"}

            # Psychologist with LCEL
            elif agent_name == "psychologist":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "psychology"}

            # Profiler with LCEL
            elif agent_name == "profiler":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "profiler"}

            # Architect with LCEL
            elif agent_name == "architect":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "architect"}

            # Dramatist with LCEL
            elif agent_name == "dramatist":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "dramatist"}

            # Mechanic with LCEL
            elif agent_name == "mechanic":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "mechanic"}

            # Navigator with LCEL
            elif agent_name == "navigator":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "navigator"}

            # Stylist with LCEL
            elif agent_name == "stylist":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "stylist"}

            # Theorist with LCEL
            elif agent_name == "theorist":
                result = await agent.run(full_text=context, existing_notes="", title=user_message[:50])
                return {"analysis": result, "type": "theorist"}

            # Generic agent execution (fallback)
            else:
                response = f"{agent_name.capitalize()} analysis of: {user_message[:100]}"
                return {"analysis": response, "type": "generic"}

        except Exception as e:
            logger.error("agent_execution_error", agent=agent_name, error=str(e))
            return {"error": str(e), "skipped": True}

    async def _check_agent_autonomy(self, agent_name: str, query: str, context: str) -> bool:
        """
        Check if an agent should respond to this query (autonomy check).

        Uses a lightweight LLM call to determine relevance.
        Returns True if agent should respond, False to skip.
        """
        # For now, use simple keyword matching (can be upgraded to LLM-based later)
        keywords = {
            "chronologist": ["timeline", "when", "sequence", "chronology", "events", "happened"],
            "psychologist": ["why", "psychology", "motivation", "character", "feeling", "think"],
            "navigator": ["travel", "journey", "distance", "miles", "km", "route", "location"],
            "architect": ["plot", "structure", "arc", "story", "narrative"],
            "dramatist": ["tension", "conflict", "drama", "stakes", "suspense"],
            "mechanic": ["magic", "rules", "system", "world", "mechanics"],
            "producer": ["goal", "plan", "project", "objective"],
            "profiler": ["entity", "relationship", "character", "person"],
            "stylist": ["style", "prose", "writing", "voice", "tone"],
            "theorist": ["theme", "symbolism", "meaning", "interpretation"]
        }

        agent_keywords = keywords.get(agent_name, [])
        query_lower = query.lower()

        # Check if any keywords match
        for keyword in agent_keywords:
            if keyword in query_lower:
                return True

        # Default: respond (broadcast mode)
        return True

    async def _build_structured_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node 4: Build structured summary from agent responses.

        Updates state with:
        - structured_summary
        """
        logger.info("build_structured_start")

        # Format structured output using AgentResponseFormatter
        formatter = AgentResponseFormatter()
        structured_parts = ["## SYSTEMATIC ANALYSIS\n"]

        # Format each agent's output using the appropriate formatter
        if state.get("timeline_analysis"):
            structured_parts.append(formatter.format_timeline(state["timeline_analysis"]))
            structured_parts.append("")

        if state.get("psychology_analysis"):
            structured_parts.append(formatter.format_psychology(state["psychology_analysis"]))
            structured_parts.append("")

        if state.get("profiler_analysis"):
            structured_parts.append(formatter.format_profiler(state["profiler_analysis"]))
            structured_parts.append("")

        if state.get("architect_analysis"):
            structured_parts.append(formatter.format_architect(state["architect_analysis"]))
            structured_parts.append("")

        if state.get("dramatist_analysis"):
            structured_parts.append(formatter.format_dramatist(state["dramatist_analysis"]))
            structured_parts.append("")

        if state.get("mechanic_analysis"):
            structured_parts.append(formatter.format_mechanic(state["mechanic_analysis"]))
            structured_parts.append("")

        if state.get("theorist_analysis"):
            structured_parts.append(formatter.format_theorist(state["theorist_analysis"]))
            structured_parts.append("")

        if state.get("navigator_analysis"):
            structured_parts.append(formatter.format_navigator(state["navigator_analysis"]))
            structured_parts.append("")

        if state.get("chronologist_analysis"):
            structured_parts.append(formatter.format_chronologist(state["chronologist_analysis"]))
            structured_parts.append("")

        if state.get("stylist_analysis"):
            structured_parts.append(formatter.format_stylist(state["stylist_analysis"]))
            structured_parts.append("")

        structured_summary = "\n".join(structured_parts)

        logger.info("build_structured_complete", length=len(structured_summary))

        return {"structured_summary": structured_summary}

    async def _synthesize_narrative_node(self, state: OrchestratorState) -> Dict[str, Any]:
        """
        Node 5: Synthesize natural language narrative from agent responses.

        Updates state with:
        - narrative_summary
        - final_output
        """
        logger.info("synthesize_narrative_start")

        # Use LLM to synthesize narrative
        agent_summaries = []
        for agent_name, response in state["agent_responses"].items():
            if not response.get("skipped"):
                agent_summaries.append(f"- {agent_name}: {response.get('analysis', 'No analysis')}")

        synthesis_prompt = f"""
User Question: {state["user_message"]}

Agent Responses:
{chr(10).join(agent_summaries)}

Synthesize a natural, conversational response that addresses the user's question
based on the agent responses above. Be concise and helpful.
"""

        # Simple synthesis (can be enhanced with LLM call)
        narrative_summary = f"Based on the analysis from {len(agent_summaries)} agents, here's what I found:\n\n"
        narrative_summary += "\n".join(agent_summaries)

        # Combine structured + narrative
        final_output = state["structured_summary"] + "\n\n## NARRATIVE SUMMARY\n\n" + narrative_summary

        logger.info("synthesize_narrative_complete")

        return {
            "narrative_summary": narrative_summary,
            "final_output": final_output,
            "messages": [AIMessage(content=final_output)]
        }

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    async def process_chat(
        self,
        user_message: str,
        vault_id: UUID,
        conversation_id: Optional[UUID] = None
    ):
        """
        Process a chat message using the LangGraph workflow with streaming support.

        Args:
            user_message: User's query
            vault_id: Vault to search
            conversation_id: Optional conversation ID for resuming

        Yields:
            Chunks of the response as they're generated
        """
        from typing import AsyncGenerator
        from uuid import uuid4
        from sqlmodel import Session
        from writeros.schema import Conversation, Message
        from writeros.utils.db import engine

        logger.info("langgraph_process_chat_start", query=user_message[:100])

        # Create or use existing conversation
        if not conversation_id:
            conversation_id = self._create_conversation(vault_id, user_message)
            logger.info("conversation_created", conversation_id=str(conversation_id))

        # Initialize state
        initial_state: OrchestratorState = {
            "user_message": user_message,
            "vault_id": vault_id,
            "conversation_id": conversation_id,
            "rag_documents": [],
            "rag_entities": [],
            "context_str": "",
            "selected_agents": [],
            "agent_responses": {},
            "timeline_analysis": None,
            "psychology_analysis": None,
            "travel_analysis": None,
            "plot_analysis": None,
            "tension_analysis": None,
            "structured_summary": "",
            "narrative_summary": "",
            "final_output": "",
            "messages": [HumanMessage(content=user_message)],
            "error": None
        }

        # Run the workflow
        config = {"configurable": {"thread_id": str(conversation_id)}}
        final_state = await self.app.ainvoke(initial_state, config)

        # Save user message
        self._save_message(conversation_id, "user", user_message)

        # Stream structured summary first
        if final_state["structured_summary"]:
            yield final_state["structured_summary"]
            yield "\n\n"

        # Then stream narrative summary
        yield "## 💬 NARRATIVE SUMMARY\n\n"
        yield final_state["narrative_summary"]

        # Save complete assistant message
        full_response = ""
        if final_state["structured_summary"]:
            full_response += final_state["structured_summary"] + "\n\n"
        full_response += "## 💬 NARRATIVE SUMMARY\n\n" + final_state["narrative_summary"]

        self._save_message(
            conversation_id,
            "assistant",
            full_response,
            agent="LangGraphOrchestrator"
        )

        logger.info("langgraph_process_chat_complete", conversation_id=str(conversation_id))

    def _create_conversation(self, vault_id: UUID, first_message: str) -> UUID:
        """Create a new conversation in the database."""
        from sqlmodel import Session
        from writeros.schema import Conversation
        from writeros.utils.db import engine

        with Session(engine) as session:
            title = first_message[:50] + "..." if len(first_message) > 50 else first_message
            conv = Conversation(vault_id=vault_id, title=title)
            session.add(conv)
            session.commit()
            session.refresh(conv)
            return conv.id

    def _save_message(self, conversation_id: UUID, role: str, content: str, agent: str = None):
        """Save a message to the database."""
        from sqlmodel import Session
        from writeros.schema import Message
        from writeros.utils.db import engine

        with Session(engine) as session:
            msg = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                agent=agent
            )
            session.add(msg)
            session.commit()
