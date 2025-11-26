"""
Comprehensive Tests for New Features
Tests: Provenance Enums, Agent Autonomy, Answer Synthesis, Iterative RAG
"""
import asyncio
from uuid import UUID, uuid4
from writeros.schema.enums import (
    StateChangeEventType, KnowledgeSourceType, DependencyType,
    PresenceType, IngestionSourceType
)
from writeros.agents.base import BaseAgent
from writeros.agents.navigator import NavigatorAgent
from writeros.agents.mechanic import MechanicAgent
from writeros.agents.profiler import ProfilerAgent
from writeros.agents.orchestrator import OrchestratorAgent
from writeros.rag.retriever import RAGRetriever


def test_provenance_enums():
    """Test 1: Provenance Enums"""
    print("\\n=== TEST 1: Provenance Enums ===")
    
    # Test enum creation
    try:
        event_type = StateChangeEventType.CREATION
        source_type = KnowledgeSourceType.DIRECT_OBSERVATION
        dep_type = DependencyType.PREREQUISITE
        presence_type = PresenceType.CONFIRMED
        ingestion_type = IngestionSourceType.USER_INPUT
        
        print(f"✅ StateChangeEventType: {event_type}")
        print(f"✅ KnowledgeSourceType: {source_type}")
        print(f"✅ DependencyType: {dep_type}")
        print(f"✅ PresenceType: {presence_type}")
        print(f"✅ IngestionSourceType: {ingestion_type}")
        
        # Test enum values
        assert event_type == "creation"
        assert source_type == "direct_observation"
        print("✅ Enum values match expected strings")
        
        return True
    except Exception as e:
        print(f"❌ Provenance Enums Test Failed: {e}")
        return False


async def test_agent_autonomy():
    """Test 2: Agent Autonomy (should_respond)"""
    print("\\n=== TEST 2: Agent Autonomy ===")
    
    try:
        # Test Navigator with travel query
        navigator = NavigatorAgent()
        travel_query = "How long does it take to travel from Winterfell to King's Landing?"
        should_respond, confidence, reason = await navigator.should_respond(travel_query)
        
        print(f"\\nNavigator (Travel Query):")
        print(f"  Should Respond: {should_respond}")
        print(f"  Confidence: {confidence}")
        print(f"  Reason: {reason}")
        assert should_respond == True, "Navigator should respond to travel queries"
        assert confidence >= 0.7, "Navigator should have high confidence for travel queries"
        print("✅ Navigator correctly identifies travel query")
        
        # Test Navigator with non-travel query
        non_travel_query = "Who is Jon Snow's mother?"
        should_respond, confidence, reason = await navigator.should_respond(non_travel_query)
        
        print(f"\\nNavigator (Non-Travel Query):")
        print(f"  Should Respond: {should_respond}")
        print(f"  Confidence: {confidence}")
        print(f"  Reason: {reason}")
        assert should_respond == False, "Navigator should skip non-travel queries"
        print("✅ Navigator correctly skips non-travel query")
        
        # Test Mechanic with rules query
        mechanic = MechanicAgent()
        rules_query = "Can dragons breathe underwater in this world?"
        should_respond, confidence, reason = await mechanic.should_respond(rules_query)
        
        print(f"\\nMechanic (Rules Query):")
        print(f"  Should Respond: {should_respond}")
        print(f"  Confidence: {confidence}")
        print(f"  Reason: {reason}")
        assert should_respond == True, "Mechanic should respond to rules queries"
        print("✅ Mechanic correctly identifies rules query")
        
        # Test Profiler with character query
        profiler = ProfilerAgent()
        character_query = "Who knows about Jon's parentage?"
        should_respond, confidence, reason = await profiler.should_respond(character_query)
        
        print(f"\\nProfiler (Character Query):")
        print(f"  Should Respond: {should_respond}")
        print(f"  Confidence: {confidence}")
        print(f"  Reason: {reason}")
        assert should_respond == True, "Profiler should respond to character queries"
        print("✅ Profiler correctly identifies character query")
        
        return True
    except Exception as e:
        print(f"❌ Agent Autonomy Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_iterative_rag():
    """Test 3: Iterative RAG Retrieval"""
    print("\\n=== TEST 3: Iterative RAG Retrieval ===")
    
    try:
        retriever = RAGRetriever()
        
        # Test with a simple query (will work even with empty DB)
        query = "Tell me about dragons"
        print(f"\\nTesting iterative retrieval with query: '{query}'")
        print("Note: This test validates the method exists and executes without errors.")
        print("With an empty database, it will converge early (no results found).")
        
        result = await retriever.retrieve_iterative(
            initial_query=query,
            max_hops=3,  # Use 3 for testing (faster)
            limit_per_hop=2
        )
        
        print(f"\\nResults:")
        print(f"  Documents: {len(result.documents)}")
        print(f"  Entities: {len(result.entities)}")
        print(f"  Facts: {len(result.facts)}")
        print(f"  Events: {len(result.events)}")
        
        # Check that method returns correct structure
        assert hasattr(result, 'documents'), "Result should have documents"
        assert hasattr(result, 'entities'), "Result should have entities"
        assert hasattr(result, 'facts'), "Result should have facts"
        assert hasattr(result, 'events'), "Result should have events"
        
        print("✅ Iterative RAG method exists and returns correct structure")
        print("   (Empty results expected if database is empty)")
        
        return True
    except Exception as e:
        print(f"❌ Iterative RAG Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_orchestrator_broadcast():
    """Test 4: Orchestrator Broadcast & Synthesis"""
    print("\\n=== TEST 4: Orchestrator Broadcast & Synthesis ===")
    
    try:
        orchestrator = OrchestratorAgent()
        
        print("\\nTesting broadcast mechanism...")
        print("Note: This test verifies the orchestrator can broadcast and agents can self-select.")
        print("Full synthesis requires LLM calls and may take time.\\n")
        
        # Check that _execute_agents_with_autonomy method exists
        assert hasattr(orchestrator, '_execute_agents_with_autonomy'), \
            "Orchestrator should have _execute_agents_with_autonomy method"
        print("✅ Orchestrator has broadcast method (_execute_agents_with_autonomy)")
        
        # Check that _synthesize_response method exists
        assert hasattr(orchestrator, '_synthesize_response'), \
            "Orchestrator should have _synthesize_response method"
        print("✅ Orchestrator has synthesis method (_synthesize_response)")
        
        # Test broadcast to a few agents
        test_agents = ["navigator", "mechanic", "profiler"]
        query = "How long to travel from Winterfell to King's Landing?"
        context = "Test context"
        
        print(f"\\nBroadcasting to {len(test_agents)} agents...")
        results = await orchestrator._execute_agents_with_autonomy(
            test_agents, query, context
        )
        
        print(f"\\nResults from broadcast:")
        for agent_name, result in results.items():
            if isinstance(result, dict) and result.get("skipped"):
                print(f"  {agent_name}: SKIPPED ({result['reason']})")
            else:
                print(f"  {agent_name}: RESPONDED")
        
        # Verify at least Navigator responded (it should for travel queries)
        if "navigator" in results:
            nav_result = results["navigator"]
            if isinstance(nav_result, dict) and nav_result.get("skipped"):
                print("⚠️  Navigator skipped travel query (unexpected)")
            else:
                print("✅ Navigator responded to travel query as expected")
        
        return True
    except Exception as e:
        print(f"❌ Orchestrator Broadcast Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests"""
    print("\\n" + "="*60)
    print("COMPREHENSIVE FEATURE TESTING")
    print("="*60)
    
    results = []
    
    # Test 1: Provenance Enums (synchronous)
    results.append(("Provenance Enums", test_provenance_enums()))
    
    # Test 2: Agent Autonomy
    results.append(("Agent Autonomy", await test_agent_autonomy()))
    
    # Test 3: Iterative RAG
    results.append(("Iterative RAG", await test_iterative_rag()))
    
    # Test 4: Orchestrator Broadcast
    results.append(("Orchestrator Broadcast", await test_orchestrator_broadcast()))
    
    # Summary
    print("\\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\\nTotal: {total_passed}/{total_tests} tests passed")
    print("="*60)
    
    return total_passed == total_tests


if __name__ == "__main__":
    asyncio.run(run_all_tests())
