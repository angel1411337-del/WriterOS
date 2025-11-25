import pytest
from uuid import uuid4
from sqlmodel import Session, select
from writeros.schema.world import Conflict, ConflictParticipant, Entity
from writeros.schema.enums import ConflictType, ConflictStatus, ConflictRole, EntityType



def test_create_conflict(db_session):
    # 1. Create Vault ID
    vault_id = uuid4()
    
    # 2. Create Entities (Protagonist & Antagonist)
    hero = Entity(
        vault_id=vault_id,
        name="Hero",
        type=EntityType.CHARACTER
    )
    villain = Entity(
        vault_id=vault_id,
        name="Villain",
        type=EntityType.CHARACTER
    )
    db_session.add(hero)
    db_session.add(villain)
    db_session.commit()
    db_session.refresh(hero)
    db_session.refresh(villain)
    
    # 3. Create Conflict
    conflict = Conflict(
        vault_id=vault_id,
        name="The Final Battle",
        conflict_type=ConflictType.PERSON_VS_PERSON,
        status=ConflictStatus.CLIMAX,
        stakes="The fate of the world",
        intensity=90
    )
    db_session.add(conflict)
    db_session.commit()
    db_session.refresh(conflict)
    
    # 4. Add Participants
    p1 = ConflictParticipant(
        conflict_id=conflict.id,
        entity_id=hero.id,
        role=ConflictRole.PROTAGONIST
    )
    p2 = ConflictParticipant(
        conflict_id=conflict.id,
        entity_id=villain.id,
        role=ConflictRole.ANTAGONIST
    )
    db_session.add(p1)
    db_session.add(p2)
    db_session.commit()
    
    # 5. Verify
    db_session.refresh(conflict)
    assert len(conflict.participants) == 2
    assert conflict.name == "The Final Battle"
    assert conflict.intensity == 90
    
    # Check roles
    participants = {p.entity_id: p.role for p in conflict.participants}
    assert participants[hero.id] == ConflictRole.PROTAGONIST
    assert participants[villain.id] == ConflictRole.ANTAGONIST
