import asyncio
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Import the Swarm
from agents import AgentSwarm
# Import the Writer (Ensure utils/writer.py matches the code you provided)
from utils.writer import ObsidianWriter

load_dotenv()

# --- THE SCENARIO ---
# Combined Story + Mechanic Stress Test
MOCK_TRANSCRIPT = """
The war for the Iron Valley has begun. 
Lord Silas, a man driven by a deep fear of poverty, sits on the throne of the Iron Keep. 
He hates his brother, General Kael, who leads the Rebellion. 
Kael is an idealist who desires freedom for the people, but his reckless nature makes him dangerous.

To reach the Iron Keep from Kael's camp in the Whispering Woods, the army must travel East. 
It is a slow three-day march through the Swamp of Sorrows. 
However, if they take the river barges, they can reach the Keep in just 12 hours.

In the Iron Kingdom, soldiers use Steam Rifles. 
Firing one costs 1 Water Canister. It overheats after 3 shots. 
To use the Rifle, you must first master the Steam Valve technique.
"""

async def run_simulation():
    print("========================================")
    print("   WriterOS V3 - Mechanic Simulation")
    print("========================================")

    # 1. Initialize
    test_vault_path = Path("./output/Test_Simulation")

    # Clean up previous test run
    if test_vault_path.exists():
        shutil.rmtree(test_vault_path)
    test_vault_path.mkdir(parents=True, exist_ok=True)

    print("🤖 Initializing Agents...")
    swarm = AgentSwarm()
    writer = ObsidianWriter(test_vault_path)

    print(f"📂 Output Target: {test_vault_path.absolute()}")
    print("\n📝 Processing Mock Data...")

    # 2. Run Profiler
    print("\n1. 🕵️ Running Profiler...")
    lore_data = await swarm.profiler.run(MOCK_TRANSCRIPT, "", "Simulation Data")
    writer.update_story_bible(lore_data, "Simulation Data")
    print(f"   ✅ Extracted {len(lore_data.characters)} Characters.")

    # 3. Run Psychologist
    print("\n2. 🧠 Running Psychologist...")
    psych_data = await swarm.psychologist.run(MOCK_TRANSCRIPT, "", "Simulation Data")
    writer.update_psych_profiles(psych_data)
    print(f"   ✅ Analyzed {len(psych_data.profiles)} Psyches.")

    # 4. Run Navigator
    print("\n3. 🗺️ Running Navigator...")
    nav_data = await swarm.navigator.run(MOCK_TRANSCRIPT, "", "Simulation Data")
    writer.update_navigation_data(nav_data, "Simulation Data")
    print(f"   ✅ Mapped {len(nav_data.locations)} Locations.")



    # 5. Run Mechanic (The Test Case)
    print("\n4. ⚙️ Running Mechanic...")
    mech_data = await swarm.mechanic.run(MOCK_TRANSCRIPT, "", "Simulation Data")

    # --- DEBUG PRINT START ---
    print("\n🔎 RAW AI DATA RECEIVED:")
    if mech_data and mech_data.systems:
        for sys in mech_data.systems:
            print(f"   System: {sys.name}")
            for ab in sys.abilities:
                print(f"      - Ability: {ab.name}")
                print(f"        Prerequisite detected: '{ab.prerequisites}'") # <--- CHECK THIS
    # --- DEBUG PRINT END ---

    if mech_data and len(mech_data.systems) > 0:
        writer.update_systems(mech_data, "Simulation Data")
        print(f"\n   ✅ Extracted {len(mech_data.systems)} Systems.")
        print("   👉 Check 'output/Test_Simulation/Story_Bible/Systems' for the .md file.")
    else:
        print("   ❌ Mechanic failed to extract data.")

    print("\n========================================")
    print("🎉 SIMULATION COMPLETE")

if __name__ == "__main__":
    asyncio.run(run_simulation())