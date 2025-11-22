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
from .schema import Document, Entity, Fact, Relationship, EntityType
from utils.db import engine
from utils.embeddings import embedding_service

class ProducerAgent(BaseAgent):
    def __init__(self, model_name="gpt-4o", vault_root: Optional[str] = None):
        super().__init__(model_name)

        self.repo_root = Path(__file__).resolve().parent.parent
        self.sample_vault_root = self.repo_root / "sample_data" / "sample_vault"
        self.default_vault_root = Path(vault_root) if vault_root else Path(r"C:\Users\rahme\Desktop\Genius Loci")

        self._set_vault_root(self._resolve_vault_root(self.default_vault_root))

        logger.info(f"📁 Producer initialized with vault: {self.vault_root}")

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
            logger.warning(
                f"Preferred vault '{candidate_root}' not found. Falling back to sample vault at {self.sample_vault_root}."
            )
            return self.sample_vault_root

        logger.warning(f"Preferred vault '{candidate_root}' not found and no sample vault available.")
        return candidate_root

    # ============================================
    # 📂 FILE LOADING UTILITIES
    # ============================================
    
    def _load_file(self, filepath: str) -> str:
        """Load a single markdown file with error handling"""
        try:
            path = Path(filepath)
            if not path.exists():
                logger.warning(f"File not found: {filepath}")
                return f"[File not found: {filepath}]"
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return f"[Error loading file: {e}]"
    
    def _load_project_context(self) -> str:
        """Load Project Bible files (Dogfooding Mode)"""
        logger.info("📚 Loading Project Bible for Global View...")
        
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
        logger.info("📖 Loading Story Bible...")
        
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
        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({})
        return result.strip().lower()
    
    async def _load_targeted_context(self, query: str) -> str:
        """Smart context loading based on semantic analysis"""
        context_type = await self._detect_context_type(query)
        
        if context_type == "project":
            logger.info("🐕 Project query detected - loading Project Bible")
            return self._load_project_context()
        else:
            logger.info("📖 Story query detected - loading Story Bible")
            return self._load_story_context()
   
    # ============================================
    # 🎬 MAIN ORCHESTRATOR
    # ============================================
    
    async def query(self, question: str, mode: Optional[str] = None, vault_path: Optional[str] = None) -> str:
        """Main entry point for Producer queries."""
        logger.info(f"🎬 Producer received query: {question}")

        active_root = self._resolve_vault_root(Path(vault_path) if vault_path else self.default_vault_root)
        self._set_vault_root(active_root)
        
        if mode is None:
            mode = await self._detect_mode(question)
            logger.info(f"🤖 Auto-detected mode: {mode}")

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
        logger.info(f"🔎 Producer running local vector search for: {query}")

        embedding = embedding_service.embed_query(query)

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
        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({})
        return result.strip().lower()
    
    async def _parse_sql_query(self, question: str) -> Dict[str, str]:
        """Convert natural language to SQL criteria"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Convert this question to SQL criteria.
            Return JSON with: {"type": "character|location|faction", "key": "property_name", "value": "property_value"}
            Example: "List all villains" -> {"type": "character", "key": "role", "value": "villain"}
            """),
            ("user", f"Query: {question}")
        ])
        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({})
        try: 
            clean_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_result)
        except: 
            return {"type": "character", "key": "role", "value": "unknown"}
    
    async def _parse_traversal_query(self, question: str) -> Dict[str, str]:
        """Extract start and end nodes"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extract the two entities. Return JSON: {"start": "Entity A", "end": "Entity B"}"""),
            ("user", f"Query: {question}")
        ])
        chain = prompt | self.llm | StrOutputParser()
        result = await chain.ainvoke({})
        try: 
            clean_result = result.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_result)
        except: 
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
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"context": context, "query": query})

    async def global_view(self, query: str, context: str) -> str:
        """High-level project analysis."""
        logger.info("🌍 Producer executing Global View...")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Executive Producer. Analyze the project state.
            ### GLOBAL CONTEXT:
            {context}"""),
            ("user", "{query}")
        ])
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"context": context, "query": query})

    async def drift_search(self, problem: str, vault_context: str) -> str:
        """Logic/Causality Solver."""
        logger.info(f"🕵️ Producer running Drift Search on: {problem}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Narrative Forensic Analyst.
            Solve the plot hole by tracing Relationships and Psychology.
            1. Identify Nodes. 2. Trace Edges (Leverage/Motive). 3. Find Path.
            ### CONTEXT:
            {context}"""),
            ("user", f"PROBLEM: {problem}")
        ])
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({"context": vault_context})

    # ============================================
    # 📊 STRUCTURED QUERY (SQL)
    # ============================================

    async def structured_query(self, criteria: Dict[str, str], vault=None) -> str:
        """Executes a real SQL query against Postgres."""
        logger.info(f"📊 Producer executing SQL Query: {criteria}")
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

    # ============================================
    # 🕸️ GRAPH TRAVERSAL
    # ============================================

    async def agentic_traversal(self, start_node_name: str, end_node_name: str, vault=None) -> str:
        """Walks the graph using SQL Relationships table."""
        logger.info(f"👣 Producer walking DB Graph: {start_node_name} -> {end_node_name}")
        current_node = start_node_name
        path = [current_node]
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
                    (Relationship.from_entity_id == node_obj.id) |
                    (Relationship.to_entity_id == node_obj.id)
                )).all()
                if not rels: return f"Dead end at {current_node}."

                # 3. Resolve Neighbor Names
                neighbor_names = []
                for r in rels:
                    neighbor_id = r.to_entity_id if r.from_entity_id == node_obj.id else r.from_entity_id
                    n_obj = session.get(Entity, neighbor_id)
                    if n_obj: neighbor_names.append(n_obj.name)

                # 4. AI Decides next step
                decision_prompt = ChatPromptTemplate.from_messages([
                    ("system", "Pick the neighbor most likely to lead to the target."),
                    ("user", f"Current: {current_node}\nTarget: {end_node_name}\nNeighbors: {neighbor_names}\n\nReturn ONLY the name.")
                ])
                next_step = (await (decision_prompt | self.llm | StrOutputParser()).ainvoke({})).strip()

                if next_step in visited: return f"Loop detected at {next_step}. Traversal failed."
                
                current_node = next_step
                path.append(current_node)
                visited.add(current_node)
                
                if current_node == end_node_name: return f"✅ Path Found in DB: {' -> '.join(path)}"

        return f"❌ Max steps reached. Path: {' -> '.join(path)}"