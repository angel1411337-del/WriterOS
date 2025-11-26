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

from writeros.schema.organization import Organization
from writeros.schema.family import Family, FamilyMember
from writeros.schema.group import Group, GroupMember
from writeros.schema.world import Entity
from writeros.schema.identity import User, Vault
from writeros.schema.enums import EntityType

# Setup in-memory DB
engine = create_engine("sqlite:///:memory:")

def setup_module():
    SQLModel.metadata.create_all(engine)

def test_gendry_case():
    """
    Test the Gendry use case:
    - ✅ IN Baratheon Family (bloodline, but illegitimate)
    - ❌ NOT IN House Baratheon organization (bastard = no formal membership)
    - ❌ NOT IN any political faction
    - ✅ IN Smallfolk group (grew up as apprentice)
    """
    with Session(engine) as session:
        # Setup
        user = User(email="test@test.com", username="tester")
        session.add(user)
        session.commit()
        
        vault = Vault(name="Test Vault", owner_id=user.id)
        session.add(vault)
        session.commit()
        
        # Create Gendry
        gendry = Entity(
            name="Gendry",
            type=EntityType.CHARACTER,
            vault_id=vault.id,
            description="Bastard son of Robert Baratheon"
        )
        session.add(gendry)
        
        # Create Robert Baratheon
        robert = Entity(
            name="Robert Baratheon",
            type=EntityType.CHARACTER,
            vault_id=vault.id
        )
        session.add(robert)
        
        # Create House Baratheon (Organization)
        baratheon_org_entity = Entity(
            name="House Baratheon",
            type=EntityType.ORGANIZATION,
            vault_id=vault.id
        )
        session.add(baratheon_org_entity)
        session.commit()
        
        house_baratheon = Organization(
            vault_id=vault.id,
            entity_id=baratheon_org_entity.id,
            organization_type="noble_house",
            leader_id=robert.id,
            member_ids=[str(robert.id)]  # Gendry NOT in this list
        )
        session.add(house_baratheon)
        
        # Create Baratheon Family (Bloodline)
        baratheon_family = Family(
            vault_id=vault.id,
            family_name="Baratheon",
            legitimate_member_ids=[str(robert.id)],
            bastard_member_ids=[str(gendry.id)],  # Gendry IS here
            current_head_id=robert.id
        )
        session.add(baratheon_family)
        
        # Link Gendry to Baratheon Family
        gendry_family_link = FamilyMember(
            vault_id=vault.id,
            family_id=baratheon_family.id,
            character_id=gendry.id,
            is_legitimate=False,  # CRITICAL: He's a bastard
            parent_id=robert.id,
            can_inherit=False  # Bastards can't inherit
        )
        session.add(gendry_family_link)
        
        # Create Smallfolk Group
        smallfolk_entity = Entity(
            name="Smallfolk",
            type=EntityType.GROUP,
            vault_id=vault.id
        )
        session.add(smallfolk_entity)
        session.commit()
        
        smallfolk_group = Group(
            vault_id=vault.id,
            entity_id=smallfolk_entity.id,
            name="Smallfolk",
            category_type="social_class",
            membership_criteria="birth, occupation",
            social_hierarchy_level=1
        )
        session.add(smallfolk_group)
        
        # Link Gendry to Smallfolk
        gendry_group_link = GroupMember(
            vault_id=vault.id,
            group_id=smallfolk_group.id,
            entity_id=gendry.id,
            membership_type="born_into"
        )
        session.add(gendry_group_link)
        session.commit()
        
        # ============================================
        # VERIFICATION
        # ============================================
        
        # 1. Verify Gendry is in Baratheon bloodline but NOT legitimate
        family_link = session.exec(
            select(FamilyMember).where(FamilyMember.character_id == gendry.id)
        ).first()
        assert family_link is not None
        assert family_link.is_legitimate == False
        assert family_link.can_inherit == False
        
        # 2. Verify Gendry is NOT in House Baratheon organization
        org = session.get(Organization, house_baratheon.id)
        assert str(gendry.id) not in org.member_ids
        
        # 3. Verify Gendry IS in Smallfolk group
        group_link = session.exec(
            select(GroupMember).where(
                GroupMember.entity_id == gendry.id,
                GroupMember.group_id == smallfolk_group.id
            )
        ).first()
        assert group_link is not None
        
        print("\n✅ Gendry Test Case Passed!")
        print(f"  ✅ IN Baratheon Family (bastard: {not family_link.is_legitimate})")
        print(f"  ❌ NOT IN House Baratheon Organization")
        print(f"  ✅ IN Smallfolk Group")
        print(f"  ❌ Cannot Inherit: {not family_link.can_inherit}")

if __name__ == "__main__":
    setup_module()
    test_gendry_case()
