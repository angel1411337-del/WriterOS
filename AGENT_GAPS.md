# Agent Gaps Review

## DramatistAgent
- Implements `run`, wrapping the tension/emotion scoring pipeline to provide a usable entrypoint.

## StylistAgent
- Implements `run` so prose critiques can be invoked via the shared agent interface.

## ChronologistAgent
- Implements `run` with timeline extraction instead of being an empty subclass.

## PsychologistAgent
- Import side-effect print removed to avoid stdout pollution during runtime and tests.
