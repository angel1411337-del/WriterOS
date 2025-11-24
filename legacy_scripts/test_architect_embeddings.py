import asyncio
import logging
from agents.architect import ArchitectAgent
from utils.db import init_db

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_architect_embeddings():
    print("Starting Architect Embeddings Verification...")
    
    # 1. Initialize DB
    init_db()
    
    # 2. Initialize Architect
    architect = ArchitectAgent()
    
    # 3. Test Scene Search
    print("\nTesting Scene Search...")
    scenes = await architect.find_similar_scenes("High stakes battle")
    print(f"Scenes Found:\n{scenes}")
    
    # 4. Test Plot Point Search
    print("\nTesting Plot Point Search...")
    events = await architect.find_related_plot_points("Betrayal")
    print(f"Events Found:\n{events}")

if __name__ == "__main__":
    asyncio.run(test_architect_embeddings())
