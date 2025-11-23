"""
Generate rich test data for Phase 4A graph visualization.
Creates family trees, faction hierarchies, and location maps.
"""
import asyncio
from uuid import uuid4
from pathlib import Path
from agents.profiler import ProfilerAgent
from src.writeros.schema import Entity, Relationship, EntityType, RelationType
from utils.db import engine, init_db
from sqlmodel import Session

async def generate_rich_test_data():
    init_db()
    
    vault_id = uuid4()
    profiler = ProfilerAgent()
    
    print("Creating comprehensive test data for WriterOS graphs...")
    print(f"Vault ID: {vault_id}\n")
    
    with Session(engine) as session:
        # ===== CHARACTERS (for family tree) =====
        print("Creating characters...")
        
        # Generation 1 (Founders)
        rickard = Entity(vault_id=vault_id, name="Rickard Stark", type=EntityType.CHARACTER,
                        description="Lord of Winterfell, Generation 1", 
                        canon={"layer": "primary", "status": "active"})
        
        # Generation 2
        brandon = Entity(vault_id=vault_id, name="Brandon Stark", type=EntityType.CHARACTER,
                        description="Eldest son of Rickard", 
                        canon={"layer": "primary", "status": "active"})
        ned = Entity(vault_id=vault_id, name="Eddard Stark", type=EntityType.CHARACTER,
                    description="Second son of Rickard, Lord of Winterfell", 
                    canon={"layer": "primary", "status": "active"})
        benjen = Entity(vault_id=vault_id, name="Benjen Stark", type=EntityType.CHARACTER,
                       description="Youngest son of Rickard", 
                       canon={"layer": "primary", "status": "active"})
        
        # Generation 3 (Ned's children)
        robb = Entity(vault_id=vault_id, name="Robb Stark", type=EntityType.CHARACTER,
                     description="Eldest son of Ned", 
                     canon={"layer": "primary", "status": "active"})
        sansa = Entity(vault_id=vault_id, name="Sansa Stark", type=EntityType.CHARACTER,
                      description="Eldest daughter of Ned", 
                      canon={"layer": "primary", "status": "active"})
        arya = Entity(vault_id=vault_id, name="Arya Stark", type=EntityType.CHARACTER,
                     description="Second daughter of Ned", 
                     canon={"layer": "primary", "status": "active"})
        bran = Entity(vault_id=vault_id, name="Bran Stark", type=EntityType.CHARACTER,
                     description="Second son of Ned", 
                     canon={"layer": "primary", "status": "active"})
        rickon = Entity(vault_id=vault_id, name="Rickon Stark", type=EntityType.CHARACTER,
                       description="Youngest son of Ned", 
                       canon={"layer": "primary", "status": "active"})
        jon = Entity(vault_id=vault_id, name="Jon Snow", type=EntityType.CHARACTER,
                    description="Bastard son (or is he?)", 
                    canon={"layer": "primary", "status": "active"})
        
        # ===== FACTIONS =====
        print("Creating factions...")
        
        starks = Entity(vault_id=vault_id, name="House Stark", type=EntityType.FACTION,
                       description="The Great House of the North", 
                       canon={"layer": "primary", "status": "active"})
        nights_watch = Entity(vault_id=vault_id, name="Night's Watch", type=EntityType.FACTION,
                             description="Sworn brotherhood protecting the Wall", 
                             canon={"layer": "primary", "status": "active"})
        kings_guard = Entity(vault_id=vault_id, name="Kingsguard", type=EntityType.FACTION,
                            description="Elite royal guard", 
                            canon={"layer": "primary", "status": "active"})
        
        lannisters = Entity(vault_id=vault_id, name="House Lannister", type=EntityType.FACTION,
                           description="The Wealthy House of the West", 
                           canon={"layer": "primary", "status": "active"})
        
        tywin = Entity(vault_id=vault_id, name="Tywin Lannister", type=EntityType.CHARACTER,
                      description="Lord of Casterly Rock", 
                      canon={"layer": "primary", "status": "active"})

        # ===== LOCATIONS (with coordinates) =====
        print("Creating locations with coordinates...")
        
        winterfell = Entity(
            vault_id=vault_id, 
            name="Winterfell", 
            type=EntityType.LOCATION,
            description="Ancestral home of House Stark",
            properties={
                "coordinates": {"x": 0.3, "y": 0.2},  # North-west
                "map_region": "The North"
            },
            canon={"layer": "primary", "status": "active"}
        )
        
        the_wall = Entity(
            vault_id=vault_id, 
            name="The Wall", 
            type=EntityType.LOCATION,
            description="Massive fortification at the northern border",
            properties={
                "coordinates": {"x": 0.5, "y": 0.05},  # Far north, centered
                "map_region": "Beyond the North"
            },
            canon={"layer": "primary", "status": "active"}
        )
        
        kings_landing = Entity(
            vault_id=vault_id, 
            name="King's Landing", 
            type=EntityType.LOCATION,
            description="Capital of the Seven Kingdoms",
            properties={
                "coordinates": {"x": 0.65, "y": 0.75},  # South-east
                "map_region": "Crownlands"
            },
            canon={"layer": "primary", "status": "active"}
        )
        
        castle_black = Entity(
            vault_id=vault_id, 
            name="Castle Black", 
            type=EntityType.LOCATION,
            description="Primary fortress of the Night's Watch",
            properties={
                "coordinates": {"x": 0.5, "y": 0.1},  # Just south of The Wall
                "map_region": "The Wall"
            },
            canon={"layer": "primary", "status": "active"}
        )
        
        # Add all entities
        all_entities = [
            rickard, brandon, ned, benjen, robb, sansa, arya, bran, rickon, jon,
            starks, nights_watch, kings_guard, lannisters, tywin,
            winterfell, the_wall, kings_landing, castle_black
        ]
        
        session.add_all(all_entities)
        session.commit()
        
        # Refresh to get IDs
        for entity in all_entities:
            session.refresh(entity)
        
        print(f"Created {len(all_entities)} entities\n")
        
        # ===== RELATIONSHIPS =====
        print("Creating relationships...")
        
        relationships = []
        
        # FAMILY TREE relationships
        print("  - Family tree (PARENT/CHILD)...")
        
        # Generation 1 -> 2
        relationships.extend([
            Relationship(vault_id=vault_id, from_entity_id=rickard.id, to_entity_id=brandon.id,
                        rel_type=RelationType.PARENT, description="Father to eldest son",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=rickard.id, to_entity_id=ned.id,
                        rel_type=RelationType.PARENT, description="Father to second son",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=rickard.id, to_entity_id=benjen.id,
                        rel_type=RelationType.PARENT, description="Father to youngest son",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
        ])
        
        # Generation 2 -> 3 (Ned's children)
        relationships.extend([
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=robb.id,
                        rel_type=RelationType.PARENT, description="Father to heir",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=sansa.id,
                        rel_type=RelationType.PARENT, description="Father to daughter",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=arya.id,
                        rel_type=RelationType.PARENT, description="Father to daughter",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=bran.id,
                        rel_type=RelationType.PARENT, description="Father to son",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=rickon.id,
                        rel_type=RelationType.PARENT, description="Father to youngest",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
        ])
        
        # Siblings (Generation 3)
        relationships.extend([
            Relationship(vault_id=vault_id, from_entity_id=robb.id, to_entity_id=sansa.id,
                        rel_type=RelationType.SIBLING, description="Brother and sister",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=robb.id, to_entity_id=arya.id,
                        rel_type=RelationType.SIBLING, description="Brother and sister",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
        ])
        
        # FACTION relationships (hierarchy)
        print("  - Faction hierarchy (LEADS/MEMBER_OF)...")
        
        relationships.extend([
            # Ned leads House Stark
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=starks.id,
                        rel_type=RelationType.LEADS, description="Lord of Winterfell",
                        effective_from={"sequence": 0}, effective_until={"sequence": 50},
                        canon={"layer": "primary", "status": "active"}),
            
            # Robb becomes leader after Ned
            Relationship(vault_id=vault_id, from_entity_id=robb.id, to_entity_id=starks.id,
                        rel_type=RelationType.MEMBER_OF, description="Heir to Winterfell",
                        effective_from={"sequence": 0}, effective_until={"sequence": 50},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=robb.id, to_entity_id=starks.id,
                        rel_type=RelationType.LEADS, description="King in the North",
                        effective_from={"sequence": 50}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            
            # Family members of House Stark
            Relationship(vault_id=vault_id, from_entity_id=sansa.id, to_entity_id=starks.id,
                        rel_type=RelationType.MEMBER_OF, description="Member of House Stark",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=arya.id, to_entity_id=starks.id,
                        rel_type=RelationType.MEMBER_OF, description="Member of House Stark",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=bran.id, to_entity_id=starks.id,
                        rel_type=RelationType.MEMBER_OF, description="Member of House Stark",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            
            # Benjen and Jon join Night's Watch
            Relationship(vault_id=vault_id, from_entity_id=jon.id, to_entity_id=nights_watch.id,
                        rel_type=RelationType.MEMBER_OF, description="Sworn brother",
                        effective_from={"sequence": 30}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            
            # Tywin leads Lannisters
            Relationship(vault_id=vault_id, from_entity_id=tywin.id, to_entity_id=lannisters.id,
                        rel_type=RelationType.LEADS, description="Lord of Casterly Rock",
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            
            # FACTION vs FACTION
            Relationship(vault_id=vault_id, from_entity_id=starks.id, to_entity_id=lannisters.id,
                        rel_type=RelationType.ENEMY, description="War of the Five Kings",
                        effective_from={"sequence": 40}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
        ])
        
        # LOCATION relationships
        print("  - Location connections (LOCATED_IN/CONNECTED_TO)...")
        
        relationships.extend([
            # Characters located in places
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=winterfell.id,
                        rel_type=RelationType.LOCATED_IN, description="Lord at Winterfell",
                        effective_from={"sequence": 0}, effective_until={"sequence": 40},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=ned.id, to_entity_id=kings_landing.id,
                        rel_type=RelationType.LOCATED_IN, description="Hand of the King",
                        effective_from={"sequence": 40}, effective_until={"sequence": 50},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=jon.id, to_entity_id=castle_black.id,
                        rel_type=RelationType.LOCATED_IN, description="Stationed at Castle Black",
                        effective_from={"sequence": 30}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            
            # Location connections (with travel times)
            Relationship(vault_id=vault_id, from_entity_id=winterfell.id, to_entity_id=castle_black.id,
                        rel_type=RelationType.CONNECTED_TO, description="Road to the Wall",
                        properties={"travel_time": 240},  # 10 days
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=winterfell.id, to_entity_id=kings_landing.id,
                        rel_type=RelationType.CONNECTED_TO, description="Kingsroad",
                        properties={"travel_time": 720},  # 30 days
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
            Relationship(vault_id=vault_id, from_entity_id=castle_black.id, to_entity_id=the_wall.id,
                        rel_type=RelationType.CONNECTED_TO, description="At the Wall",
                        properties={"travel_time": 2},  # 2 hours
                        effective_from={"sequence": 0}, effective_until={"sequence": 100},
                        canon={"layer": "primary", "status": "active"}),
        ])
        
        session.add_all(relationships)
        session.commit()
        
        print(f"Created {len(relationships)} relationships\n")
    
    # Generate all graph types
    print("=" * 60)
    print("Generating graph visualizations...\n")
    
    output_dir = Path(".writeros/graphs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    graph_types = ["force", "family", "faction", "location"]
    
    for graph_type in graph_types:
        print(f"Generating {graph_type} graph...")
        
        graph_data = await profiler.generate_graph_data(
            vault_id=vault_id,
            graph_type=graph_type,
            max_nodes=100,
            canon_layer="primary"
        )
        
        output_path = profiler.generate_graph_html(
            graph_data=graph_data,
            output_path=f"{graph_type}_demo.html",
            graph_type=graph_type,
            title=f"{graph_type.capitalize()} Graph Demo"
        )
        
        print(f"  -> {output_path}")
        print(f"     Nodes: {len(graph_data['nodes'])}, Links: {len(graph_data['links'])}\n")
    
    print("=" * 60)
    print("\nDone! Open these files in your browser:")
    print("  - force_demo.html (all relationships)")
    print("  - family_demo.html (family tree only)")
    print("  - faction_demo.html (faction hierarchy)")
    print("  - location_demo.html (location map)\n")
    
    print("Test different features:")
    print("  1. Switch layouts using the dropdown")
    print("  2. Drag the timeline slider (0-100)")
    print("  3. Toggle entity/relationship filters")
    print("  4. Search for characters")
    print("  5. Drag nodes and refresh - positions persist\n")

if __name__ == "__main__":
    asyncio.run(generate_rich_test_data())
