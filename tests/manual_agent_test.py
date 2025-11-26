import asyncio
import os
import sys
from uuid import uuid4

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from writeros.agents.orchestrator import OrchestratorAgent
from writeros.agents.navigator import NavigatorAgent

async def test_navigator_risen():
    print("🤖 Initializing NavigatorAgent...")
    navigator = NavigatorAgent()
    
    # Query that requires RAG (implicit destination, unknown speed)
    # "Ned" implies King's Landing (if RAG knows context)
    # "Letter" implies Raven
    query = "Can a letter from Winterfell reach Ned in King's Landing before the Littlefinger scene?"
    
    print(f"\n\n📝 Sending Travel Query: '{query}'\n" + "="*50)
    
    # We need to mock existing_notes or rely on RAG
    # Since we just integrated RAG, let's see if it works.
    # Note: RAG might be empty if DB is empty. 
    # But Navigator should still attempt queries and return "No canonical data" or similar.
    
    result = await navigator.run(query, existing_notes="", title="Test Query")
    
    print("\n\n📊 Navigator Result:")
    print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    asyncio.run(test_navigator_risen())
