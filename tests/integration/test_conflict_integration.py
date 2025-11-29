import pytest
from uuid import uuid4
from sqlmodel import Session
from writeros.schema.world import Conflict, ConflictParticipant, Entity
from writeros.schema.enums import ConflictType, ConflictStatus, ConflictRole, EntityType
from writeros.agents.architect import ArchitectAgent
from writeros.agents.dramatist import DramatistAgent



from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_session(db_session):
    """
    Patches Session in conflict_engine to return the test db_session.
    This ensures the ConflictEngine sees the uncommitted data from the test setup.
    """
    with patch("writeros.services.conflict_engine.Session") as mock_session_cls:
        # When Session(engine) is called, return a context manager that yields db_session
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = db_session
        mock_ctx.__exit__.return_value = None
        mock_session_cls.return_value = mock_ctx
        yield mock_session_cls

@pytest.mark.asyncio
async def test_architect_conflict_integration(db_session, mock_session):
    # 1. Setup Data
    vault_id = uuid4()
    
    conflict = Conflict(
        vault_id=vault_id,
        name="The Long War",
        conflict_type=ConflictType.PERSON_VS_SOCIETY,
        status=ConflictStatus.RISING_ACTION,
        stakes="Freedom",
        intensity=80
    )
    db_session.add(conflict)
    db_session.commit()
    
    # 2. Run Architect
    architect = ArchitectAgent()
    tasks = await architect.generate_plot_tasks(vault_id)
    
    # 3. Verify
    assert len(tasks) > 0
    assert "Escalate Conflict 'The Long War'" in tasks[0]

@pytest.mark.asyncio
async def test_dramatist_conflict_integration(db_session, mock_session):
    # 1. Setup Data
    vault_id = uuid4()
    
    hero = Entity(vault_id=vault_id, name="Hero", type=EntityType.CHARACTER)
    db_session.add(hero)
    db_session.commit()
    
    conflict = Conflict(
        vault_id=vault_id,
        name="Nemesis Duel",
        conflict_type=ConflictType.PERSON_VS_PERSON,
        status=ConflictStatus.CLIMAX,
        stakes="Life or Death",
        intensity=95
    )
    db_session.add(conflict)
    db_session.commit()
    
    participant = ConflictParticipant(
        conflict_id=conflict.id,
        entity_id=hero.id,
        role=ConflictRole.PROTAGONIST
    )
    db_session.add(participant)
    db_session.commit()
    
    # 2. Run Dramatist
    dramatist = DramatistAgent()
    instructions = await dramatist.generate_scene_instructions(vault_id, [str(hero.id)])
    
    # 3. Verify
    assert len(instructions) > 0
    assert "Push for maximum intensity!" in instructions[0]
