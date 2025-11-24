import asyncio
import os
from uuid import uuid4
from agents.profiler import ProfilerAgent
from agents.schema import Entity, EntityType, Relationship, RelationType
from sqlmodel import Session
from utils.db import engine, init_db

async def test_family_tree():
    print("🌳 Starting Family Tree Visualization Test...")
    
    # Initialize database and agent
    init_db()
    agent = ProfilerAgent()
    
    # Setup: Create a multi-generation family
    vault_id = uuid4()
    
    with Session(engine) as session:
        # Create family members across 4 generations
        # Generation -2: Grandparents
        grandpa = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Grandpa Stark",
            properties={"role": "elder"}
        )
        grandma = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Grandma Stark",
            properties={"role": "elder"}
        )
        
        # Generation -1: Parents
        father = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Ned Stark",
            properties={"role": "father"}
        )
        mother = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Catelyn Stark",
            properties={"role": "mother"}
        )
        
        # Generation 0: Target character (siblings)
        robb = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Robb Stark",
            properties={"role": "protagonist"}
        )
        sansa = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Sansa Stark",
            properties={"role": "sibling"}
        )
        
        # Generation +1: Children
        child = Entity(
            vault_id=vault_id,
            type=EntityType.CHARACTER,
            name="Future Stark",
            properties={"role": "heir"}
        )
        
        session.add_all([grandpa, grandma, father, mother, robb, sansa, child])
        session.commit()
        session.refresh(grandpa)
        session.refresh(grandma)
        session.refresh(father)
        session.refresh(mother)
        session.refresh(robb)
        session.refresh(sansa)
        session.refresh(child)
        
        # Create family relationships with metadata
        relationships = [
            # Grandpa -> Father (parent relationship, generation_level = -1)
            Relationship(
                vault_id=vault_id,
                from_entity_id=grandpa.id,
                to_entity_id=father.id,
                rel_type=RelationType.PARENT,
                relationship_metadata={
                    "is_blood_relative": True,
                    "generation_level": -1
                }
            ),
            # Grandma -> Father
            Relationship(
                vault_id=vault_id,
                from_entity_id=grandma.id,
                to_entity_id=father.id,
                rel_type=RelationType.PARENT,
                relationship_metadata={
                    "is_blood_relative": True,
                    "generation_level": -1
                }
            ),
            # Father -> Robb (parent relationship, generation_level = -1)
            Relationship(
                vault_id=vault_id,
                from_entity_id=father.id,
                to_entity_id=robb.id,
                rel_type=RelationType.PARENT,
                relationship_metadata={
                    "is_blood_relative": True,
                    "generation_level": -1
                }
            ),
            # Mother -> Robb
            Relationship(
                vault_id=vault_id,
                from_entity_id=mother.id,
                to_entity_id=robb.id,
                rel_type=RelationType.PARENT,
                relationship_metadata={
                    "is_blood_relative": True,
                    "generation_level": -1
                }
            ),
            # Father -> Sansa
            Relationship(
                vault_id=vault_id,
                from_entity_id=father.id,
                to_entity_id=sansa.id,
                rel_type=RelationType.PARENT,
                relationship_metadata={
                    "is_blood_relative": True,
                    "generation_level": -1
                }
            ),
            # Robb <-> Sansa (sibling, generation_level = 0)
            Relationship(
                vault_id=vault_id,
                from_entity_id=robb.id,
                to_entity_id=sansa.id,
                rel_type=RelationType.SIBLING,
                relationship_metadata={
                    "is_blood_relative": True,
                    "generation_level": 0
                }
            ),
            # Robb -> Child (child relationship, generation_level = +1)
            Relationship(
                vault_id=vault_id,
                from_entity_id=robb.id,
                to_entity_id=child.id,
                rel_type=RelationType.CHILD,
                relationship_metadata={
                    "is_blood_relative": True,
                    "generation_level": 1
                }
            ),
        ]
        
        for rel in relationships:
            session.add(rel)
        session.commit()
        
        target_id = robb.id
        
    # Test: Build family tree from Robb's perspective
    print(f"\n🔍 Building family tree for: Robb Stark (ID: {target_id})")
    result = await agent.build_family_tree(target_id)
    
    print(f"\n📊 Results:")
    print(f"   - Total family members: {result['total_members']}")
    print(f"   - Generation range: {result['generation_range']['min']} to {result['generation_range']['max']}")
    
    print(f"\n👥 Family Members by Generation:")
    for gen in sorted(result['generations'].keys()):
        members = result['generations'][gen]
        gen_label = f"Generation {gen:+d}" if gen != 0 else "Same Generation (Root)"
        print(f"\n   {gen_label}:")
        for member in members:
            print(f"      - {member['name']} ({member['type']})")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    with Session(engine) as session:
        session.query(Relationship).filter(Relationship.vault_id == vault_id).delete()
        session.query(Entity).filter(Entity.vault_id == vault_id).delete()
        session.commit()
        
    print("✅ Test Complete!")

if __name__ == "__main__":
    if os.name == 'nt':
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        
    asyncio.run(test_family_tree())
