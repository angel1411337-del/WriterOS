"""
Quick test script to verify graph type filtering
"""
import asyncio
from pathlib import Path
from uuid import uuid4
from agents.profiler import ProfilerAgent
from agents.schema import Entity, Relationship, EntityType, RelationType
from utils.db import engine, init_db
from sqlmodel import Session

async def test_graph_types():
    init_db()
    
    vault_id = uuid4()
    profiler = ProfilerAgent()
    
    print("Creating test data...")
    with Session(engine) as session:
        # Characters
        jon = Entity(vault_id=vault_id, name="Jon Snow", type=EntityType.CHARACTER,
                    description="Bastard son", canon={"layer": "primary", "status": "active"})
        ned = Entity(vault_id=vault_id, name="Ned Stark", type=EntityType.CHARACTER,
                    description="Lord of Winterfell", canon={"layer": "primary", "status": "active"})
        
        # Location
        winterfell = Entity(vault_id=vault_id, name="Winterfell", type=EntityType.LOCATION,
                           description="Castle in the North", canon={"layer": "primary", "status": "active"})
        
        # Faction
        nights_watch = Entity(vault_id=vault_id, name="Night's Watch", type=EntityType.FACTION,
                             description="Protectors of the Wall", canon={"layer": "primary", "status": "active"})
        
        session.add_all([jon, ned, winterfell, nights_watch])
        session.commit()
        session.refresh(jon)
        session.refresh(ned)
        session.refresh(winterfell)
        session.refresh(nights_watch)
        
        # Relationships
        family_rel = Relationship(vault_id=vault_id, from_entity_id=jon.id, to_entity_id=ned.id,
                                 rel_type=RelationType.FAMILY, description="Father-son",
                                 canon={"layer": "primary", "status": "active"})
        
        member_rel = Relationship(vault_id=vault_id, from_entity_id=jon.id, to_entity_id=nights_watch.id,
                                 rel_type=RelationType.MEMBER_OF, description="Member",
                                 canon={"layer": "primary", "status": "active"})
        
        located_rel = Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=winterfell.id,
                                  rel_type=RelationType.LOCATED_IN, description="Lives in",
                                  canon={"layer": "primary", "status": "active"})
        
        session.add_all([family_rel, member_rel, located_rel])
        session.commit()
    
    print("\nTesting graph type filtering...\n")
    
    # Test FORCE (all relationships)
    print("=" * 50)
    print("FORCE GRAPH (all relationships)")
    data = await profiler.generate_graph_data(vault_id=vault_id, graph_type="force")
    print(f"  Nodes: {len(data['nodes'])}")
    print(f"  Links: {len(data['links'])}")
    print(f"  Link types: {[l['type'] for l in data['links']]}")
    
    # Test FAMILY (only family relationships)
    print("\n" + "=" * 50)
    print("FAMILY GRAPH (only family relationships)")
    data = await profiler.generate_graph_data(vault_id=vault_id, graph_type="family")
    print(f"  Nodes: {len(data['nodes'])}")
    print(f"  Links: {len(data['links'])}")
    print(f"  Link types: {[l['type'] for l in data['links']]}")
    print(f"  Expected: 1 link (FAMILY)")
    
    # Test FACTION (only faction relationships)
    print("\n" + "=" * 50)
    print("FACTION GRAPH (only faction relationships)")
    data = await profiler.generate_graph_data(vault_id=vault_id, graph_type="faction")
    print(f"  Nodes: {len(data['nodes'])}")
    print(f"  Links: {len(data['links'])}")
    print(f"  Link types: {[l['type'] for l in data['links']]}")
    print(f"  Expected: 1 link (MEMBER_OF)")
    
    # Test LOCATION (only location relationships)
    print("\n" + "=" * 50)
    print("LOCATION GRAPH (only location relationships)")
    data = await profiler.generate_graph_data(vault_id=vault_id, graph_type="location")
    print(f"  Nodes: {len(data['nodes'])}")
    print(f"  Links: {len(data['links'])}")
    print(f"  Link types: {[l['type'] for l in data['links']]}")
    print(f"  Expected: 1 link (LOCATED_IN)")
    
    # Cleanup
    print("\n" + "=" * 50)
    print("Cleaning up...")
    with Session(engine) as session:
        session.query(Relationship).filter(Relationship.vault_id == vault_id).delete()
        session.query(Entity).filter(Entity.vault_id == vault_id).delete()
        session.commit()
    
    print("✅ Graph type filtering test complete!")

if __name__ == "__main__":
    asyncio.run(test_graph_types())
