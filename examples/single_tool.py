"""Quick demo: single tool call via the agent."""
import asyncio
from src.agent import ReActAgent


async def main():
    agent = ReActAgent()
    result = await agent.run("What is 247 * 13?")

    print(f"Answer: {result.answer}")
    print(f"Steps: {result.total_steps}")
    print(f"Model: {result.model}")
    print(f"Tokens: input={result.total_tokens.input}, output={result.total_tokens.output}")
    print(f"Trace ID: {result.run_id}")

    for step in result.steps:
        print(f"  Step {step.step}: {step.tool}({step.args}) → {step.result} [{step.latency_ms}ms]")


if __name__ == "__main__":
    asyncio.run(main())
