"""Research Agent — handles web search and content extraction."""
from __future__ import annotations

from datetime import date

from ..tools import TOOL_REGISTRY
from .base import BaseAgent


def _build_research_prompt() -> str:
    """Build system prompt with current date injected."""
    today = date.today().strftime("%B %d, %Y")
    return f"""You are a research agent. Your job is to gather comprehensive, accurate information on a topic.

Today's date is {today}. Always use the current year ({date.today().year}) in your searches unless the user specifies otherwise.

<instructions>
## Approach
1. Use web_search to find relevant, current information.
2. If search results reference important pages, use http_get to fetch detailed content.
3. Synthesize findings into a clear, structured summary.
4. Include specific facts, dates, numbers, and names — not vague statements.

## Output Format
Structure your final answer as:
- **Summary**: 2-3 sentence overview
- **Key Findings**: Bullet points with specific facts
- **Sources**: List URLs you referenced

## Rules
- If given multiple search queries, execute them all for comprehensive coverage.
- For "deep" research: do multiple searches with different query angles, fetch key pages.
- For "shallow" research: 1-2 searches, return top results.
- Always provide factual, sourced information.
- If web_search fails, try rephrasing the query with different keywords. If still no results, state what you know from training data.
- NEVER fabricate URLs or sources. Only cite what you actually found.
- You are ONLY responsible for research. Do NOT comment on document creation, file generation, or anything outside information gathering.
- Focus solely on finding and reporting information. Another agent handles document creation.
</instructions>
"""


class ResearchAgent(BaseAgent):
    """Agent specialized in web research and content extraction."""

    agent_name = "research"

    def __init__(self, depth: str = "shallow") -> None:
        from ..config import get_config
        cfg = get_config()

        # Select tools available to this agent
        tools = []
        for name in ("web_search", "http_get"):
            if name in TOOL_REGISTRY:
                tools.append(TOOL_REGISTRY[name])

        max_steps = 5 if depth == "shallow" else 8

        # Use per-agent model override if configured (e.g. gemini-2.5-flash for speed)
        research_model = cfg.agents.research.model or None

        super().__init__(
            system_prompt=_build_research_prompt(),
            tools=tools,
            max_steps=max_steps,
            max_tokens=4096,
            model=research_model,
        )
