"""
Test script for Producer dogfooding

This tests the Producer's ability to read its own documentation
and answer questions about WriterOS development.

Usage:
    python test_producer_dogfooding.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import agents
sys.path.append(str(Path(__file__).parent))

from agents.producer import ProducerAgent

async def test_dogfooding():
    """Test Producer reading its own roadmap and documentation"""

    print("=" * 80)
    print("PRODUCER DOGFOODING TEST")
    print("=" * 80)
    print()

    # Initialize Producer
    producer = ProducerAgent()

    # TEST 1: What should I work on?
    print("🧪 TEST 1: Today's Priority")
    print("-" * 80)
    query1 = "What should I work on today?"
    print(f"Query: {query1}")
    print()

    response1 = await producer.query(query1)
    print(f"Response:\n{response1}")
    print()
    print("=" * 80)
    print()

    # TEST 2: What's the status of Week 1?
    print("🧪 TEST 2: Sprint Status")
    print("-" * 80)
    query2 = "What is the status of Week 1 in the roadmap?"
    print(f"Query: {query2}")
    print()

    response2 = await producer.query(query2)
    print(f"Response:\n{response2}")
    print()
    print("=" * 80)
    print()

    # TEST 3: What agents are completed?
    print("🧪 TEST 3: Agent Status")
    print("-" * 80)
    query3 = "Which agents are completed and which are in progress?"
    print(f"Query: {query3}")
    print()

    response3 = await producer.query(query3)
    print(f"Response:\n{response3}")
    print()
    print("=" * 80)
    print()

    # TEST 4: Explain the 5 search modes
    print("🧪 TEST 4: Technical Question")
    print("-" * 80)
    query4 = "Explain the Producer's 5 search modes"
    print(f"Query: {query4}")
    print()

    response4 = await producer.query(query4)
    print(f"Response:\n{response4}")
    print()
    print("=" * 80)
    print()

    # TEST 5: Explicit mode - force global
    print("🧪 TEST 5: Explicit Mode (Global)")
    print("-" * 80)
    query5 = "What dependencies does the Mechanic agent have?"
    print(f"Query: {query5}")
    print(f"Mode: global (explicit)")
    print()

    response5 = await producer.query(query5, mode="global")
    print(f"Response:\n{response5}")
    print()
    print("=" * 80)
    print()

async def test_interactive():
    """Interactive mode - ask questions yourself"""

    producer = ProducerAgent()

    print("=" * 80)
    print("INTERACTIVE PRODUCER TEST")
    print("=" * 80)
    print()
    print("Ask the Producer questions about WriterOS development.")
    print("Type 'quit' or 'exit' to stop.")
    print()

    while True:
        try:
            query = input("You: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break

            if not query:
                continue

            print()
            print("Producer is thinking...")
            response = await producer.query(query)
            print()
            print(f"Producer: {response}")
            print()
            print("-" * 80)
            print()

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print()

async def test_simple():
    """Simple single query test"""

    producer = ProducerAgent()

    query = "What should I work on next?"
    print(f"Query: {query}\n")

    response = await producer.query(query)
    print(f"Producer: {response}")

if __name__ == "__main__":
    import sys

    # Check command line argument
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

        if mode == "interactive":
            asyncio.run(test_interactive())
        elif mode == "simple":
            asyncio.run(test_simple())
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python test_producer_dogfooding.py [interactive|simple]")
            print("       (default is full test suite)")
            sys.exit(1)
    else:
        # Default: Run full test suite
        asyncio.run(test_dogfooding())
