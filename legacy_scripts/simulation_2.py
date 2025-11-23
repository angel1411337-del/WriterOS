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
    print("   WriterOS V2 - Full Stack Simulation")
    print("========================================")

    # 1. Initialize
    # We use a specific test folder so we don't mess up your main vault
    # Change this to os.getenv("OBSIDIAN_VAULT_PATH") if you want to write to real vault
    test_vault_path = Path("./output/Test_Simulation")

    # Clean up previous test run
    if test_vault_path.exists():
        try:
            shutil.rmtree(test_vault_path)
        except Exception as e:
            print(f"⚠️ Could not clean folder (might be open): {e}")

    test_vault_path.mkdir(parents=True, exist_ok=True)

    print("🤖 Initializing Agents (Default Model: gpt-5.1)...")
    swarm = AgentSwarm()
    writer = ObsidianWriter(test_vault_path)

    print(f"📂 Output Target: {test_vault_path.absolute()}")
    print("\n📝 Processing Mock Data...")

    # 2. Run Profiler
    print("\n1. 🕵️ Running Profiler (V2)...")
    try:
        lore_data = await swarm.profiler.run(MOCK_TRANSCRIPT, "", "Simulation Data")
        writer.update_story_bible(lore_data, "Simulation Data")
        print(f"   ✅ Extracted {len(lore_data.characters)} Characters.")
    except Exception as e:
        print(f"   ❌ Profiler Failed: {e}")

    # 3. Run Psychologist
    print("\n2. 🧠 Running Psychologist...")
    try:
        psych_data = await swarm.psychologist.run(MOCK_TRANSCRIPT, "", "Simulation Data")
        writer.update_psych_profiles(psych_data)
        print(f"   ✅ Analyzed {len(psych_data.profiles)} Psyches.")
    except Exception as e:
        print(f"   ❌ Psychologist Failed: {e}")

    # 4. Run Navigator
    print("\n3. 🗺️ Running Navigator...")
    try:
        nav_data = await swarm.navigator.run(MOCK_TRANSCRIPT, "", "Simulation Data")
        writer.update_navigation_data(nav_data, "Simulation Data")
        print(f"   ✅ Mapped {len(nav_data.locations)} Locations.")
    except Exception as e:
        print(f"   ❌ Navigator Failed: {e}")

    # 5. Run Mechanic (The System Test)
    print("\n4. ⚙️ Running Mechanic...")
    try:
        mech_data = await swarm.mechanic.run(MOCK_TRANSCRIPT, "", "Simulation Data")

        if mech_data and mech_data.systems:
            writer.update_systems(mech_data, "Simulation Data")
            print(f"   ✅ Extracted {len(mech_data.systems)} Systems.")

            # Verify Tech Tree Logic
            for sys in mech_data.systems:
                print(f"      -> System: {sys.name}")
                for ab in sys.abilities:
                    if ab.prerequisites:
                        print(f"         🔗 Prerequisite Found: {ab.prerequisites} --> {ab.name}")
        else:
            print("   ⚠️ Mechanic returned no systems.")

    except Exception as e:
        print(f"   ❌ Mechanic Failed: {e}")

    print("\n========================================")
    print("🎉 SIMULATION COMPLETE")
    print(f"👉 Open Obsidian Folder: {test_vault_path}/Story_Bible/Systems")

if __name__ == "__main__":
    asyncio.run(run_simulation())