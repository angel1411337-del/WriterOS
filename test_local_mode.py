import asyncio
import logging
from agents.producer import ProducerAgent
from utils.db import init_db
from utils.embeddings import embedding_service

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_local_mode():
    print("Starting Local Mode Verification...")
    
    # 1. Initialize DB (ensure vector extension exists)
    init_db()
    
    # 2. Initialize Producer
    producer = ProducerAgent()
    
    # 3. Test Query
    # Note: This test assumes there might be some data, or at least it shouldn't crash.
    # If DB is empty, it should return "No relevant information found..."
    query = "What is the main conflict?"
    print(f"\nQuery: {query}")
    
    try:
        response = await producer.query(query, mode="local")
        print(f"\nResponse:\n{response}")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(test_local_mode())
