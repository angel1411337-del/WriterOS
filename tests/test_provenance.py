import sys
import os
from uuid import uuid4
from sqlalchemy import JSON
import sqlalchemy.dialects.postgresql

# Monkeypatch JSONB to JSON for SQLite compatibility
sqlalchemy.dialects.postgresql.JSONB = JSON

from sqlmodel import SQLModel, create_engine, Session

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from writeros.schema.provenance import StateChangeEvent, ContentDependency
from writeros.schema.world import Entity
from writeros.schema.identity import User, Vault
from writeros.services.provenance import ProvenanceService

# Setup in-memory DB
engine = create_engine("sqlite:///:memory:")

def setup_module():
    SQLModel.metadata.create_all(engine)

def test_provenance_state_replay():
    with Session(engine) as session:
        # Setup Data
        user = User(email="test@test.com", username="tester")
        session.add(user)
        session.commit()
        
        vault = Vault(name="Test Vault", owner_id=user.id)
        session.add(vault)
        session.commit()
        
        hero = Entity(name="Jon Snow", type="character", vault_id=vault.id)
        session.add(hero)
        session.commit()
        
        # 1. Add Event: Get Sword
        event1 = StateChangeEvent(
            vault_id=vault.id,
            entity_id=hero.id,
            event_type="inventory_add",
            payload={"item": "Longclaw"},
            world_timestamp=100
        )
        session.add(event1)
        
        # 2. Add Event: Move to Wall
        event2 = StateChangeEvent(
            vault_id=vault.id,
            entity_id=hero.id,
            event_type="location_move",
            payload={"new_location_id": str(uuid4())},
            world_timestamp=200
        )
        session.add(event2)
        session.commit()
        
        # Test Replay
        service = ProvenanceService(session)
        state = service.compute_character_state(hero.id)
        
        assert "Longclaw" in state["inventory"]
        assert state["location"] is not None
        
        print("\n✅ State Replay Passed!")
        print(f"State: {state}")

def test_retcon_impact():
    with Session(engine) as session:
        # Setup Data (reuse or new)
        vault = session.exec(select(Vault)).first()
        hero = session.exec(select(Entity)).first()
        scene_id = uuid4()
        
        # Create Dependency
        dep = ContentDependency(
            vault_id=vault.id,
            dependent_scene_id=scene_id,
            dependency_type="assumes_alive",
            dependency_id=hero.id,
            assumption="Jon is alive"
        )
        session.add(dep)
        session.commit()
        
        # Test Detection
        service = ProvenanceService(session)
        impacted = service.detect_retcon_impact(hero.id)
        
        assert len(impacted) == 1
        assert impacted[0].assumption == "Jon is alive"
        
        # Test Invalidation
        service.invalidate_dependencies(hero.id, "Jon died")
        session.refresh(dep)
        assert dep.is_valid == False
        assert dep.invalidation_reason == "Jon died"
        
        print("\n✅ Retcon Impact Passed!")

if __name__ == "__main__":
    from sqlmodel import select
    setup_module()
    test_provenance_state_replay()
    test_retcon_impact()
