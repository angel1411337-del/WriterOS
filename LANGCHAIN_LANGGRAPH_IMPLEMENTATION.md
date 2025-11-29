# LangChain + LangGraph Comprehensive Implementation
**Date:** 2025-11-27
**Goal:** Leverage LangChain and LangGraph to their fullest potential
**Status:** Implementation Plan

---

## 🎯 Strategic Vision

**Current State:** Manual orchestration with `asyncio.gather()` and custom LLM clients

**Target State:** Full LangChain/LangGraph ecosystem with:
- 🔗 **LCEL (LangChain Expression Language)** for composable chains
- 📊 **LangGraph** for complex multi-agent workflows
- 🧠 **Memory** systems (conversation, entity, summary)
- 🛠️ **Tools** for function calling and file operations
- 📈 **Tracing** with LangSmith integration
- ♻️ **Streaming** for real-time responses

---

## 📦 Phase 1: LangChain Foundation (Week 1)

### 1.1 Upgrade LangChain Ecosystem

**File:** `requirements.txt`

```txt
# LangChain Core Ecosystem (Latest)
langchain>=0.3.0
langchain-core>=0.3.0
langchain-community>=0.3.0
langchain-openai>=0.2.0

# LangGraph for Workflows
langgraph>=0.2.28
langgraph-checkpoint>=0.1.0
langgraph-checkpoint-sqlite>=0.1.0

# LangSmith for Observability (Optional but Recommended)
langsmith>=0.1.0

# Existing dependencies...
openai>=1.50.0
tiktoken>=0.7.0
```

### 1.2 Replace Custom LLM Client with LangChain

**Current:** `src/writeros/utils/llm_client.py` (Custom wrapper)

**New:** `src/writeros/utils/llm_client.py` (LangChain native)

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

logger = structlog.get_logger()

class LLMClient:
    """LangChain-native LLM client with streaming, structured output, and tracing"""

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.7,
        streaming: bool = True,
        enable_tracing: bool = True
    ):
        self.model = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            streaming=streaming
        )
        self.streaming = streaming
        self.enable_tracing = enable_tracing

    async def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        response_format: Optional[type[BaseModel]] = None,
        tools: Optional[List] = None,
        stream: bool = None
    ):
        """
        Unified chat interface supporting:
        - Streaming responses
        - Structured outputs (Pydantic)
        - Function calling (tools)
        - Automatic tracing
        """
        # Convert messages to LangChain format
        lc_messages = self._convert_messages(messages, system_prompt)

        # Build chain based on requirements
        if response_format:
            # Structured output with Pydantic
            chain = self._build_structured_chain(lc_messages, response_format)
        elif tools:
            # Function calling with tools
            chain = self._build_tool_chain(lc_messages, tools)
        else:
            # Standard text response
            chain = self._build_text_chain(lc_messages)

        # Execute with optional streaming
        use_streaming = stream if stream is not None else self.streaming

        if use_streaming:
            return chain.astream({})
        else:
            return await chain.ainvoke({})

    def _convert_messages(self, messages, system_prompt):
        """Convert dict messages to LangChain message objects"""
        lc_messages = []

        if system_prompt:
            lc_messages.append(SystemMessage(content=system_prompt))

        for msg in messages:
            if msg['role'] == 'user':
                lc_messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                lc_messages.append(AIMessage(content=msg['content']))
            elif msg['role'] == 'system':
                lc_messages.append(SystemMessage(content=msg['content']))

        return lc_messages

    def _build_text_chain(self, messages):
        """Simple text response chain"""
        prompt = ChatPromptTemplate.from_messages(messages)
        chain = prompt | self.model | StrOutputParser()
        return chain

    def _build_structured_chain(self, messages, response_format: type[BaseModel]):
        """Structured output chain with Pydantic validation"""
        prompt = ChatPromptTemplate.from_messages(messages)
        parser = PydanticOutputParser(pydantic_object=response_format)

        # Add format instructions to prompt
        format_instructions = parser.get_format_instructions()
        messages.append(SystemMessage(
            content=f"\n\nFormat your response as JSON:\n{format_instructions}"
        ))

        chain = prompt | self.model | parser
        return chain

    def _build_tool_chain(self, messages, tools):
        """Function calling chain with tools"""
        model_with_tools = self.model.bind_tools(tools)
        prompt = ChatPromptTemplate.from_messages(messages)

        chain = prompt | model_with_tools
        return chain

# Factory function
def get_llm_client(
    model_name: str = "gpt-4o",
    streaming: bool = True
) -> LLMClient:
    """Get LangChain-native LLM client"""
    return LLMClient(model_name=model_name, streaming=streaming)
```

**Benefits:**
- ✅ **Streaming by default** (real-time responses)
- ✅ **Structured outputs** with automatic Pydantic validation
- ✅ **Tool calling** built-in
- ✅ **Automatic tracing** (LangSmith integration)
- ✅ **LCEL composability** (can chain with other runnables)

---

### 1.3 Add LangChain Memory Systems

**File:** `src/writeros/memory/__init__.py` (NEW)

```python
from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory
from langchain_community.memory import SQLChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from sqlmodel import Session, select
from writeros.utils.db import engine
from writeros.schema import Conversation, Message
from uuid import UUID
from typing import List
import structlog

logger = structlog.get_logger()

class PostgresChatHistory(BaseChatMessageHistory):
    """
    LangChain-compatible chat history backed by PostgreSQL.
    Integrates with existing Conversation/Message schema.
    """

    def __init__(self, conversation_id: UUID):
        self.conversation_id = conversation_id

    @property
    def messages(self) -> List:
        """Retrieve messages from database"""
        with Session(engine) as session:
            msgs = session.exec(
                select(Message)
                .where(Message.conversation_id == self.conversation_id)
                .order_by(Message.created_at)
            ).all()

            return self._to_langchain_messages(msgs)

    def add_message(self, message) -> None:
        """Add message to database"""
        from langchain_core.messages import HumanMessage, AIMessage

        with Session(engine) as session:
            msg = Message(
                conversation_id=self.conversation_id,
                role='user' if isinstance(message, HumanMessage) else 'assistant',
                content=message.content
            )
            session.add(msg)
            session.commit()

    def clear(self) -> None:
        """Clear conversation history"""
        with Session(engine) as session:
            msgs = session.exec(
                select(Message)
                .where(Message.conversation_id == self.conversation_id)
            ).all()
            for msg in msgs:
                session.delete(msg)
            session.commit()

    def _to_langchain_messages(self, msgs):
        """Convert DB messages to LangChain format"""
        from langchain_core.messages import HumanMessage, AIMessage

        return [
            HumanMessage(content=m.content) if m.role == 'user'
            else AIMessage(content=m.content)
            for m in msgs
        ]

class MemoryManager:
    """Factory for different memory types"""

    @staticmethod
    def get_conversation_memory(conversation_id: UUID):
        """Get buffer memory for short-term chat"""
        history = PostgresChatHistory(conversation_id)
        return ConversationBufferMemory(
            chat_memory=history,
            return_messages=True,
            memory_key="chat_history"
        )

    @staticmethod
    def get_summary_memory(conversation_id: UUID, llm):
        """Get summarizing memory for long conversations"""
        history = PostgresChatHistory(conversation_id)
        return ConversationSummaryMemory(
            chat_memory=history,
            llm=llm,
            return_messages=True,
            memory_key="chat_history"
        )
```

**Usage in Agents:**
```python
class PsychologistAgent(BaseAgent):
    async def run(self, query, vault_id, conversation_id):
        # Get conversation memory
        memory = MemoryManager.get_conversation_memory(conversation_id)

        # Load history into prompt
        history = memory.load_memory_variables({})

        prompt = f"""
        Previous conversation:
        {history['chat_history']}

        New query: {query}
        """

        response = await self.llm.chat([{"role": "user", "content": prompt}])

        # Save to memory
        memory.save_context(
            {"input": query},
            {"output": response}
        )

        return response
```

---

### 1.4 Convert Agents to LangChain LCEL Chains

**Example: ChronologistAgent → LCEL Chain**

**Current:**
```python
class ChronologistAgent(BaseAgent):
    async def run(self, query, vault_id):
        # Manual prompt building
        prompt = f"Analyze timeline: {query}"
        response = await self.llm.chat([{"role": "user", "content": prompt}])
        # Manual parsing
        return self._parse_timeline(response)
```

**New (LCEL):**
```python
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List

class TimelineEvent(BaseModel):
    """Structured timeline event"""
    title: str = Field(description="Event title")
    order: int = Field(description="Chronological order")
    description: str = Field(description="Event description")
    timestamp: str = Field(description="When it occurred")

class TimelineExtraction(BaseModel):
    """Complete timeline analysis"""
    events: List[TimelineEvent]
    continuity_notes: str = Field(description="Timeline issues or notes")

class ChronologistAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_name="gpt-4o")
        self.chain = self._build_chain()

    def _build_chain(self):
        """Build LCEL chain for timeline analysis"""
        # Parser
        parser = PydanticOutputParser(pydantic_object=TimelineExtraction)

        # Prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a chronologist analyzing narrative timelines.
            Extract events in chronological order and identify continuity issues.

            {format_instructions}
            """),
            ("user", "Query: {query}\n\nContext:\n{context}")
        ])

        # RAG retrieval (as a Runnable)
        def retrieve_context(inputs):
            retriever = RAGRetriever()
            results = retriever.retrieve(
                query=inputs['query'],
                vault_id=inputs['vault_id']
            )
            return {
                **inputs,
                'context': '\n'.join([d.content for d in results.documents])
            }

        # Build chain
        chain = (
            RunnableLambda(retrieve_context)  # RAG step
            | RunnablePassthrough.assign(
                format_instructions=lambda _: parser.get_format_instructions()
            )
            | prompt  # Prompt formatting
            | self.llm.model  # LLM call
            | parser  # Parse to Pydantic
        )

        return chain

    async def run(self, query: str, vault_id: UUID) -> TimelineExtraction:
        """Execute timeline analysis chain"""
        result = await self.chain.ainvoke({
            'query': query,
            'vault_id': vault_id
        })
        return result
```

**Benefits:**
- ✅ **Type-safe** (Pydantic models)
- ✅ **Composable** (can chain with other runnables)
- ✅ **Streamable** (use `.astream()` for real-time)
- ✅ **Traceable** (automatic LangSmith logging)
- ✅ **Testable** (each step is a discrete function)

---

## 📊 Phase 2: LangGraph Multi-Agent System (Week 2-3)

### 2.1 Orchestrator as LangGraph Workflow

**Current:** Manual broadcast + synthesis

**New:** State-driven agent collaboration graph

**File:** `src/writeros/workflows/orchestrator_graph.py` (NEW)

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import TypedDict, Annotated, List, Dict, Any
from operator import add
from uuid import UUID
import structlog

logger = structlog.get_logger()

# ==================== State Definition ====================

class OrchestratorState(TypedDict):
    """Shared state across all agents"""

    # Input
    user_message: str
    vault_id: UUID
    conversation_id: UUID

    # RAG Context
    rag_documents: Annotated[List[Dict], add]  # Accumulate docs
    rag_entities: Annotated[List[Dict], add]
    total_context_tokens: int

    # Agent Responses (keyed by agent name)
    agent_responses: Dict[str, Any]

    # Structured Analysis
    timeline_analysis: Any  # TimelineExtraction
    psychology_analysis: Any  # PsychologyExtraction
    travel_analysis: Any  # TravelExtraction
    architect_analysis: Any  # ArchitectExtraction

    # Synthesis
    narrative_summary: str
    structured_summary: str
    final_output: str

    # Control Flow
    agents_to_invoke: List[str]
    agents_completed: Annotated[List[str], add]
    mechanic_veto_active: bool
    user_approved: bool

# ==================== Node Functions ====================

async def rag_retrieval_node(state: OrchestratorState) -> OrchestratorState:
    """Step 1: Retrieve context from RAG system"""
    from writeros.rag.retriever import RAGRetriever

    logger.info("rag_retrieval_started", query=state['user_message'])

    retriever = RAGRetriever()
    results = await retriever.retrieve(
        query=state['user_message'],
        vault_id=state['vault_id'],
        limit=10
    )

    state['rag_documents'].extend([
        {'content': d.content, 'source': d.source_id}
        for d in results.documents
    ])
    state['rag_entities'].extend([
        {'name': e.name, 'type': e.type}
        for e in results.entities
    ])
    state['total_context_tokens'] = sum(
        len(d['content'].split()) for d in state['rag_documents']
    ) * 1.3  # Rough token estimate

    logger.info("rag_retrieval_complete",
                docs=len(state['rag_documents']),
                entities=len(state['rag_entities']))

    return state

async def agent_router_node(state: OrchestratorState) -> OrchestratorState:
    """Step 2: Determine which agents should respond"""
    from writeros.agents.profiler import ProfilerAgent
    from writeros.agents.chronologist import ChronologistAgent
    from writeros.agents.psychologist import PsychologistAgent
    from writeros.agents.navigator import NavigatorAgent
    from writeros.agents.architect import ArchitectAgent
    from writeros.agents.mechanic import MechanicAgent

    # Map of all available agents
    agents = {
        'profiler': ProfilerAgent(),
        'chronologist': ChronologistAgent(),
        'psychologist': PsychologistAgent(),
        'navigator': NavigatorAgent(),
        'architect': ArchitectAgent(),
        'mechanic': MechanicAgent()
    }

    # Ask each agent if they should respond
    agents_to_invoke = []

    for name, agent in agents.items():
        should_respond, confidence, reason = await agent.should_respond(
            query=state['user_message'],
            context=state['rag_documents']
        )

        if should_respond:
            agents_to_invoke.append(name)
            logger.info("agent_selected", agent=name, confidence=confidence)
        else:
            logger.info("agent_skipped", agent=name, reason=reason)

    state['agents_to_invoke'] = agents_to_invoke
    return state

async def parallel_agent_execution_node(state: OrchestratorState) -> OrchestratorState:
    """Step 3: Execute all selected agents in parallel"""
    import asyncio
    from writeros.agents.profiler import ProfilerAgent
    from writeros.agents.chronologist import ChronologistAgent
    from writeros.agents.psychologist import PsychologistAgent
    from writeros.agents.navigator import NavigatorAgent
    from writeros.agents.architect import ArchitectAgent

    agents_map = {
        'profiler': ProfilerAgent(),
        'chronologist': ChronologistAgent(),
        'psychologist': PsychologistAgent(),
        'navigator': NavigatorAgent(),
        'architect': ArchitectAgent()
    }

    # Execute agents in parallel
    tasks = []
    for agent_name in state['agents_to_invoke']:
        if agent_name in agents_map:
            agent = agents_map[agent_name]
            tasks.append(agent.chain.ainvoke({
                'query': state['user_message'],
                'vault_id': state['vault_id'],
                'context': state['rag_documents']
            }))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Store results by agent name
    for agent_name, result in zip(state['agents_to_invoke'], results):
        if isinstance(result, Exception):
            logger.error("agent_failed", agent=agent_name, error=str(result))
        else:
            state['agent_responses'][agent_name] = result
            state['agents_completed'].append(agent_name)

            # Store in typed fields for easy access
            if agent_name == 'chronologist':
                state['timeline_analysis'] = result
            elif agent_name == 'psychologist':
                state['psychology_analysis'] = result
            elif agent_name == 'navigator':
                state['travel_analysis'] = result
            elif agent_name == 'architect':
                state['architect_analysis'] = result

    logger.info("parallel_execution_complete",
                completed=len(state['agents_completed']),
                failed=len(tasks) - len(state['agents_completed']))

    return state

async def build_structured_summary_node(state: OrchestratorState) -> OrchestratorState:
    """Step 4: Format structured analysis from agent responses"""
    from writeros.agents.orchestrator import OrchestratorAgent

    orchestrator = OrchestratorAgent()
    structured = orchestrator._build_structured_summary(state['agent_responses'])

    state['structured_summary'] = structured
    return state

async def synthesize_narrative_node(state: OrchestratorState) -> OrchestratorState:
    """Step 5: Generate prose synthesis"""
    from writeros.agents.orchestrator import OrchestratorAgent

    orchestrator = OrchestratorAgent()
    synthesis = await orchestrator._synthesize_response(
        state['user_message'],
        state['agent_responses']
    )

    state['narrative_summary'] = synthesis
    return state

async def combine_outputs_node(state: OrchestratorState) -> OrchestratorState:
    """Step 6: Combine structured + narrative outputs"""
    output = ""

    if state['structured_summary']:
        output += "## 📊 SYSTEMATIC ANALYSIS\n\n"
        output += state['structured_summary']
        output += "\n\n"

    output += "## 💬 NARRATIVE SUMMARY\n\n"
    output += state['narrative_summary']

    state['final_output'] = output
    return state

async def mechanic_validation_node(state: OrchestratorState) -> OrchestratorState:
    """Step 7: Check for logic violations (optional step)"""
    from writeros.agents.mechanic import MechanicAgent

    mechanic = MechanicAgent()

    # If narrative involves scene generation, validate it
    if 'generate' in state['user_message'].lower() or 'write' in state['user_message'].lower():
        violations = await mechanic.validate_content(state['narrative_summary'])

        if any(v.type == 'FATAL' for v in violations):
            state['mechanic_veto_active'] = True
            logger.warning("mechanic_veto_triggered", violations=len(violations))
        else:
            state['mechanic_veto_active'] = False
    else:
        state['mechanic_veto_active'] = False

    return state

# ==================== Conditional Edges ====================

def should_validate_with_mechanic(state: OrchestratorState) -> str:
    """Route to mechanic validation if generating content"""
    if 'generate' in state['user_message'].lower() or 'write' in state['user_message'].lower():
        return "validate"
    else:
        return "combine"

def mechanic_veto_decision(state: OrchestratorState) -> str:
    """Route based on mechanic veto status"""
    if state.get('mechanic_veto_active'):
        return "user_review"  # Pause for human approval
    else:
        return "combine"  # Continue normally

# ==================== Graph Construction ====================

def build_orchestrator_graph():
    """Build the complete orchestrator workflow"""

    # Initialize with checkpointing
    checkpointer = SqliteSaver.from_conn_string(".writeros/orchestrator_checkpoints.db")

    # Create graph
    workflow = StateGraph(OrchestratorState)

    # Add nodes
    workflow.add_node("rag_retrieval", rag_retrieval_node)
    workflow.add_node("agent_router", agent_router_node)
    workflow.add_node("parallel_execution", parallel_agent_execution_node)
    workflow.add_node("build_structured", build_structured_summary_node)
    workflow.add_node("synthesize", synthesize_narrative_node)
    workflow.add_node("mechanic_validate", mechanic_validation_node)
    workflow.add_node("combine_outputs", combine_outputs_node)

    # Linear flow
    workflow.set_entry_point("rag_retrieval")
    workflow.add_edge("rag_retrieval", "agent_router")
    workflow.add_edge("agent_router", "parallel_execution")
    workflow.add_edge("parallel_execution", "build_structured")
    workflow.add_edge("build_structured", "synthesize")

    # Conditional routing for mechanic validation
    workflow.add_conditional_edges(
        "synthesize",
        should_validate_with_mechanic,
        {
            "validate": "mechanic_validate",
            "combine": "combine_outputs"
        }
    )

    workflow.add_conditional_edges(
        "mechanic_validate",
        mechanic_veto_decision,
        {
            "user_review": "combine_outputs",  # For now, just continue (Phase 3 will add pause)
            "combine": "combine_outputs"
        }
    )

    workflow.add_edge("combine_outputs", END)

    # Compile with checkpointing
    return workflow.compile(checkpointer=checkpointer)

# ==================== Usage ====================

async def run_orchestrator(user_message: str, vault_id: UUID, conversation_id: UUID):
    """Execute orchestrator workflow"""
    graph = build_orchestrator_graph()

    # Initial state
    initial_state = {
        'user_message': user_message,
        'vault_id': vault_id,
        'conversation_id': conversation_id,
        'rag_documents': [],
        'rag_entities': [],
        'total_context_tokens': 0,
        'agent_responses': {},
        'agents_completed': [],
        'mechanic_veto_active': False,
        'user_approved': False
    }

    # Execute graph
    config = {"configurable": {"thread_id": str(conversation_id)}}
    result = await graph.ainvoke(initial_state, config)

    return result['final_output']
```

**Benefits:**
- ✅ **Visual debugging** (export graph as diagram)
- ✅ **State persistence** (resume after crashes)
- ✅ **Conditional routing** (mechanic veto, etc.)
- ✅ **Parallel execution** (agents run concurrently)
- ✅ **Automatic checkpointing** (can resume multi-day workflows)

---

### 2.2 Streaming Output with LangGraph

**File:** `src/writeros/cli/main.py`

```python
@app.command()
def chat(
    message: str = typer.Argument(...),
    vault_id: str = typer.Option(None),
    stream: bool = typer.Option(True, help="Stream output in real-time")
):
    """Chat with orchestrator (streaming enabled)"""
    import asyncio
    from uuid import UUID
    from writeros.workflows.orchestrator_graph import build_orchestrator_graph

    async def _run():
        graph = build_orchestrator_graph()

        initial_state = {
            'user_message': message,
            'vault_id': UUID(vault_id),
            'conversation_id': UUID(),  # New conversation
            'rag_documents': [],
            'rag_entities': [],
            'agent_responses': {},
            'agents_completed': []
        }

        config = {"configurable": {"thread_id": str(UUID())}}

        if stream:
            # Stream state updates in real-time
            print("\nThinking...\n")

            async for event in graph.astream(initial_state, config):
                # Event structure: {node_name: node_output}
                for node_name, node_output in event.items():
                    if node_name == "rag_retrieval":
                        print(f"📚 Retrieved {len(node_output.get('rag_documents', []))} documents")
                    elif node_name == "agent_router":
                        agents = node_output.get('agents_to_invoke', [])
                        print(f"🤖 Invoking agents: {', '.join(agents)}")
                    elif node_name == "parallel_execution":
                        completed = len(node_output.get('agents_completed', []))
                        print(f"✓ {completed} agents completed")
                    elif node_name == "combine_outputs":
                        print("\n" + node_output['final_output'])
        else:
            # Non-streaming (wait for complete result)
            result = await graph.ainvoke(initial_state, config)
            print(result['final_output'])

    asyncio.run(_run())
```

**User Experience:**
```bash
$ writeros chat "Tell me about Jon Snow's journey" --vault-id xxx

Thinking...

📚 Retrieved 12 documents
🤖 Invoking agents: chronologist, psychologist, architect, navigator
✓ 4 agents completed

## 📊 SYSTEMATIC ANALYSIS

### ⏱️ TIMELINE ANALYSIS
**Events Identified:** 3
1. **Jon joins Night's Watch** (Order: 1)
...

## 💬 NARRATIVE SUMMARY

Jon Snow's journey represents...
```

---

### 2.3 Tool Calling with LangChain

**File:** `src/writeros/tools/vault_tools.py` (NEW)

```python
from langchain_core.tools import tool
from typing import Optional, List
from uuid import UUID
from writeros.schema import Document, Entity
from writeros.utils.db import engine
from sqlmodel import Session, select
import structlog

logger = structlog.get_logger()

@tool
def search_vault(query: str, vault_id: str, limit: int = 5) -> List[str]:
    """
    Search vault for relevant documents.

    Args:
        query: Search query
        vault_id: UUID of vault to search
        limit: Maximum results to return

    Returns:
        List of document contents
    """
    from writeros.rag.retriever import RAGRetriever

    retriever = RAGRetriever()
    results = retriever.retrieve(
        query=query,
        vault_id=UUID(vault_id),
        limit=limit
    )

    return [d.content for d in results.documents]

@tool
def get_character_info(character_name: str, vault_id: str) -> str:
    """
    Get information about a specific character.

    Args:
        character_name: Name of character
        vault_id: UUID of vault

    Returns:
        Character information as text
    """
    with Session(engine) as session:
        entity = session.exec(
            select(Entity)
            .where(Entity.name == character_name)
            .where(Entity.vault_id == UUID(vault_id))
        ).first()

        if not entity:
            return f"Character '{character_name}' not found"

        return f"""
        Name: {entity.name}
        Type: {entity.type}
        Description: {entity.description}
        """

@tool
def create_note(title: str, content: str, vault_path: str) -> str:
    """
    Create a new note in the vault.

    Args:
        title: Note title (becomes filename)
        content: Note content (markdown)
        vault_path: Path to vault directory

    Returns:
        Confirmation message
    """
    import os
    from pathlib import Path

    # Sanitize filename
    filename = title.replace(' ', '_').replace('/', '_') + '.md'
    filepath = Path(vault_path) / filename

    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n{content}")

    logger.info("note_created", path=str(filepath))
    return f"Created note: {filename}"

# Tool registry
VAULT_TOOLS = [
    search_vault,
    get_character_info,
    create_note
]
```

**Usage in Agent:**
```python
class ProducerAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_name="gpt-4o")

        # Bind tools to model
        self.model_with_tools = self.llm.model.bind_tools(VAULT_TOOLS)

        # Build chain with tools
        self.chain = self._build_chain()

    def _build_chain(self):
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a project manager. Use tools to interact with the vault."),
            ("user", "{query}")
        ])

        chain = prompt | self.model_with_tools

        return chain

    async def run(self, query: str, vault_id: UUID):
        """Execute with tool calling"""
        result = await self.chain.ainvoke({
            'query': query,
            'vault_id': str(vault_id)
        })

        # Check if tools were called
        if result.tool_calls:
            # Execute tools
            from langgraph.prebuilt import ToolNode
            tool_node = ToolNode(VAULT_TOOLS)

            tool_results = await tool_node.ainvoke(result)
            return tool_results
        else:
            return result.content
```

---

## 📈 Phase 3: Advanced Features (Week 3-4)

### 3.1 Human-in-the-Loop with LangGraph

**(Already covered in APPROVED_REFACTOR_PLAN.md - Mechanic Veto System)**

### 3.2 LangSmith Tracing Integration

**File:** `.env`

```bash
# LangSmith Configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="your-langsmith-api-key"
LANGCHAIN_PROJECT="writeros-production"
```

**File:** `src/writeros/utils/llm_client.py`

```python
import os
from langsmith import Client

# Automatically enabled when env vars set
# No code changes needed - tracing happens automatically!

# Optional: Custom run metadata
from langsmith.run_helpers import traceable

@traceable(
    run_type="chain",
    name="chronologist_analysis",
    tags=["agent", "timeline"]
)
async def analyze_timeline(query: str):
    # This function will be traced in LangSmith
    pass
```

**Benefits:**
- ✅ Automatic trace logging for every LLM call
- ✅ Latency tracking
- ✅ Token usage analytics
- ✅ Error tracking
- ✅ Chain visualization

---

### 3.3 Retrieval-Augmented Generation (RAG) with LCEL

**File:** `src/writeros/rag/lcel_retriever.py` (NEW)

```python
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores.pgvector import PGVector
from writeros.utils.embeddings import get_embedding_service

class LCELRAGChain:
    """RAG chain using LCEL composition"""

    def __init__(self, vault_id: UUID):
        self.vault_id = vault_id
        self.embeddings = get_embedding_service()

        # Vector store
        self.vectorstore = PGVector(
            collection_name=str(vault_id),
            connection_string=os.getenv("DATABASE_URL"),
            embedding_function=self.embeddings
        )

        # Build chain
        self.chain = self._build_chain()

    def _build_chain(self):
        """Build RAG chain with LCEL"""

        # Retriever as runnable
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})

        # Prompt template
        template = """Answer the question based on the following context:

        Context:
        {context}

        Question: {question}

        Answer:"""

        prompt = ChatPromptTemplate.from_template(template)

        # Model
        from langchain_openai import ChatOpenAI
        model = ChatOpenAI(model="gpt-4o")

        # Build RAG chain
        chain = (
            {
                "context": retriever | (lambda docs: "\n\n".join([d.page_content for d in docs])),
                "question": RunnablePassthrough()
            }
            | prompt
            | model
            | StrOutputParser()
        )

        return chain

    async def ask(self, question: str) -> str:
        """Ask question with RAG"""
        return await self.chain.ainvoke(question)
```

**Usage:**
```python
# Simple RAG query
rag = LCELRAGChain(vault_id)
answer = await rag.ask("What is Jon Snow's character arc?")
```

---

### 3.4 Multi-Turn Conversations with Checkpointing

**File:** `src/writeros/workflows/conversation_graph.py` (NEW)

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, AIMessage
from typing import TypedDict, List

class ConversationState(TypedDict):
    messages: List
    vault_id: str
    conversation_id: str

async def process_message_node(state: ConversationState):
    """Process user message with context"""
    from writeros.workflows.orchestrator_graph import build_orchestrator_graph

    # Get last user message
    last_message = state['messages'][-1].content

    # Run orchestrator
    orchestrator = build_orchestrator_graph()
    result = await orchestrator.ainvoke({
        'user_message': last_message,
        'vault_id': UUID(state['vault_id']),
        'conversation_id': UUID(state['conversation_id']),
        # ... other fields
    })

    # Add AI response to messages
    state['messages'].append(AIMessage(content=result['final_output']))
    return state

def build_conversation_graph():
    """Multi-turn conversation with memory"""
    checkpointer = SqliteSaver.from_conn_string(".writeros/conversations.db")

    workflow = StateGraph(ConversationState)
    workflow.add_node("process", process_message_node)
    workflow.set_entry_point("process")
    workflow.add_edge("process", END)

    return workflow.compile(checkpointer=checkpointer)

# Usage
graph = build_conversation_graph()
config = {"configurable": {"thread_id": "user_123_conversation_456"}}

# Turn 1
await graph.ainvoke({
    "messages": [HumanMessage(content="Tell me about Jon Snow")],
    "vault_id": str(vault_id),
    "conversation_id": str(conv_id)
}, config)

# Turn 2 (remembers Turn 1)
await graph.ainvoke({
    "messages": [HumanMessage(content="What about his relationship with Ygritte?")],
    "vault_id": str(vault_id),
    "conversation_id": str(conv_id)
}, config)
```

---

## 🎯 Complete Migration Checklist

### Week 1: LangChain Foundation
- [ ] Install LangChain ecosystem packages
- [ ] Replace LLMClient with LangChain native
- [ ] Add PostgresChatHistory for memory
- [ ] Convert 1 agent to LCEL (ChronologistAgent)
- [ ] Test streaming output
- [ ] Enable LangSmith tracing

### Week 2: LangGraph Core
- [ ] Build orchestrator state graph
- [ ] Migrate RAG retrieval to graph node
- [ ] Implement parallel agent execution
- [ ] Add structured summary node
- [ ] Test graph checkpointing
- [ ] Visualize graph (export diagram)

### Week 3: Tools & Advanced
- [ ] Create vault tools (@tool decorators)
- [ ] Bind tools to ProducerAgent
- [ ] Implement LCEL RAG chain
- [ ] Add multi-turn conversation graph
- [ ] Test tool calling end-to-end

### Week 4: Mechanic Veto (Human-in-Loop)
- [ ] Build mechanic validation node
- [ ] Add user review pause point
- [ ] Implement revision cycle
- [ ] Test checkpoint resume
- [ ] Deploy to production

---

## 📊 Benefits Summary

| Feature | Before | After | Benefit |
|---------|--------|-------|---------|
| **Streaming** | Manual chunks | Built-in `.astream()` | Real-time UX |
| **Memory** | Manual DB queries | LangChain memory | Auto conversation history |
| **Tools** | Custom implementation | `@tool` decorator | LLM can call functions |
| **Structured Output** | Regex parsing | Pydantic parser | Type-safe responses |
| **Orchestration** | `asyncio.gather()` | LangGraph | Visual debugging |
| **Checkpointing** | None | SQLite checkpointer | Resume workflows |
| **Tracing** | Manual logging | LangSmith | Automatic observability |
| **Composability** | Monolithic | LCEL chains | Reusable components |

---

## 🚀 Next Steps

1. **Install dependencies:**
   ```bash
   pip install langchain langgraph langchain-openai langsmith langgraph-checkpoint-sqlite
   ```

2. **Set up LangSmith** (optional but recommended):
   ```bash
   export LANGCHAIN_TRACING_V2=true
   export LANGCHAIN_API_KEY=your_key
   ```

3. **Start migration:**
   - Begin with LLMClient refactor (Week 1, Day 1)
   - Convert one agent to LCEL as proof-of-concept
   - Test streaming before moving to LangGraph

**Ready to implement?** Let me know and I'll start with Phase 1!
