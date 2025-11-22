import asyncio
import os
from uuid import uuid4
from agents.architect import ArchitectAgent
from agents.schema import Anchor, AnchorStatus, Entity, EntityType
from sqlmodel import Session, select
from utils.db import engine

async def test_anchors():
    print("🚀 Starting Architect Anchors Test...")
    
    # Initialize Agent
    agent = ArchitectAgent()
    
    # Create a dummy Anchor
    test_anchor_name = f"Test Anchor {uuid4().hex[:4]}"
    print(f"🛠️ Creating test anchor: {test_anchor_name}")
    
    # We need a valid vault_id. Let's use a dummy one or find one.
    # For simplicity, we'll create a dummy vault entity first if needed, or just use a random UUID.
    vault_id = uuid4()
    
    with Session(engine) as session:
        anchor = Anchor(
            vault_id=vault_id,
            name=test_anchor_name,
            description="The protagonist must discover the hidden door.",
            status=AnchorStatus.PENDING,
            anchor_category="plot"
        )
        session.add(anchor)
        session.commit()
        session.refresh(anchor)
        anchor_id = anchor.id
        
    # 1. Test List Anchors
    print("📋 Testing list_anchors...")
    anchors = await agent.list_anchors(status=AnchorStatus.PENDING)
    found = any(a.name == test_anchor_name for a in anchors)
    print(f"   - Found test anchor: {'✅' if found else '❌'}")
    
    # 2. Test Critique Draft
    print("📝 Testing critique_draft...")
    draft = "The protagonist walked around the room and finally noticed a faint outline on the wall. He pushed it, and a hidden door slid open."
    critique = await agent.critique_draft(draft, context="A mysterious room.")
    print(f"   - Critique received (Length: {len(critique)})")
    # print(critique) # Optional: print full critique
    
    # 3. Test Review Anchor Progress
    print("🕵️ Testing review_anchor_progress...")
    progress = await agent.review_anchor_progress(draft)
    print(f"   - Progress Report: {progress}")
    
    # Cleanup
    print("🧹 Cleaning up...")
    with Session(engine) as session:
        a = session.get(Anchor, anchor_id)
        if a:
            session.delete(a)
            session.commit()
            
    print("✅ Test Complete.")

if __name__ == "__main__":
    # Set encoding for Windows
    if os.name == 'nt':
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        
    asyncio.run(test_anchors())
