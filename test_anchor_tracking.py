import asyncio
import os
from uuid import uuid4, UUID
from agents.architect import ArchitectAgent
from agents.schema import Anchor, AnchorStatus, Entity, EntityType, Fact, FactType, Relationship, RelationType, Event
from sqlmodel import Session, select
from utils.db import engine, init_db

async def test_prerequisite_tracking():
    print("🚀 Starting Anchor Prerequisite Tracking Test...")
    
    # Initialize database and agent
    init_db()
    agent = ArchitectAgent()
    
    # Setup: Create test entities
    vault_id = uuid4()
    
    with Session(engine) as session:
        # Create test entities
        robb = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Robb Stark",
            properties={"role": "protagonist"}
        )
        frey = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Walder Frey",
            properties={"role": "antagonist"}
        )
        session.add(robb)
        session.add(frey)
        session.commit()
        session.refresh(robb)
        session.refresh(frey)
        
        # Create an Anchor with 3 prerequisites
        anchor = Anchor(
            vault_id=vault_id,
            name="Red Wedding",
            description="Robb Stark must be betrayed at the Twins",
            status=AnchorStatus.PENDING,
            prerequisites=[
                {"type": "fact", "entity": "Robb Stark", "content": "married"},
                {"type": "relationship", "from": "Walder Frey", "to": "Robb Stark", "status": "hostile"},
                {"type": "event", "name": "Bolton contacts Lannisters"}
            ]
        )
        session.add(anchor)
        session.commit()
        session.refresh(anchor)
        anchor_id = anchor.id
        
    # Test 1: Check prerequisites before any are met
    print("\n📋 Test 1: Checking prerequisites (none met)...")
    result1 = await agent.check_anchor_prerequisites(anchor_id)
    print(f"   - Prerequisites met: {result1['prerequisites_met']}/{result1['prerequisites_total']}")
    print(f"   - Status: {result1['status']}")
    print(f"   - Completion: {result1['completion_percentage']:.1f}%")
    
    # Test 2: Add prerequisite 1 (Fact)
    print("\n✅ Adding Fact: Robb married...")
    with Session(engine) as session:
        robb_entity = session.exec(select(Entity).where(Entity.name == "Robb Stark")).first()
        fact = Fact(
            entity_id=robb_entity.id,
            fact_type=FactType.TRAIT,
            content="Robb Stark married Talisa against the Frey's wishes"
        )
        session.add(fact)
        session.commit()
    
    result2 = await agent.check_anchor_prerequisites(anchor_id)
    print(f"   - Prerequisites met: {result2['prerequisites_met']}/{result2['prerequisites_total']}")
    print(f"   - Status: {result2['status']}")
    
    # Test 3: Add prerequisite 2 (Relationship)
    print("\n✅ Adding Relationship: Frey -> Robb (hostile)...")
    with Session(engine) as session:
        robb_entity = session.exec(select(Entity).where(Entity.name == "Robb Stark")).first()
        frey_entity = session.exec(select(Entity).where(Entity.name == "Walder Frey")).first()
        rel = Relationship(
            vault_id=vault_id,
            from_entity_id=frey_entity.id,
            to_entity_id=robb_entity.id,
            rel_type=RelationType.ENEMY,
            properties={"status": "hostile"}
        )
        session.add(rel)
        session.commit()
    
    result3 = await agent.check_anchor_prerequisites(anchor_id)
    print(f"   - Prerequisites met: {result3['prerequisites_met']}/{result3['prerequisites_total']}")
    print(f"   - Status: {result3['status']}")
    
    # Test 4: Add prerequisite 3 (Event)
    print("\n✅ Adding Event: Bolton contacts Lannisters...")
    with Session(engine) as session:
        event = Event(
            vault_id=vault_id,
            name="Bolton contacts Lannisters",
            description="Roose Bolton secretly negotiates with the Lannisters"
        )
        session.add(event)
        session.commit()
    
    result4 = await agent.check_anchor_prerequisites(anchor_id)
    print(f"   - Prerequisites met: {result4['prerequisites_met']}/{result4['prerequisites_total']}")
    print(f"   - Status: {result4['status']}")
    print(f"   - Completion: {result4['completion_percentage']:.1f}%")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    with Session(engine) as session:
        # Delete in reverse order (relationships, facts, events, entities, anchors)
        session.query(Relationship).filter(Relationship.vault_id == vault_id).delete()
        session.query(Fact).filter(Fact.entity_id.in_(
            session.query(Entity.id).filter(Entity.vault_id == vault_id)
        )).delete(synchronize_session=False)
        session.query(Event).filter(Event.vault_id == vault_id).delete()
        session.query(Entity).filter(Entity.vault_id == vault_id).delete()
        session.query(Anchor).filter(Anchor.vault_id == vault_id).delete()
        session.commit()
        
    print("✅ Test Complete!")

if __name__ == "__main__":
    if os.name == 'nt':
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        
    asyncio.run(test_prerequisite_tracking())
