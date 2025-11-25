from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlmodel import Session, select, desc
from writeros.utils import db as db_utils
from writeros.schema.world import Conflict, ConflictParticipant, Entity
from writeros.schema.enums import ConflictStatus, ConflictRole

class ConflictEngine:
    def get_active_conflicts(self, vault_id: UUID) -> List[Conflict]:
        """Returns all conflicts where status != RESOLUTION."""
        with Session(db_utils.engine) as session:
            statement = select(Conflict).where(
                Conflict.vault_id == vault_id,
                Conflict.status != ConflictStatus.RESOLUTION
            )
            return session.exec(statement).all()

    def get_tension_map(self, vault_id: UUID) -> List[Dict[str, Any]]:
        """Returns a weighted list of characters involved in the most high-intensity conflicts."""
        with Session(db_utils.engine) as session:
            # Join Conflict and ConflictParticipant to get high intensity conflicts
            statement = select(Conflict, ConflictParticipant, Entity).join(
                ConflictParticipant, Conflict.id == ConflictParticipant.conflict_id
            ).join(
                Entity, ConflictParticipant.entity_id == Entity.id
            ).where(
                Conflict.vault_id == vault_id,
                Conflict.status != ConflictStatus.RESOLUTION
            ).order_by(desc(Conflict.intensity))
            
            results = session.exec(statement).all()
            
            tension_map = []
            for conflict, participant, entity in results:
                tension_map.append({
                    "character_id": str(entity.id),
                    "character_name": entity.name,
                    "conflict_id": str(conflict.id),
                    "conflict_name": conflict.name,
                    "intensity": conflict.intensity,
                    "role": participant.role,
                    "status": conflict.status
                })
            return tension_map

    def update_conflict_status(self, conflict_id: UUID, new_status: ConflictStatus) -> Dict[str, Any]:
        """Handles the logic (e.g., if moving to CLIMAX, check if intensity is high enough)."""
        with Session(db_utils.engine) as session:
            conflict = session.get(Conflict, conflict_id)
            if not conflict:
                return {"error": "Conflict not found"}
            
            # Logic: Check intensity for Climax
            if new_status == ConflictStatus.CLIMAX and conflict.intensity < 70:
                return {
                    "success": False, 
                    "message": f"Cannot move to CLIMAX. Intensity {conflict.intensity} is too low (needs 70+)."
                }
            
            conflict.status = new_status
            session.add(conflict)
            session.commit()
            session.refresh(conflict)
            return {"success": True, "conflict": conflict}
