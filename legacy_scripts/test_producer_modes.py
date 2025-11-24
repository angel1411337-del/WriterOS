import asyncio
import os
from uuid import uuid4
from agents.producer import ProducerAgent
from agents.schema import Entity, EntityType, Relationship, RelationType, Fact, FactType, Event
from sqlmodel import Session
from utils.db import engine, init_db
from utils.embeddings import embedding_service

async def test_producer_modes():
    print("🎬 Starting Producer 5 Modes Verification Test...")
    
    # Initialize
    init_db()
    agent = ProducerAgent()
    vault_id = uuid4()
    
    # Setup test data
    print("\n📊 Setting up test data...")
    with Session(engine) as session:
        # Create test entities
        jon = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Jon Snow",
            description="The bastard of Winterfell",
            properties={"role": "protagonist", "eye_color": "grey"}
        )
        king = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Robert Baratheon",
            description="The King",
            properties={"role": "king"}
        )
        villain = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Joffrey Baratheon",
            description="The cruel prince",
            properties={"role": "villain"}
        )
        ned = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Ned Stark",
            description="Lord of Winterfell",
            properties={"role": "lord"}
        )
        
        session.add_all([jon, king, villain, ned])
        session.commit()
        session.refresh(jon)
        session.refresh(king)
        session.refresh(villain)
        session.refresh(ned)
        
        # Create relationships for traversal
        rel1 = Relationship(
            vault_id=vault_id,
            from_entity_id=jon.id,
            to_entity_id=ned.id,
            rel_type=RelationType.FAMILY,
            description="Raised by Ned"
        )
        rel2 = Relationship(
            vault_id=vault_id,
            from_entity_id=ned.id,
            to_entity_id=king.id,
            rel_type=RelationType.FRIEND,
            description="Old friends"
        )
        
        session.add_all([rel1, rel2])
        
        # Create a fact with embedding for local search
        fact = Fact(
            entity_id=jon.id,
            fact_type=FactType.TRAIT,
            content="Jon Snow has grey eyes that reflect his Stark heritage",
            embedding=embedding_service.embed_query("Jon Snow has grey eyes")
        )
        
        # Create an event for drift analysis
        event = Event(
            vault_id=vault_id,
            name="Ned's Execution",
            description="Ned Stark was executed by Joffrey"
        )
        
        session.add(fact)
        session.add(event)
        session.commit()
    
    # TEST 1: Local Search (Vector RAG)
    print("\n" + "="*60)
    print("TEST 1: LOCAL SEARCH (Vector RAG)")
    print("="*60)
    print("Query: 'What color are Jon's eyes?'")
    try:
        result1 = await agent.query("What color are Jon's eyes?", mode="local")
        print(f"✅ Response: {result1[:200]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # TEST 2: Global Search (Context Stuffing)
    print("\n" + "="*60)
    print("TEST 2: GLOBAL SEARCH (Context Stuffing)")
    print("="*60)
    print("Query: 'What should I work on today?'")
    try:
        result2 = await agent.query("What should I work on today?", mode="global")
        print(f"✅ Response: {result2[:200]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # TEST 3: Drift Search (Causal Analysis)
    print("\n" + "="*60)
    print("TEST 3: DRIFT SEARCH (Causal Analysis)")
    print("="*60)
    print("Query: 'What happens if Ned dies?'")
    try:
        result3 = await agent.query("What happens if Ned dies?", mode="drift")
        print(f"✅ Response: {result3[:200]}...")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # TEST 4: Structured Query (SQL/JSONB)
    print("\n" + "="*60)
    print("TEST 4: STRUCTURED QUERY (SQL)")
    print("="*60)
    print("Query: 'List all characters with role: villain'")
    try:
        result4 = await agent.query("List all characters with role: villain", mode="sql")
        print(f"✅ Response: {result4}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # TEST 5: Graph Traversal (Relationship Path)
    print("\n" + "="*60)
    print("TEST 5: GRAPH TRAVERSAL (Relationship Path)")
    print("="*60)
    print("Query: 'How does Jon Snow know Robert Baratheon?'")
    try:
        result5 = await agent.query("How does Jon Snow know Robert Baratheon?", mode="traversal")
        print(f"✅ Response: {result5}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # TEST 6: Mode Auto-Detection
    print("\n" + "="*60)
    print("TEST 6: MODE AUTO-DETECTION")
    print("="*60)
    print("Query (no mode): 'Show me all villains'")
    try:
        result6 = await agent.query("Show me all villains")  # Should auto-detect as sql
        print(f"✅ Response: {result6}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    with Session(engine) as session:
        session.query(Fact).filter(Fact.entity_id.in_(
            session.query(Entity.id).filter(Entity.vault_id == vault_id)
        )).delete(synchronize_session=False)
        session.query(Event).filter(Event.vault_id == vault_id).delete()
        session.query(Relationship).filter(Relationship.vault_id == vault_id).delete()
        session.query(Entity).filter(Entity.vault_id == vault_id).delete()
        session.commit()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    if os.name == 'nt':
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        
    asyncio.run(test_producer_modes())
