"""
Provenance System Service Layer
Implements logic for state replay, knowledge tracking, and retcon impact analysis.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select, col

from writeros.schema.provenance import (
    StateChangeEvent, CharacterKnowledge, ContentDependency, ScenePresence
)
from writeros.schema.world import Entity

class ProvenanceService:
    def __init__(self, session: Session):
        self.session = session

    def compute_character_state(self, character_id: UUID, world_timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        Replays StateChangeEvents to reconstruct a character's state at a given time.
        """
        # 1. Fetch all valid events up to this timestamp
        query = select(StateChangeEvent).where(
            StateChangeEvent.entity_id == character_id,
            StateChangeEvent.is_superseded == False
        )
        
        if world_timestamp is not None:
            query = query.where(StateChangeEvent.world_timestamp <= world_timestamp)
            
        # Sort by time
        query = query.order_by(StateChangeEvent.world_timestamp, StateChangeEvent.narrative_sequence)
        
        events = self.session.exec(query).all()
        
        # 2. Replay Logic
        current_state = {
            "inventory": [],
            "status": "alive",
            "location": None,
            "attributes": {}
        }
        
        for event in events:
            self._apply_event(current_state, event)
            
        return current_state

    def _apply_event(self, state: Dict[str, Any], event: StateChangeEvent):
        """Applies a single event to the state dict."""
        payload = event.payload
        etype = event.event_type
        
        if etype == "inventory_add":
            item = payload.get("item")
            if item:
                state["inventory"].append(item)
        elif etype == "inventory_remove":
            item = payload.get("item")
            if item and item in state["inventory"]:
                state["inventory"].remove(item)
        elif etype == "location_move":
            state["location"] = payload.get("new_location_id")
        elif etype == "status_change":
            state["status"] = payload.get("new_status")
        # Add more handlers as needed

    def get_character_knowledge(self, character_id: UUID, world_timestamp: Optional[int] = None) -> List[CharacterKnowledge]:
        """
        Returns a list of what the character currently believes.
        """
        # Fetch knowledge that hasn't been forgotten or superseded
        query = select(CharacterKnowledge).where(
            CharacterKnowledge.character_id == character_id,
            CharacterKnowledge.superseded_by_id == None
        )
        
        # TODO: Add logic for 'forgotten_at_sequence' if we had a sequence number passed in
        
        return self.session.exec(query).all()

    def detect_retcon_impact(self, modified_entity_id: UUID) -> List[ContentDependency]:
        """
        Finds all content dependencies that might be broken by a change to this entity.
        """
        query = select(ContentDependency).where(
            ContentDependency.dependency_id == modified_entity_id,
            ContentDependency.is_valid == True
        )
        return self.session.exec(query).all()

    def invalidate_dependencies(self, modified_entity_id: UUID, reason: str):
        """
        Marks dependencies as invalid.
        """
        dependencies = self.detect_retcon_impact(modified_entity_id)
        for dep in dependencies:
            dep.is_valid = False
            dep.invalidation_reason = reason
            self.session.add(dep)
        self.session.commit()

    def character_last_seen(self, character_id: UUID) -> Optional[ScenePresence]:
        """
        Finds the last scene where a character was present.
        """
        # We need to join with Scene to order by sequence, but for now assuming created_at or similar
        # Ideally we'd have a sequence number on ScenePresence or join with Scene table
        query = select(ScenePresence).where(
            ScenePresence.entity_id == character_id
        ).order_by(col(ScenePresence.created_at).desc()).limit(1)
        
        return self.session.exec(query).first()
