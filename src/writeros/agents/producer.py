import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from sqlalchemy.sql import column
from sqlalchemy.sql.expression import func
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base import BaseAgent, logger
from writeros.schema import Document, Entity, Fact, Relationship, EntityType
from writeros.utils.db import engine
from writeros.utils.embeddings import get_embedding_service

class ProducerAgent(BaseAgent):
    def __init__(self, model_name="gpt-4o", vault_root: Optional[str] = None, enable_tools: bool = True):
        super().__init__(model_name)

        self.repo_root = Path(__file__).resolve().parent.parent.parent.parent
        self.sample_vault_root = self.repo_root / "sample_data" / "sample_vault"
        self.default_vault_root = Path(vault_root) if vault_root else Path(r"C:\Users\rahme\Desktop\Genius Loci")

        self._set_vault_root(self._resolve_vault_root(self.default_vault_root))

        # Bind LangChain tools if enabled
        self.tools_enabled = enable_tools
        if enable_tools:
            try:
                from writeros.agents.langgraph_tools import PRODUCER_TOOLS
                self.llm_with_tools = self.llm.client.bind_tools(PRODUCER_TOOLS)
                self.log.info("producer_tools_bound", num_tools=len(PRODUCER_TOOLS))
            except ImportError:
                self.log.warning("langgraph_tools_not_available", fallback="tool_calling_disabled")
                self.llm_with_tools = self.llm.client
                self.tools_enabled = False
        else:
            self.llm_with_tools = self.llm.client

        self.log.info("producer_initialized", vault_root=str(self.vault_root), tools_enabled=self.tools_enabled)

    def _set_vault_root(self, vault_root: Path) -> None:
        self.vault_root = vault_root
        self.project_bible_path = self.vault_root / "00_Project_Bible"
        self.story_bible_path = self.vault_root / "01_Story_Bible"

    def _resolve_vault_root(self, preferred_root: Optional[Path]) -> Path:
        """Pick the best available vault root, falling back to sample data."""
        candidate_root = preferred_root or self.default_vault_root
        if candidate_root and candidate_root.exists():
            return candidate_root

        if self.sample_vault_root.exists():
            self.log.warning("preferred_vault_not_found", preferred=str(candidate_root), fallback=str(self.sample_vault_root))
            return self.sample_vault_root

        self.log.warning("no_vault_found", preferred=str(candidate_root))
        return candidate_root

    # ============================================
    # 📂 FILE LOADING UTILITIES
    # ============================================
    
    def _load_file(self, filepath: str) -> str:
        """Load a single markdown file with error handling"""
        try:
            path = Path(filepath)
            if not path.exists():
                self.log.warning("file_not_found", filepath=filepath)
                return f"[File not found: {filepath}]"
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.log.error("error_loading_file", filepath=filepath, error=str(e))
            return f"[Error loading file: {e}]"
    
    def _load_project_context(self) -> str:
        """Load Project Bible files (Dogfooding Mode)"""
        self.log.info("loading_project_bible")
        
        # ✅ HYBRID FIX: Keep the comprehensive file list
        files_to_load = [
            "WriterOS_Architecture_V2.5_COMPLETE.md",
            "Roadmap.md",
            "Backlog.md",
            "V2.5_CHANGES_SUMMARY.md",
            "Producer_5_Modes_Quick_Reference.md",
        ]
        
        context_parts = []
        for filename in files_to_load:
            filepath = self.project_bible_path / filename
            if filepath.exists():
                content = self._load_file(str(filepath))
                context_parts.append(f"# {filename}\n\n{content}\n\n---\n")
        
        return "\n".join(context_parts)
    
    def _load_story_context(self) -> str:
        """Load Story Bible files for novel queries"""
        self.log.info("loading_story_bible")
        
        context_parts = []
        if self.story_bible_path.exists():
            for md_file in self.story_bible_path.glob("**/*.md"):
                content = self._load_file(str(md_file))
                context_parts.append(f"# {md_file.name}\n\n{content}\n\n---\n")
        
        return "\n".join(context_parts)
    
    async def _detect_context_type(self, question: str) -> str:
        """Use LLM to classify whether question is about project or story"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Classify this query as either 'project' or 'story':
            - project: Questions about development, implementation, roadmap, agents, code, architecture, WriterOS features
            - story: Questions about characters, plot, world-building, narrative, chapters, novel content
            Reply with ONLY one word: 'project' or 'story'"""),
            ("user", f"Query: {question}")
        ])
        chain = prompt | self.llm.client | StrOutputParser()
        result = await chain.ainvoke({})
        return result.strip().lower()
    
    async def _load_targeted_context(self, query: str) -> str:
        """Smart context loading based on semantic analysis"""
        context_type = await self._detect_context_type(query)
        
        if context_type == "project":
            self.log.info("project_query_detected")
            return self._load_project_context()
        else:
            self.log.info("story_query_detected")
            return self._load_story_context()
   
    # ============================================
    # 🎬 MAIN ORCHESTRATOR
    # ============================================

    async def run(self, full_text: str, existing_notes: str, title: str):
        """Standard entry point for Orchestrator."""
        self.log.info("running_producer", title=title)
        # If existing_notes are provided, use them as context for a consult
        if existing_notes:
            return await self.consult(full_text, existing_notes)
        # Otherwise, run the full query pipeline
        return await self.query(full_text)

    async def run_with_tools(self, user_message: str, context: str, vault_id: str) -> Dict[str, Any]:
        """
        Enhanced run method that uses tool-augmented LLM.

        This allows the ProducerAgent to autonomously call tools like:
        - search_vault: Search for specific information
        - create_note: Create character sheets, documentation
        - get_entity_details: Deep dive into entities

        Args:
            user_message: User's query
            context: RAG context from retriever
            vault_id: Vault ID for tool calls

        Returns:
            Dict with analysis and any tool_calls made
        """
        if not self.tools_enabled:
            # Fallback to regular query
            result = await self.consult(user_message, context)
            return {"analysis": result, "tool_calls": []}

        self.log.info("producer_running_with_tools", query=user_message[:100])

        # Create prompt that encourages tool use
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Producer Agent with access to powerful tools.

You can autonomously call tools to gather information or create content:
- search_vault: Find specific information in the vault
- get_entity_details: Get comprehensive entity information
- create_note: Create new notes (character sheets, documentation)
- list_vault_entities: Browse available entities

Use tools when they would provide better answers than the context alone.

Context:
{context}"""),
            ("user", "{query}")
        ])

        # Invoke LLM with tools
        chain = prompt | self.llm_with_tools
        result = await chain.ainvoke({"context": context, "query": user_message, "vault_id": vault_id})

        # Check if LLM wants to call tools
        if hasattr(result, "tool_calls") and result.tool_calls:
            self.log.info("producer_tool_calls_requested", num_calls=len(result.tool_calls))
            return {
                "analysis": result.content if hasattr(result, "content") else str(result),
                "tool_calls": result.tool_calls,
                "wants_tools": True
            }
        else:
            # No tool calls, return analysis
            return {
                "analysis": result.content if hasattr(result, "content") else str(result),
                "tool_calls": [],
                "wants_tools": False
            }
    
    async def query(self, question: str, mode: Optional[str] = None, vault_path: Optional[str] = None) -> str:
        """Main entry point for Producer queries."""
        self.log.info("producer_query_received", question=question)

        active_root = self._resolve_vault_root(Path(vault_path) if vault_path else self.default_vault_root)
        self._set_vault_root(active_root)
        
        if mode is None:
            mode = await self._detect_mode(question)
            self.log.info("mode_auto_detected", mode=mode)

        if mode == "local":
            return await self._local_vector_search(question)
        
        elif mode == "global":
            context = await self._load_targeted_context(question)
            return await self.global_view(question, context)
        
        elif mode == "drift":
            context = await self._load_targeted_context(question)
            return await self.drift_search(question, context)
        
        elif mode == "sql":
            criteria = await self._parse_sql_query(question)
            return await self.structured_query(criteria, vault_path)    
        
        elif mode == "traversal":
            nodes = await self._parse_traversal_query(question)
            return await self.agentic_traversal(nodes["start"], nodes["end"], vault_path)
        
        else:
            context = await self._load_targeted_context(question)
            return await self.consult(question, context)

    async def _local_vector_search(self, query: str, limit: int = 5) -> str:
        """Semantic search over Facts and Documents using vector similarity."""
        self.log.info("running_local_vector_search", query=query)

        embedding = get_embedding_service().embed_query(query)

        with Session(engine) as session:
            facts = session.exec(
                select(Fact)
                .order_by(Fact.embedding.cosine_distance(embedding))
                .limit(limit)
            ).all()

            documents = session.exec(
                select(Document)
                .order_by(Document.embedding.cosine_distance(embedding))
                .limit(limit)
            ).all()

        if not facts and not documents:
            return "No relevant information found in local vector search."

        sections = []

        if facts:
            formatted_facts = []
            for fact in facts:
                source = f" (source: {fact.source})" if fact.source else ""
                formatted_facts.append(f"- ({fact.fact_type}) {fact.content}{source}")
            sections.append("📌 Facts:\n" + "\n".join(formatted_facts))

        if documents:
            formatted_docs = []
            for doc in documents:
                snippet = doc.content[:200] + ("..." if len(doc.content) > 200 else "")
                formatted_docs.append(f"- {doc.title} [{doc.doc_type}]: {snippet}")
            sections.append("📄 Documents:\n" + "\n".join(formatted_docs))

        return "\n\n".join(sections)

    # ============================================
    # 🧠 INTELLIGENCE LAYER
    # ============================================

    async def _detect_mode(self, question: str) -> str:
        """Use LLM to classify query intent"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Classify this query into ONE mode (reply with just the word):
            - global: Project status, summaries, "what should I work on"
            - drift: What-if scenarios, causal analysis, logic problems
            - sql: Filters, "list all X with property Y"
            - traversal: "How does A connect to B", relationship paths
            - local: Specific fact lookup
            Reply with ONLY the mode name."""),
            ("user", f"Query: {question}")
        ])
        chain = prompt | self.llm.client | StrOutputParser()
        result = await chain.ainvoke({})
        return result.strip().lower()
    
    async def _parse_sql_query(self, question: str) -> Dict[str, str]:
        """Convert natural language to SQL criteria"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Convert this question to SQL criteria.
            Return JSON with: {"type": "character|location|faction", "key": "property_name", "value": "property_value"}
            Example: "List all villains" -> {"type": "character", "key": "role", "value": "unknown"}
            """),
            ("user", f"Query: {question}")
        ])
        chain = prompt | self.llm.client | StrOutputParser()
        result = await chain.ainvoke({})
        try:
            clean_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_result)
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.warning(
                "structured_query_parse_failed",
                error=str(e),
                error_type=type(e).__name__,
                raw_result=result[:200] if result else None,
                returning_default=True
            )
            return {"type": "character", "key": "role", "value": "unknown"}
    
    async def _parse_traversal_query(self, question: str) -> Dict[str, str]:
        """Extract start and end nodes"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract the two entities. Return JSON: {"start": "Entity A", "end": "Entity B"}"""),
            ("user", f"Query: {question}")
        ])
        chain = prompt | self.llm.client | StrOutputParser()
        result = await chain.ainvoke({})
        try:
            clean_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_result)
        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            logger.warning(
                "traversal_query_parse_failed",
                error=str(e),
                error_type=type(e).__name__,
                raw_result=result[:200] if result else None,
                returning_default=True
            )
            return {"start": "Unknown", "end": "Unknown"}

    # ============================================
    # 💬 CHAT & DRIFT
    # ============================================

    async def consult(self, query: str, context: str) -> str:
        """Standard Chat using RAG Context."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the WriterOS Producer. Answer based strictly on the context provided.
            ### CONTEXT:
            {context}"""),
            ("user", "{query}")
        ])
        chain = prompt | self.llm.client | StrOutputParser()
        return await chain.ainvoke({"context": context, "query": query})

    async def global_view(self, query: str, context: str) -> str:
        """High-level project analysis."""
        self.log.info("executing_global_view")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Executive Producer. Analyze the project state.
            ### GLOBAL CONTEXT:
            {context}"""),
            ("user", "{query}")
        ])
        chain = prompt | self.llm.client | StrOutputParser()
        return await chain.ainvoke({"context": context, "query": query})

    async def drift_search(self, problem: str, vault_context: str) -> str:
        """Logic/Causality Solver."""
        self.log.info("running_drift_search", problem=problem)
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Narrative Forensic Analyst.
            Solve the plot hole by tracing Relationships and Psychology.
            1. Identify Nodes. 2. Trace Edges (Leverage/Motive). 3. Find Path.
            ### CONTEXT:
            {context}"""),
            ("user", f"PROBLEM: {problem}")
        ])
        chain = prompt | self.llm.client | StrOutputParser()
        return await chain.ainvoke({"context": vault_context})

    # ============================================
    # 📊 STRUCTURED QUERY (SQL)
    # ============================================

    async def structured_query(self, criteria: Dict[str, str], vault=None) -> str:
        """Executes a real SQL query against Postgres."""
        self.log.info("executing_sql_query", criteria=criteria)
        entity_type = criteria.get("type")
        key = criteria.get("key")
        value = criteria.get("value")

        with Session(engine) as session:
            statement = select(Entity)
            if entity_type:
                statement = statement.where(Entity.type == entity_type.lower())
            if key and value:
                # ✅ HYBRID FIX: Use SQLAlchemy column helpers for JSONB querying
                properties_column = column("properties")
                json_value = func.json_extract_path_text(properties_column, key)
                statement = statement.where(json_value.ilike(f"%{value}%"))

            results = session.exec(statement).all()
            if not results: return "No entities found matching criteria in Database."
            names = [e.name for e in results]
            return f"Found {len(names)} matches in DB: {', '.join(names)}"

        if mode == "local":
            return await self._local_vector_search(question)
        
        elif mode == "global":
            context = await self._load_targeted_context(question)
            return await self.global_view(question, context)
        
        elif mode == "drift":
            context = await self._load_targeted_context(question)
            return await self.drift_search(question, context)
        
        elif mode == "sql":
            criteria = await self._parse_sql_query(question)
            return await self.structured_query(criteria, vault_path)    
        
        elif mode == "traversal":
            nodes = await self._parse_traversal_query(question)
            return await self.agentic_traversal(nodes["start"], nodes["end"], vault_path)
        visited = {current_node}
        max_steps = 6

        with Session(engine) as session:
            for i in range(max_steps):
                if current_node == end_node_name: break
                
                # 1. Get ID of current node
                node_obj = session.exec(select(Entity).where(Entity.name == current_node)).first()
                if not node_obj: return f"❌ Node '{current_node}' not found in Database."

                # 2. Get Neighbors
                rels = session.exec(select(Relationship).where(
                    (Relationship.source_entity_id == node_obj.id) |
                    (Relationship.target_entity_id == node_obj.id)
                )).all()
                if not rels: return f"Dead end at {current_node}."

                # 3. Resolve Neighbor Names
                neighbor_names = []
                for r in rels:
                    neighbor_id = r.target_entity_id if r.source_entity_id == node_obj.id else r.source_entity_id
                    n_obj = session.get(Entity, neighbor_id)
                    if n_obj: neighbor_names.append(n_obj.name)

                # 4. AI Decides next step
                decision_prompt = ChatPromptTemplate.from_messages([
                    ("system", "Pick the neighbor most likely to lead to the target."),
                    ("user", f"Current: {current_node}\nTarget: {end_node_name}\nNeighbors: {neighbor_names}\n\nReturn ONLY the name.")
                ])
                next_step = (await (decision_prompt | self.llm.client | StrOutputParser()).ainvoke({})).strip()

                if next_step in visited: return f"Loop detected at {next_step}. Traversal failed."
                
                current_node = next_step
                path.append(current_node)
                visited.add(current_node)
                
                if current_node == end_node_name: return f"✅ Path Found in DB: {' -> '.join(path)}"

        return f"❌ Max steps reached. Path: {' -> '.join(path)}"