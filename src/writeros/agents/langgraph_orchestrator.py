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
from writeros.rag.retriever import RAGRetriever
from writeros.utils.langsmith_config import configure_langsmith, get_langsmith_url
from writeros.core.logging import get_logger

logger = get_logger(__name__)


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
    timeline_analysis: Optional[Any]
    psychology_analysis: Optional[Any]
    travel_analysis: Optional[Any]
    plot_analysis: Optional[Any]
    tension_analysis: Optional[Any]

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

    def __init__(self, enable_tracking: bool = True, checkpoint_dir: str = "./checkpoints"):
        super().__init__(model_name="gpt-5.1", enable_tracking=enable_tracking)

        # Configure LangSmith tracing
        langsmith_enabled = configure_langsmith()
        if langsmith_enabled:
            logger.info("langsmith_tracing_active", url=get_langsmith_url())

        # Initialize retriever
        self.retriever = RAGRetriever()

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
        logger.info("rag_retrieval_node_start", query=state["user_message"][:100])

        # Perform iterative RAG
        rag_result = await self.retriever.retrieve_iterative(
            initial_query=state["user_message"],
            max_hops=10,
            limit_per_hop=3
        )

        # Format context
        context_str = self.retriever.format_results(rag_result)

        logger.info(
            "rag_retrieval_complete",
            num_docs=len(rag_result.documents),
            num_entities=len(rag_result.entities)
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
        Node 2: Determine which agents should respond.

        For now, broadcasts to all agents. In the future, this could use
        an LLM to intelligently select only relevant agents.

        Updates state with:
        - selected_agents
        """
        # For now, select all agents (broadcast)
        selected_agents = list(self.agents.keys())

        logger.info("agent_router_selected", agents=selected_agents)

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

        # Extract structured analyses
        timeline_analysis = results.get("chronologist", {}).get("analysis")
        psychology_analysis = results.get("psychologist", {}).get("analysis")
        travel_analysis = results.get("navigator", {}).get("analysis")
        plot_analysis = results.get("architect", {}).get("analysis")
        tension_analysis = results.get("dramatist", {}).get("analysis")

        logger.info(
            "parallel_agents_complete",
            responses_count=len([r for r in results.values() if not r.get("skipped")])
        )

        return {
            "agent_responses": results,
            "timeline_analysis": timeline_analysis,
            "psychology_analysis": psychology_analysis,
            "travel_analysis": travel_analysis,
            "plot_analysis": plot_analysis,
            "tension_analysis": tension_analysis
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
        Execute a single agent with autonomy check and tool support.

        Returns:
            Dict with agent response or {"skipped": True} if agent declined
        """
        # Check if agent wants to respond (autonomy)
        should_respond = await self._check_agent_autonomy(agent_name, user_message, context)

        if not should_respond:
            logger.info("agent_skipped", agent=agent_name, reason="autonomy_check")
            return {"skipped": True, "reason": "Not relevant to my expertise"}

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

            # Psychologist
            elif agent_name == "psychologist":
                response = f"Psychology analysis for: {user_message}\nContext: {context[:200]}"
                return {"analysis": response, "type": "psychology"}

            # Generic agent execution
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

        # Format structured output
        structured_parts = ["## SYSTEMATIC ANALYSIS\n"]

        if state.get("timeline_analysis"):
            structured_parts.append("### TIMELINE ANALYSIS")
            structured_parts.append(str(state["timeline_analysis"]))
            structured_parts.append("")

        if state.get("psychology_analysis"):
            structured_parts.append("### PSYCHOLOGY ANALYSIS")
            structured_parts.append(str(state["psychology_analysis"]))
            structured_parts.append("")

        if state.get("travel_analysis"):
            structured_parts.append("### TRAVEL ANALYSIS")
            structured_parts.append(str(state["travel_analysis"]))
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
