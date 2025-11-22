import asyncio
import os
from dotenv import load_dotenv
from agents.psychologist import PsychologistAgent

# Load API Keys
load_dotenv()

async def run_test():
    # 1. Initialize the Agent
    agent = PsychologistAgent(model_name="gpt-4o") # Use 4o for speed testing
    print("🧠 Psychologist Agent Loaded.")

    # 2. Create Fake "Transcript" Data
    # (This allows you to test specific scenarios without finding a video for them)
    mock_transcript = """
    JONATHAN: I can't go back to the city, Sarah! You don't understand. 
    They know who I am now. If I return, they'll kill me, and I can't leave my daughter alone.
    
    SARAH: You have to facing them is the only way to get your honor back.
    
    JONATHAN: Honor? You think I care about honor? I just want to survive!
    """

    print(f"\n📝 Analyzing Mock Transcript:\n{mock_transcript}\n")

    # 3. Run the Agent
    try:
        result = await agent.run(mock_transcript, existing_notes="", title="Test Scene")

        # 4. Print the Raw Output
        print("--- 📊 AGENT OUTPUT ---")
        if not result.profiles:
            print("❌ No profiles extracted.")

        for p in result.profiles:
            print(f"\n👤 Name: {p.name}")
            print(f"   Archetype: {p.archetype}")
            print(f"   Desire:    {p.core_desire}")
            print(f"   Fear:      {p.core_fear}")
            print(f"   Alignment: {p.moral_alignment}")
            print("-" * 30)

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())