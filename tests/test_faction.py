import sys
import os
from uuid import uuid4
from sqlalchemy import JSON
import sqlalchemy.dialects.postgresql

# Monkeypatch JSONB to JSON for SQLite compatibility
sqlalchemy.dialects.postgresql.JSONB = JSON

from sqlmodel import SQLModel, create_engine, Session, select

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from writeros.schema.faction import Faction
from writeros.schema.world import Entity
from writeros.schema.identity import User, Vault
from writeros.schema.enums import EntityType

# Setup in-memory DB
engine = create_engine("sqlite:///:memory:")

def setup_module():
    SQLModel.metadata.create_all(engine)

def test_faction_creation():
    with Session(engine) as session:
        # Setup Data
        user = User(email="test@test.com", username="tester")
        session.add(user)
        session.commit()
        
        vault = Vault(name="Test Vault", owner_id=user.id)
        session.add(vault)
        session.commit()
        
        # Create Faction Entity
        stark_entity = Entity(
            name="House Stark",
            type=EntityType.FACTION,
            vault_id=vault.id,
            description="The Great House of the North"
        )
        session.add(stark_entity)
        session.commit()
        
        # Create Leader
        ned = Entity(
            name="Eddard Stark",
            type=EntityType.CHARACTER,
            vault_id=vault.id
        )
        session.add(ned)
        session.commit()
        
        # Create Faction
        stark_faction = Faction(
            vault_id=vault.id,
            entity_id=stark_entity.id,
            faction_type="noble_house",
            motto="Winter is Coming",
            sigil_description="A grey direwolf on a white field",
            colors=["grey", "white"],
            leader_id=ned.id,
            leadership_type="monarchy",
            succession_rules="primogeniture",
            member_count=50,
            influence_level=85,
            wealth_level=70,
            military_strength=75,
            status="active",
            goals=["Protect the North", "Honor and Duty"],
            values=["honor", "loyalty", "justice"]
        )
        session.add(stark_faction)
        session.commit()
        
        # Verify
        retrieved = session.exec(
            select(Faction).where(Faction.entity_id == stark_entity.id)
        ).first()
        
        assert retrieved is not None
        assert retrieved.motto == "Winter is Coming"
        assert retrieved.leader_id == ned.id
        assert retrieved.influence_level == 85
        assert "honor" in retrieved.values
        
        print("\n✅ Faction Creation Passed!")
        print(f"Faction: {stark_entity.name}")
        print(f"Motto: {retrieved.motto}")
        print(f"Influence: {retrieved.influence_level}")
        print(f"Values: {retrieved.values}")

def test_faction_hierarchy():
    with Session(engine) as session:
        vault = session.exec(select(Vault)).first()
        
        # Create parent faction (The North)
        north_entity = Entity(
            name="The North",
            type=EntityType.FACTION,
            vault_id=vault.id
        )
        session.add(north_entity)
        session.commit()
        
        north_faction = Faction(
            vault_id=vault.id,
            entity_id=north_entity.id,
            faction_type="region",
            status="active"
        )
        session.add(north_faction)
        session.commit()
        
        # Create vassal (House Bolton)
        bolton_entity = Entity(
            name="House Bolton",
            type=EntityType.FACTION,
            vault_id=vault.id
        )
        session.add(bolton_entity)
        session.commit()
        
        bolton_faction = Faction(
            vault_id=vault.id,
            entity_id=bolton_entity.id,
            faction_type="noble_house",
            parent_faction_id=north_faction.id,
            status="active"
        )
        session.add(bolton_faction)
        session.commit()
        
        # Update parent's vassal list
        north_faction.vassal_faction_ids = [str(bolton_faction.id)]
        session.add(north_faction)
        session.commit()
        
        # Verify hierarchy
        assert bolton_faction.parent_faction_id == north_faction.id
        assert str(bolton_faction.id) in north_faction.vassal_faction_ids
        
        print("\n✅ Faction Hierarchy Passed!")
        print(f"Parent: {north_entity.name}")
        print(f"Vassal: {bolton_entity.name}")

if __name__ == "__main__":
    setup_module()
    test_faction_creation()
    test_faction_hierarchy()
