import asyncio
import logging
from agents.profiler import ProfilerAgent
from agents.psychologist import PsychologistAgent
from utils.db import init_db

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_psych_profiler_embeddings():
    print("Starting Profiler & Psychologist Embeddings Verification...")
    
    # 1. Initialize DB
    init_db()
    
    # 2. Initialize Agents
    profiler = ProfilerAgent()
    psychologist = PsychologistAgent()
    
    # 3. Test Profiler Entity Search
    print("\nTesting Profiler Entity Search...")
    entities = await profiler.find_similar_entities("Honorable warrior")
    print(f"Entities Found:\n{entities}")
    
    # 4. Test Psychologist State Search
    print("\nTesting Psychologist State Search...")
    states = await psychologist.find_similar_states("Fear of abandonment")
    print(f"States Found:\n{states}")

if __name__ == "__main__":
    asyncio.run(test_psych_profiler_embeddings())
