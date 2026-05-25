"""Demo: multi-step tool chaining via the agent."""
import asyncio
from src.agent import ReActAgent


async def main():
    agent = ReActAgent()
    result = await agent.run(
        "Search for the population of Tokyo, then calculate that number divided by 1000."
    )

    print(f"Answer: {result.answer}")
    print(f"Total steps: {result.total_steps}")
    print(f"Model: {result.model}")
    print(f"Trace ID: {result.run_id}")
    print()

    for step in result.steps:
        print(f"  Step {step.step} [{step.timestamp}]")
        print(f"    Thought: {step.thought}")
        print(f"    Tool:    {step.tool}({step.args})")
        print(f"    Result:  {step.result[:100]}...")
        print(f"    Latency: {step.latency_ms}ms")
        print()


if __name__ == "__main__":
    asyncio.run(main())
