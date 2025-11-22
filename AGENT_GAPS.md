# Agent Gaps Review

## DramatistAgent
- Implements `run`, wrapping the tension/emotion scoring pipeline to provide a usable entrypoint.

## StylistAgent
- Implements `run` so prose critiques can be invoked via the shared agent interface.

## ChronologistAgent
- Implements `run` with timeline extraction instead of being an empty subclass.

## PsychologistAgent
- Import side-effect print removed to avoid stdout pollution during runtime and tests.
- The agent lacks a `run` implementation, so invoking it will hit `BaseAgent.run` and raise `NotImplementedError`.
- No default entry point means tension/pacing helpers cannot be orchestrated from the agent router.

## StylistAgent
- Similar to the Dramatist, there is no `run` method, so calls to the agent will fail with `NotImplementedError`.
- Only exposes `critique_prose`, which requires manual invocation and bypasses the standard interface.

## ChronologistAgent
- Currently defined as `pass` with no behaviors; any attempt to instantiate will initialize the base class and then lack usable methods.

## PsychologistAgent
- Emits a `print` statement on import ("--- LOADING NEW PSYCHOLOGIST V2 AGENT ---"), which side-effects stdout during runtime and tests.
- Otherwise follows the BaseAgent interface, but the import side effect may interfere with logging expectations.
