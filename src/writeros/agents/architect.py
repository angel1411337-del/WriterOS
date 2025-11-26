from typing import Optional, List, Dict, Any
from uuid import UUID
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .base import BaseAgent, logger
from sqlmodel import Session, select
from writeros.utils import db as db_utils
from writeros.utils.embeddings import get_embedding_service
from writeros.schema import Document, Event, Anchor, AnchorStatus, Fact, Relationship, Entity
from writeros.services.conflict_engine import ConflictEngine
from writeros.schema.enums import ConflictStatus
import networkx as nx
from collections import deque

class ArchitectAgent(BaseAgent):
    def __init__(self, model_name="gpt-5.1"):
        super().__init__(model_name)
        self.conflict_engine = ConflictEngine()

    async def list_anchors(self, status: Optional[AnchorStatus] = None) -> List[Anchor]:
        """
        Retrieves a list of anchors, optionally filtered by status.
        """
        self.log.info("listing_anchors", status=status)
        with Session(engine) as session:
            statement = select(Anchor)
            if status:
                statement = statement.where(Anchor.status == status)
            return session.exec(statement).all()

    async def check_anchor_prerequisites(self, anchor_id: UUID) -> Dict[str, Any]:
        """
        Checks if an Anchor's prerequisites are met by querying the database.
        Updates the anchor's status based on progress.
        
        Returns a status report with details on which prerequisites are met.
        """
        self.log.info("checking_prerequisites", anchor_id=str(anchor_id))
        
        with Session(engine) as session:
            # Fetch the anchor
            anchor = session.get(Anchor, anchor_id)
            if not anchor:
                return {"error": f"Anchor {anchor_id} not found"}
            
            prerequisites = anchor.prerequisites
            if not prerequisites:
                return {
                    "anchor_id": str(anchor_id),
                    "anchor_name": anchor.name,
                    "prerequisites": [],
                    "prerequisites_met": 0,
                    "prerequisites_total": 0,
                    "status": anchor.status
                }
            
            met_count = 0
            total_count = len(prerequisites)
            results = []
            
            for prereq in prerequisites:
                prereq_type = prereq.get("type")
                is_met = False
                details = {}
                
                if prereq_type == "fact":
                    # Check if a Fact exists matching the criteria
                    entity_name = prereq.get("entity")
                    content_pattern = prereq.get("content", "")
                    
                    # Find entity by name
                    entity = session.exec(
                        select(Entity).where(Entity.name == entity_name)
                    ).first()
                    
                    if entity:
                        # Search for matching fact
                        facts = session.exec(
                            select(Fact).where(Fact.entity_id == entity.id)
                        ).all()
                        
                        # Simple substring match for now (could use semantic search later)
                        for fact in facts:
                            if content_pattern.lower() in fact.content.lower():
                                is_met = True
                                details = {"found_fact": fact.content}
                                break
                
                elif prereq_type == "relationship":
                    # Check if a Relationship exists
                    from_name = prereq.get("from")
                    to_name = prereq.get("to")
                    rel_status = prereq.get("status")  # Could be a property value
                    
                    # Find entities
                    from_entity = session.exec(
                        select(Entity).where(Entity.name == from_name)
                    ).first()
                    to_entity = session.exec(
                        select(Entity).where(Entity.name == to_name)
                    ).first()
                    
                    if from_entity and to_entity:
                        # Find relationship
                        rels = session.exec(
                            select(Relationship).where(
                                (Relationship.from_entity_id == from_entity.id) &
                                (Relationship.to_entity_id == to_entity.id)
                            )
                        ).all()
                        
                        if rels:
                            # If status is specified, check properties
                            if rel_status:
                                for rel in rels:
                                    if rel.properties.get("status") == rel_status:
                                        is_met = True
                                        details = {"found_relationship": str(rel.rel_type)}
                                        break
                            else:
                                is_met = True
                                details = {"found_relationship": str(rels[0].rel_type)}
                
                elif prereq_type == "event":
                    # Check if an Event exists matching the name
                    event_name = prereq.get("name")
                    events = session.exec(
                        select(Event).where(Event.name == event_name)
                    ).all()
                    
                    if events:
                        is_met = True
                        details = {"found_event": event_name}
                
                if is_met:
                    met_count += 1
                
                results.append({
                    "prerequisite": prereq,
                    "is_met": is_met,
                    "details": details
                })
            
            # Update anchor
            anchor.prerequisites_met = met_count
            anchor.prerequisites_total = total_count
            
            # Update status based on progress
            if met_count == total_count:
                anchor.status = AnchorStatus.ON_TRACK
            elif met_count >= total_count * 0.5:
                anchor.status = AnchorStatus.ON_TRACK
            else:
                anchor.status = AnchorStatus.AT_RISK
            
            session.add(anchor)
            session.commit()
            session.refresh(anchor)
            
            return {
                "anchor_id": str(anchor_id),
                "anchor_name": anchor.name,
                "prerequisites": results,
                "prerequisites_met": met_count,
                "prerequisites_total": total_count,
                "status": anchor.status,
                "completion_percentage": (met_count / total_count * 100) if total_count > 0 else 0
            }

    async def critique_draft(self, draft_text: str, context: str) -> str:
        """
        Analyzes a draft chapter for structure, pacing, and continuity.
        Also checks against PENDING Anchors.
        """
        self.log.info("analyzing_draft_structure")

        # Fetch Pending Anchors
        pending_anchors = await self.list_anchors(status=AnchorStatus.PENDING)
        anchors_text = "No pending anchors."
        if pending_anchors:
            anchors_text = "\n".join([f"- {a.name}: {a.description}" for a in pending_anchors])

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are the Lead Editor of a high-end publishing house.
            Your goal is to critique the user's draft based on narrative structure, established Story Bible context, and PENDING ANCHORS.

            ### YOUR FOCUS:
            1. **Continuity**: Does this contradict the provided "WORLD CONTEXT"?
            2. **Pacing**: Is the scene moving too fast or too slow?
            3. **Structure**: Does the scene have a beginning, middle, and end?
            4. **Anchors**: Does this draft address or advance any of the "PENDING ANCHORS"?
            5. **Show, Don't Tell**: Flag exposition dumps.

            ### OUTPUT FORMAT:
            Use Markdown. Be concise. Group issues by category.
            If the draft is good, say so, but still offer one area for refinement.
            """),
            ("user", """
            --- WORLD CONTEXT (The Truth) ---
            {context}
            
            --- PENDING ANCHORS (Goals) ---
            {anchors}
            
            --- USER DRAFT ---
            {draft}
            """)
        ])

        chain = prompt | self.llm | StrOutputParser()

        return await chain.ainvoke({
            "context": context,
            "anchors": anchors_text,
            "draft": draft_text
        })

    async def review_anchor_progress(self, text: str) -> str:
        """
        Analyzes text to see if it satisfies any pending anchors.
        """
        self.log.info("reviewing_anchor_progress")
        
        pending_anchors = await self.list_anchors(status=AnchorStatus.PENDING)
        if not pending_anchors:
            return "No pending anchors to check against."
            
        anchors_list = "\n".join([f"ID: {a.id} | Name: {a.name} | Desc: {a.description}" for a in pending_anchors])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Narrative Tracker.
            Analyze the provided text and determine if it COMPLETES or ADVANCES any of the following Anchors.
            
            ### PENDING ANCHORS:
            {anchors}
            
            ### TEXT TO ANALYZE:
            {text}
            
            ### OUTPUT:
            Return a JSON object mapping Anchor IDs to their status update.
            Example:
            {{
                "anchor_id_1": "COMPLETED - The hero found the sword.",
                "anchor_id_2": "ADVANCED - The hero learned about the sword's location."
            }}
            If no anchors are touched, return empty JSON {{}}.
            """),
            ("user", "Analyze this text.")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke({
            "anchors": anchors_list,
            "text": text
        })

    async def find_similar_scenes(self, description: str, limit: int = 3) -> str:
        """
        Finds scenes in the database that are semantically similar to the description.
        Useful for checking if a scene has already been written or finding thematic echoes.
        """
        self.log.info("searching_similar_scenes", description=description)
        
        embedding = get_embedding_service().embed_query(description)
        
        with Session(db_utils.engine) as session:
            # Search Documents (assuming doc_type='scene' or similar)
            # We'll search all documents for now, but ideally we'd filter by doc_type
            results = session.exec(
                select(Document)
                .order_by(Document.embedding.cosine_distance(embedding))
                .limit(limit)
            ).all()
            
            if not results:
                return "No similar scenes found."
                
            formatted_results = []
            for doc in results:
                formatted_results.append(f"SCENE: {doc.title}\n{doc.content[:200]}...")
                
            return "\n\n".join(formatted_results)

    async def find_related_plot_points(self, query: str, limit: int = 5) -> str:
        """
        Finds plot points (Events) related to the query.
        """
        self.log.info("searching_related_plot_points", query=query)
        
        embedding = get_embedding_service().embed_query(query)
        
        with Session(db_utils.engine) as session:
            results = session.exec(
                select(Event)
                .order_by(Event.embedding.cosine_distance(embedding))
                .limit(limit)
            ).all()
            
            if not results:
                return "No related plot points found."
                
            formatted_results = []
            for event in results:
                formatted_results.append(f"EVENT: {event.name}\n{event.description}")
                
            return "\n\n".join(formatted_results)

    async def generate_plot_tasks(self, vault_id: UUID) -> List[str]:
        """
        Generates a Long-Term To-Do List based on active conflicts and plot anchors.
        """
        self.log.info("generating_plot_tasks", vault_id=str(vault_id))
        
        # Fetch Active Conflicts
        active_conflicts = self.conflict_engine.get_active_conflicts(vault_id)
        
        tasks = []
        
        # Logic: Check for stalled conflicts
        for conflict in active_conflicts:
            if conflict.status == ConflictStatus.RISING_ACTION:
                # In a real system, we'd check how long it's been in this state
                # For now, we assume if it's in Rising Action, it needs escalation
                tasks.append(f"Escalate Conflict '{conflict.name}' to Climax (Current Intensity: {conflict.intensity})")
            elif conflict.status == ConflictStatus.SETUP:
                tasks.append(f"Advance Conflict '{conflict.name}' to Inciting Incident")
                
        return tasks

    async def trace_causality_chain(self, event_id: UUID, max_depth: int = 10) -> Dict[str, Any]:
        """
        Traces the chain of events that led to a specific event (backward causality)
        and the events caused by it (forward causality).
        
        Args:
            event_id: The UUID of the focal event.
            max_depth: Maximum number of hops to trace.
            
        Returns:
            Dict containing 'causes' (ancestors) and 'effects' (descendants) subgraphs.
        """
        self.log.info("tracing_causality", event_id=str(event_id), max_depth=max_depth)
        
        with Session(engine) as session:
            # 1. Fetch all events to build the graph (optimization: fetch only relevant if possible, 
            # but for now fetch all for simplicity as graph size is likely manageable per vault)
            # In production, use recursive CTEs.
            target_event = session.get(Event, event_id)
            if not target_event:
                return {"error": "Event not found"}
                
            all_events = session.exec(select(Event).where(Event.vault_id == target_event.vault_id)).all()
            
            # 2. Build Graph
            G = nx.DiGraph()
            event_map = {str(e.id): e for e in all_events}
            
            for event in all_events:
                G.add_node(str(event.id), name=event.name)
                if event.causes_event_ids:
                    for caused_id in event.causes_event_ids:
                        if caused_id in event_map:
                            G.add_edge(str(event.id), caused_id)
                            
            # 3. Trace Backward (Causes)
            causes = []
            if str(event_id) in G:
                ancestors = nx.ancestors(G, str(event_id))
                # Filter by distance if needed, but nx.ancestors gets all. 
                # To respect max_depth, we can use bfs_predecessors or similar.
                # For simplicity with small depth, simple traversal:
                q = deque([(str(event_id), 0)])
                visited = {str(event_id)}
                
                # Reverse graph for backward traversal
                R = G.reverse()
                
                while q:
                    curr, depth = q.popleft()
                    if depth >= max_depth:
                        continue
                        
                    for neighbor in R.neighbors(curr):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            causes.append({
                                "id": neighbor,
                                "name": event_map[neighbor].name,
                                "depth": depth + 1
                            })
                            q.append((neighbor, depth + 1))

            # 4. Trace Forward (Effects)
            effects = []
            if str(event_id) in G:
                q = deque([(str(event_id), 0)])
                visited = {str(event_id)}
                
                while q:
                    curr, depth = q.popleft()
                    if depth >= max_depth:
                        continue
                        
                    for neighbor in G.neighbors(curr):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            effects.append({
                                "id": neighbor,
                                "name": event_map[neighbor].name,
                                "depth": depth + 1
                            })
                            q.append((neighbor, depth + 1))
                            
            return {
                "focal_event": {"id": str(event_id), "name": target_event.name},
                "causes": sorted(causes, key=lambda x: x['depth']),
                "effects": sorted(effects, key=lambda x: x['depth'])
            }
