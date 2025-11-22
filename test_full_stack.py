import asyncio
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Import your actual Swarm and Writer to test the real code
from agents import AgentSwarm
from utils.writer import ObsidianWriter # <--- ✅ FIXED: Imports V2 Writer

load_dotenv()

# --- THE SCENARIO ---
# A fake story segment designed to stress-test every agent.
MOCK_TRANSCRIPT = """
The war for the Iron Valley has begun. 
Lord Silas, a man driven by a deep fear of poverty, sits on the throne of the Iron Keep. 
He hates his brother, General Kael, who leads the Rebellion. 
Kael is an idealist who desires freedom for the people, but his reckless nature makes him dangerous.

To reach the Iron Keep from Kael's camp in the Whispering Woods, the army must travel East. 
It is a slow three-day march through the Swamp of Sorrows. 
However, if they take the river barges, they can reach the Keep in just 12 hours.
The Iron Keep connects to the capital city via the King's Road, which is a one-week ride by horse.
"""

async def run_simulation():
    print("========================================")
    print("   WriterOS V2 - Full Stack Simulation")
    print("========================================")

    # 1. Initialize
    # We use a specific test folder so we don't mess up your main vault
    test_vault_path = Path("./output/Test_Simulation")

    # Clean up previous test run
    if test_vault_path.exists():
        shutil.rmtree(test_vault_path)
    test_vault_path.mkdir(parents=True, exist_ok=True)

    print("🤖 Initializing Agents...")
    # Uses default model from base.py (gpt-5.1)
    swarm = AgentSwarm()
    writer = ObsidianWriter(test_vault_path)

    print(f"📂 Output Target: {test_vault_path.absolute()}")
    print("\n📝 Processing Mock Data...")

    # 2. Run Profiler (Genealogy & Relations)
    print("\n1. 🕵️ Running Profiler (V2)...")
    # Pass the DB-aware writer
    lore_data = await swarm.profiler.run(MOCK_TRANSCRIPT, "", "Simulation Data")
    writer.update_story_bible(lore_data, "Simulation Data")
    print(f"   ✅ Extracted {len(lore_data.characters)} Characters.")

    # 3. Run Psychologist (Internal State)
    print("\n2. 🧠 Running Psychologist...")
    psych_data = await swarm.psychologist.run(MOCK_TRANSCRIPT, "", "Simulation Data")
    writer.update_psych_profiles(psych_data)
    print(f"   ✅ Analyzed {len(psych_data.profiles)} Psyches.")

    # 4. Run Navigator (The Map)
    print("\n3. 🗺️ Running Navigator...")
    nav_data = await swarm.navigator.run(MOCK_TRANSCRIPT, "", "Simulation Data")
    writer.update_navigation_data(nav_data, "Simulation Data")
    print(f"   ✅ Mapped {len(nav_data.locations)} Locations.")

    print("\n========================================")
    print("🎉 SIMULATION COMPLETE")
    print("Check the 'output/Test_Simulation' folder to see the results.")

if __name__ == "__main__":
    asyncio.run(run_simulation())