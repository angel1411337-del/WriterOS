"""
Test script for D3.js Relationship Graph Generation
"""
import asyncio
from uuid import uuid4
from sqlmodel import Session
from agents.profiler import ProfilerAgent
from agents.schema import Entity, Relationship, EntityType, RelationType
from utils.db import engine, init_db

async def main():
    print("Starting D3.js Graph Generation Test...")
    
    # Initialize database
    init_db()
    
    # Create test vault
    vault_id = uuid4()
    print(f"Created test vault: {vault_id}")
    
    # Create test entities
    with Session(engine) as session:
        # Characters
        jon = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Jon Snow",
            description="Bastard son of Ned Stark, member of the Night's Watch",
            properties={"role": "protagonist", "house": "Stark"},
            tags=["stark", "nights_watch"],
            canon={"layer": "primary", "status": "active"}
        )
        
        ned = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Ned Stark",
            description="Lord of Winterfell, Warden of the North",
            properties={"role": "supporting", "house": "Stark"},
            tags=["stark", "lord"],
            canon={"layer": "primary", "status": "active"}
        )
        
        arya = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Arya Stark",
            description="Youngest daughter of Ned Stark",
            properties={"role": "protagonist", "house": "Stark"},
            tags=["stark", "assassin"],
            canon={"layer": "primary", "status": "active"}
        )
        
        cersei = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Cersei Lannister",
            description="Queen of the Seven Kingdoms",
            properties={"role": "antagonist", "house": "Lannister"},
            tags=["lannister", "queen"],
            canon={"layer": "primary", "status": "active"}
        )
        
        # Locations
        winterfell = Entity(
            vault_id=vault_id,
            type=EntityType.LOCATION,
            name="Winterfell",
            description="Ancestral home of House Stark",
            properties={"region": "North"},
            tags=["castle", "stark"],
            canon={"layer": "primary", "status": "active"}
        )
        
        # Factions
        nights_watch = Entity(
            vault_id=vault_id,
            type=EntityType.FACTION,
            name="Night's Watch",
            description="Ancient order defending the Wall",
            properties={"type": "military_order"},
            tags=["wall", "defense"],
            canon={"layer": "primary", "status": "active"}
        )
        
        session.add_all([jon, ned, arya, cersei, winterfell, nights_watch])
        session.commit()
        
        print(f"Created {6} test entities")
        
        # Create relationships
        relationships = [
            Relationship(
                vault_id=vault_id,
                from_entity_id=jon.id,
                to_entity_id=ned.id,
                rel_type=RelationType.FAMILY,
                description="Father-son relationship (Until Ned's death)",
                properties={"leverage": "Blood oath"},
                effective_from={"sequence": 0},
                effective_until={"sequence": 10},
                canon={"layer": "primary", "status": "active"}
            ),
            Relationship(
                vault_id=vault_id,
                from_entity_id=arya.id,
                to_entity_id=ned.id,
                rel_type=RelationType.FAMILY,
                description="Father-daughter relationship",
                effective_from={"sequence": 0},
                effective_until={"sequence": 10},
                canon={"layer": "primary", "status": "active"}
            ),
            Relationship(
                vault_id=vault_id,
                from_entity_id=jon.id,
                to_entity_id=arya.id,
                rel_type=RelationType.SIBLING,
                description="Half-siblings (Always)",
                effective_from={"sequence": 0},
                effective_until={"sequence": 100},
                canon={"layer": "primary", "status": "active"}
            ),
            Relationship(
                vault_id=vault_id,
                from_entity_id=ned.id,
                to_entity_id=cersei.id,
                rel_type=RelationType.ENEMY,
                description="Political enemies (Starts when Ned arrives in KL)",
                properties={"leverage": "Knowledge of incest"},
                effective_from={"sequence": 5},
                effective_until={"sequence": 10},
                canon={"layer": "primary", "status": "active"}
            ),
            Relationship(
                vault_id=vault_id,
                from_entity_id=jon.id,
                to_entity_id=nights_watch.id,
                rel_type=RelationType.MEMBER_OF,
                description="Member of the Night's Watch (Joins later)",
                effective_from={"sequence": 15},
                effective_until={"sequence": 100},
                canon={"layer": "primary", "status": "active"}
            ),
            Relationship(
                vault_id=vault_id,
                from_entity_id=ned.id,
                to_entity_id=winterfell.id,
                rel_type=RelationType.LOCATED_IN,
                description="Lord of Winterfell (Leaves for KL)",
                effective_from={"sequence": 0},
                effective_until={"sequence": 5},
                canon={"layer": "primary", "status": "active"}
            )
        ]
        
        session.add_all(relationships)
        session.commit()
        
        print(f"Created {len(relationships)} test relationships")
    
    # Generate graph
    profiler = ProfilerAgent()
    
    print("\nGenerating graph data...")
    graph_data = await profiler.generate_graph_data(
        vault_id=vault_id,
        max_nodes=100,
        canon_layer="primary"
    )
    
    print(f"  Nodes: {len(graph_data['nodes'])}")
    print(f"  Links: {len(graph_data['links'])}")
    
    # Generate HTML
    print("\nGenerating HTML visualization...")
    output_path = profiler.generate_graph_html(
        graph_data=graph_data,
        output_path="test_relationship_graph.html",
        title="Game of Thrones - Test Graph"
    )
    
    print(f"\nGraph generated successfully!")
    print(f"Open in browser: {output_path}")
    
    # Cleanup
    print("\nCleaning up test data...")
    with Session(engine) as session:
        session.query(Relationship).filter(Relationship.vault_id == vault_id).delete()
        session.query(Entity).filter(Entity.vault_id == vault_id).delete()
        session.commit()
    
    print("Test complete!")

if __name__ == "__main__":
    asyncio.run(main())
