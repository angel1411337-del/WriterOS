#!/usr/bin/env python3
"""
Performance benchmarking for WriterOS agents and RAG pipeline.

Usage:
    python -m scripts.benchmark --agent profiler --iterations 100
"""
import asyncio
import time
import argparse
from statistics import mean, stdev

from writeros.agents.profiler import ProfilerAgent
from writeros.agents.psychologist import PsychologistAgent
from writeros.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def benchmark_agent(agent_class, sample_text: str, iterations: int):
    """Benchmark an agent's performance."""
    agent = agent_class()
    timings = []
    
    for i in range(iterations):
        start = time.time()
        await agent.run(sample_text, "", f"Test {i}")
        elapsed = time.time() - start
        timings.append(elapsed)
        
        if (i + 1) % 10 == 0:
            logger.info("benchmark_progress", iteration=i+1, total=iterations)
    
    return {
        "mean": mean(timings),
        "stdev": stdev(timings) if len(timings) > 1 else 0,
        "min": min(timings),
        "max": max(timings),
    }


async def main():
    parser = argparse.ArgumentParser(description="Benchmark WriterOS performance")
    parser.add_argument("--agent", choices=["profiler", "psychologist"], default="profiler")
    parser.add_argument("--iterations", type=int, default=10)
    
    args = parser.parse_args()
    
    # Load sample text
    sample_text = "Test manuscript content for benchmarking."
    
    agent_map = {
        "profiler": ProfilerAgent,
        "psychologist": PsychologistAgent,
    }
    
    results = await benchmark_agent(agent_map[args.agent], sample_text, args.iterations)
    
    logger.info("benchmark_complete", agent=args.agent, **results)
    print(f"\n{'='*50}")
    print(f"Benchmark Results: {args.agent}")
    print(f"{'='*50}")
    print(f"Mean:   {results['mean']:.3f}s")
    print(f"Stdev:  {results['stdev']:.3f}s")
    print(f"Min:    {results['min']:.3f}s")
    print(f"Max:    {results['max']:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
