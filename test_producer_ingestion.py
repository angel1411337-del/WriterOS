import asyncio
import os
from agents.producer import ProducerAgent
from sqlmodel import Session, select, func
from utils.db import engine
from agents.schema import Document

async def test_ingestion():
    print("🚀 Starting Producer Ingestion Test...")
    
    # Initialize Agent
    agent = ProducerAgent()
    
    # Run Ingestion (skip if already done to save time/money, but for now let's just check DB)
    # print(f"📂 Ingesting from: {agent.vault_root}")
    # result = await agent.ingest_vault()
    # print(result)
    
    # Verify DB
    with Session(engine) as session:
        count = session.exec(select(func.count(Document.id))).one()
        print(f"📊 Total Documents in DB: {count}")
        
        # Check for specific files if count > 0
        if count > 0:
            docs = session.exec(select(Document).limit(5)).all()
            for d in docs:
                has_embedding = d.embedding is not None and len(d.embedding) > 0
                print(f"   - {d.title} (Size: {len(d.content)} chars, Embedding: {'✅' if has_embedding else '❌'})")
                
    print("✅ Test Complete.")

if __name__ == "__main__":
    # Set encoding for Windows
    if os.name == 'nt':
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        
    asyncio.run(test_ingestion())
