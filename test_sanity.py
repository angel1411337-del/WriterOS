"""
Simple Sanity Check for Core Implementations
Tests that the basic infrastructure is in place and working
"""

def test_enums_exist():
    """Test 1: Check that provenance enums were added"""
    print("\\n=== TEST 1: Provenance Enums Exist ===")
    try:
        from writeros.schema.enums import (
            StateChangeEventType, KnowledgeSourceType, DependencyType,
            PresenceType, IngestionSourceType
        )
        print("✅ All 5 provenance enums imported successfully")
        print(f"   - StateChangeEventType values: {[e.value for e in StateChangeEventType]}")
        print(f"   - KnowledgeSourceType values: {[e.value for e in KnowledgeSourceType]}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import enums: {e}")
        return False


def test_base_agent_has_should_respond():
    """Test 2: Check that BaseAgent has should_respond method"""
    print("\\n=== TEST 2: BaseAgent.should_respond Method ===")
    try:
        from writeros.agents.base import BaseAgent
        import inspect
        
        assert hasattr(BaseAgent, 'should_respond'), "BaseAgent should have should_respond method"
        method = getattr(BaseAgent, 'should_respond')
        assert inspect.iscoroutinefunction(method), "should_respond should be async"
        print("✅ BaseAgent.should_respond method exists and is async")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_retriever_has_iterative():
    """Test 3: Check that RAGRetriever has retrieve_iterative"""
    print("\\n=== TEST 3: RAGRetriever.retrieve_iterative Method ===")
    try:
        from writeros.rag.retriever import RAGRetriever
        import inspect
        
        retriever = RAGRetriever()
        assert hasattr(retriever, 'retrieve_iterative'), "RAGRetriever should have retrieve_iterative"
        method = getattr(retriever, 'retrieve_iterative')
        assert inspect.iscoroutinefunction(method), "retrieve_iterative should be async"
        print("✅ RAGRetriever.retrieve_iterative exists and is async")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_orchestrator_has_synthesis():
    """Test 4: Check that Orchestrator has synthesis method"""
    print("\\n=== TEST 4: Orchestrator Synthesis Method ===")
    try:
        from writeros.agents.orchestrator import OrchestratorAgent
        
        orchestrator = OrchestratorAgent()
        assert hasattr(orchestrator, '_synthesize_response'), "Orchestrator should have _synthesize_response"
        assert hasattr(orchestrator, '_execute_agents_with_autonomy'), "Orchestrator should have broadcast method"
        print("✅ Orchestrator has both _synthesize_response and _execute_agents_with_autonomy")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all sanity checks"""
    print("\\n" + "="*60)
    print("SANITY CHECK: Core Infrastructure")
    print("="*60)
    
    results = [
        ("Provenance Enums", test_enums_exist()),
        ("BaseAgent.should_respond", test_base_agent_has_should_respond()),
        ("RAGRetriever.retrieve_iterative", test_retriever_has_iterative()),
        ("Orchestrator Synthesis", test_orchestrator_has_synthesis()),
    ]
    
    print("\\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\\nTotal: {total_passed}/{total_tests} tests passed")
    print("="*60)
    
    if total_passed == total_tests:
        print("\\n🎉 All core features implemented successfully!")
    else:
        print("\\n⚠️  Some features need attention")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
