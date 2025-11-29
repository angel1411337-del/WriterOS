"""
Test script for LCEL chain implementation in ChronologistAgent.

This demonstrates:
1. LLMClient with build_chain method
2. PostgresChatHistory for conversation memory
3. ChronologistAgent with LCEL chains
4. Streaming output with .astream()
"""
import asyncio
import os
from uuid import UUID
from writeros.agents.chronologist import ChronologistAgent, TimelineExtraction
from writeros.utils.langchain_memory import PostgresChatHistory, get_or_create_conversation
from writeros.utils.llm_client import LLMClient
from langchain_core.prompts import ChatPromptTemplate

# Set UTF-8 encoding for Windows console
if os.name == 'nt':
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


async def test_llm_client_build_chain():
    """Test 1: LLMClient with build_chain method."""
    print("\n=== Test 1: LLMClient build_chain ===")

    client = LLMClient(model_name="gpt-4o-mini")

    # Create a simple chain
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("user", "{query}")
    ])

    chain = client.build_chain(prompt_template=prompt)

    result = await chain.ainvoke({"query": "What is 2+2?"})
    print(f"Result: {result[:100]}...")
    print("[PASS] Test 1 passed: build_chain works!")


async def test_postgres_chat_history():
    """Test 2: PostgresChatHistory integration."""
    print("\n=== Test 2: PostgresChatHistory ===")

    # Create or get conversation
    vault_id = UUID("b89538bf-e454-41d3-9bf7-2c8287ee1a5a")  # Genius Loci vault
    conv_id = get_or_create_conversation(vault_id, title="Test LCEL Conversation")

    # Initialize history
    history = PostgresChatHistory(conversation_id=conv_id, agent_name="TestAgent")

    # Add messages
    history.add_user_message("Tell me about timeline events.")
    history.add_ai_message("The timeline includes several key events...")

    # Retrieve messages
    messages = history.messages
    print(f"Messages retrieved: {len(messages)}")
    for msg in messages:
        # Handle Windows encoding by removing emojis
        content = msg.content[:50].encode('ascii', errors='ignore').decode('ascii')
        print(f"  - {msg.__class__.__name__}: {content}...")

    print("[PASS] Test 2 passed: PostgresChatHistory works!")


async def test_chronologist_lcel():
    """Test 3: ChronologistAgent with existing LCEL chain."""
    print("\n=== Test 3: ChronologistAgent LCEL ===")

    agent = ChronologistAgent(model_name="gpt-4o-mini")

    # Test the existing run() method which already uses LCEL
    result = await agent.run(
        full_text="Jon travels from Winterfell to Castle Black, taking 14 days. He joins the Night's Watch.",
        existing_notes="",
        title="Test Journey"
    )

    print(f"Events extracted: {len(result.events)}")
    for event in result.events:
        print(f"  - {event.order}: {event.title} - {event.summary[:50]}...")

    print("[PASS] Test 3 passed: ChronologistAgent LCEL works!")


async def test_streaming_output():
    """Test 4: Streaming output with .astream()."""
    print("\n=== Test 4: Streaming output ===")

    client = LLMClient(model_name="gpt-4o-mini")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("user", "{query}")
    ])

    # Build chain without parser to enable streaming
    chain = client.build_chain(prompt_template=prompt)

    print("Streaming response: ", end="", flush=True)
    async for chunk in chain.astream({"query": "Count from 1 to 5 slowly."}):
        print(chunk, end="", flush=True)

    print("\n[PASS] Test 4 passed: Streaming works!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("LCEL Chain Implementation Tests")
    print("=" * 60)

    try:
        await test_llm_client_build_chain()
        await test_postgres_chat_history()
        await test_chronologist_lcel()
        await test_streaming_output()

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL TESTS PASSED!")
        print("=" * 60)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
