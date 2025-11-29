"""
Example: Using Execution Tracking with PsychologistAgent

Demonstrates how to integrate the execution tracking system
into the POV-aware analyze_character method.

This example shows:
1. Creating an execution tracker
2. Tracking stages and events
3. LLM request/response tracking
4. Setting output data
5. Debugging failed executions
"""
import asyncio
from uuid import uuid4
from writeros.agents.psychologist import PsychologistAgent
from writeros.utils.execution_analytics import ExecutionAnalytics
from writeros.schema import ExecutionStage


async def example_successful_execution():
    """Example of a successful execution with tracking"""
    print("\n=== Example 1: Successful Execution ===\n")

    # Setup
    agent = PsychologistAgent()
    vault_id = uuid4()
    character_id = uuid4()

    # Create tracker
    tracker = agent.create_tracker(
        vault_id=vault_id,
        conversation_id=uuid4()
    )

    # Track execution
    async with tracker.track_execution(
        method="analyze_character",
        input_data={
            "character_id": str(character_id),
            "vault_id": str(vault_id)
        }
    ):
        # Track stage: Checking relevance (if applicable)
        await agent.log_event("Starting character analysis", level="info")

        # Track stage: Querying POVBoundary
        await tracker.track_stage(
            ExecutionStage.PRE_PROCESS,
            "Querying POVBoundary table for character knowledge"
        )

        # Simulate POV query (in real code, this would be actual DB query)
        await agent.log_event(
            "Found POV boundary records",
            level="debug",
            character_id=str(character_id),
            known_facts_count=15,
            blocked_facts_count=8
        )

        await tracker.complete_stage(
            ExecutionStage.PRE_PROCESS,
            {"known_facts": 15, "blocked_facts": 8}
        )

        # Track LLM interaction
        await tracker.track_stage(
            ExecutionStage.LLM_PREPARE,
            "Preparing psychological analysis prompt"
        )

        llm_request = {
            "messages": [
                {"role": "system", "content": "You are analyzing character psychology..."},
                {"role": "user", "content": "Analyze this character's state..."}
            ],
            "temperature": 0.7
        }

        await tracker.track_llm_request("gpt-5.1", llm_request)

        # Simulate LLM call
        await asyncio.sleep(0.1)  # Simulate network latency

        llm_response = {
            "content": "Character shows signs of internal conflict..."
        }

        await tracker.track_llm_response(
            llm_response,
            tokens_used=1234,
            latency_ms=2300
        )

        await tracker.complete_stage(ExecutionStage.LLM_CALL)

        # Track post-processing
        await tracker.track_stage(
            ExecutionStage.POST_PROCESS,
            "Processing psychological analysis"
        )

        result = {
            "character_name": "Frodo Baggins",
            "character_id": str(character_id),
            "known_facts_count": 15,
            "blocked_facts_count": 8,
            "psychological_profile": "Character shows signs of internal conflict..."
        }

        await tracker.complete_stage(ExecutionStage.POST_PROCESS)

        # Set output
        tracker.set_output(result)

        await agent.log_event("Analysis complete", level="info")

    # After execution, query the results
    print(f"Execution ID: {tracker.execution_id}")

    # Get execution details
    execution_details = ExecutionAnalytics.get_execution_with_logs(tracker.execution_id)
    print(f"\nExecution Status: {execution_details['execution'].status}")
    print(f"Duration: {execution_details['execution'].duration_ms}ms")
    print(f"\nStage Timeline:")
    for log in execution_details['logs']:
        print(f"  {log.stage.value}: {log.message} ({log.duration_ms}ms)")


async def example_failed_execution():
    """Example of handling failed execution"""
    print("\n\n=== Example 2: Failed Execution ===\n")

    agent = PsychologistAgent()
    vault_id = uuid4()
    character_id = uuid4()

    tracker = agent.create_tracker(vault_id=vault_id)

    try:
        async with tracker.track_execution(
            method="analyze_character",
            input_data={"character_id": str(character_id)}
        ):
            await agent.log_event("Starting analysis", level="info")

            # Simulate failure during LLM call
            await tracker.track_stage(ExecutionStage.LLM_CALL, "Calling LLM")

            # Simulate an error
            raise ValueError("LLM API returned invalid response")

    except ValueError as e:
        # Tracker automatically captures the error
        print(f"Execution failed: {e}")

    # Debug the failure
    execution = ExecutionAnalytics.get_execution(tracker.execution_id)
    print(f"\nExecution ID: {tracker.execution_id}")
    print(f"Status: {execution.status}")
    print(f"Error Type: {execution.error_type}")
    print(f"Error Message: {execution.error_message}")
    print(f"Failed at Stage: {execution.current_stage}")
    print(f"\nStack Trace:\n{execution.error_traceback}")


async def example_skipped_execution():
    """Example of agent skipping due to relevance check"""
    print("\n\n=== Example 3: Skipped Execution ===\n")

    agent = PsychologistAgent()
    vault_id = uuid4()

    tracker = agent.create_tracker(vault_id=vault_id)

    async with tracker.track_execution(
        method="run",
        input_data={"query": "What is the plot structure?"}
    ):
        # Relevance check
        should_respond = False
        confidence = 0.2
        reasoning = "Query is about plot structure, not character psychology"

        await tracker.track_should_respond(should_respond, confidence, reasoning)

        if not should_respond:
            await agent.log_event("Agent skipping due to low relevance", level="info")
            return None

    # Query skipped executions
    execution = ExecutionAnalytics.get_execution(tracker.execution_id)
    print(f"Execution ID: {tracker.execution_id}")
    print(f"Status: {execution.status}")
    print(f"Relevance Score: {execution.relevance_score}")
    print(f"Reasoning: {execution.relevance_reasoning}")


async def example_debugging_workflow():
    """Example debugging workflow for agent issues"""
    print("\n\n=== Example 4: Debugging Workflow ===\n")

    vault_id = uuid4()
    conversation_id = uuid4()

    # Scenario: Psychologist agent didn't fire, need to debug why
    print("Debugging why PsychologistAgent didn't fire...\n")

    result = ExecutionAnalytics.debug_why_agent_didnt_fire(
        agent_name="PsychologistAgent",
        conversation_id=conversation_id,
        vault_id=vault_id
    )

    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")

    if result['status'] == 'never_invoked':
        print("\nPossible Reasons:")
        for reason in result.get('possible_reasons', []):
            print(f"  - {reason}")

    elif result['status'] == 'skipped':
        print("\nSkipped Executions:")
        for ex in result.get('executions', []):
            print(f"  - Execution {ex['execution_id']}")
            print(f"    Relevance Score: {ex['relevance_score']}")
            print(f"    Reasoning: {ex['relevance_reasoning']}")

    elif result['status'] == 'failed':
        print("\nFailed Executions:")
        for ex in result.get('executions', []):
            print(f"  - Execution {ex['execution_id']}")
            print(f"    Error: {ex['error_type']}: {ex['error_message']}")
            print(f"    Stage: {ex['current_stage']}")


async def example_performance_analysis():
    """Example performance analysis"""
    print("\n\n=== Example 5: Performance Analysis ===\n")

    vault_id = uuid4()

    # Analyze agent performance over last 24 hours
    metrics = ExecutionAnalytics.analyze_agent_performance(
        agent_name="PsychologistAgent",
        vault_id=vault_id,
        hours=24
    )

    if 'error' not in metrics:
        print(f"Agent: {metrics['agent_name']}")
        print(f"Time Window: Last {metrics['time_window_hours']} hours")
        print(f"\nExecution Stats:")
        print(f"  Total: {metrics['total_executions']}")
        print(f"  Successful: {metrics['successful']}")
        print(f"  Failed: {metrics['failed']}")
        print(f"  Skipped: {metrics['skipped']}")
        print(f"  Success Rate: {metrics['success_rate']*100:.1f}%")

        print(f"\nPerformance:")
        print(f"  Avg Duration: {metrics['avg_duration_ms']:.0f}ms")

        print(f"\nLLM Stats:")
        llm = metrics['llm_stats']
        print(f"  Total Calls: {llm['total_calls']}")
        print(f"  Total Tokens: {llm['total_tokens']}")
        print(f"  Avg Tokens/Call: {llm['avg_tokens_per_call']:.0f}")
        print(f"  Avg Latency: {llm['avg_latency_ms']:.0f}ms")

        if metrics['common_errors']:
            print(f"\nCommon Errors:")
            for error in metrics['common_errors']:
                print(f"  - {error['error_type']}: {error['count']} occurrences")
    else:
        print(metrics['error'])


async def example_call_chain_tracing():
    """Example of tracing agent call chains"""
    print("\n\n=== Example 6: Call Chain Tracing ===\n")

    # Simulate Orchestrator -> Psychologist -> Profiler chain
    orchestrator_exec_id = uuid4()

    # Get the call chain
    chain = ExecutionAnalytics.get_execution_call_chain(orchestrator_exec_id)

    if chain:
        print("Agent Call Chain:")
        for link in chain:
            indent = "  " * link['depth']
            print(f"{indent}├─ {link['parent_agent']} → {link['child_agent']}")
            if link['call_reason']:
                print(f"{indent}   Reason: {link['call_reason']}")
            print(f"{indent}   Status: {link['status']}")
    else:
        print("No call chain found (root execution)")


async def main():
    """Run all examples"""
    await example_successful_execution()
    await example_failed_execution()
    await example_skipped_execution()
    await example_debugging_workflow()
    await example_performance_analysis()
    await example_call_chain_tracing()


if __name__ == "__main__":
    print("Agent Execution Tracking Examples")
    print("=" * 50)
    asyncio.run(main())
