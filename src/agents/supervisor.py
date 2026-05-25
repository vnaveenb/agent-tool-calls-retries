"""Supervisor Agent — LLM-based router that classifies tasks and plans execution."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import litellm
from dotenv import load_dotenv

from ..config import get_config

load_dotenv()
logger = logging.getLogger(__name__)


def _build_routing_prompt() -> str:
    """Build routing prompt with current date."""
    from datetime import date
    today = date.today().strftime("%B %d, %Y")
    year = date.today().year

    return f"""You are a task router. Today's date is {today}. The current year is {year}.

Analyze the user's request and decide which specialized agent(s) should handle it.

Available agents:
1. **research** — Searches the web, fetches URLs, gathers information. Use when the task requires current/external data.
2. **doc_generator** — Creates documents (PDF, PPT/PPTX, DOCX, CSV, Excel). Use when the task asks to generate/create a file.
3. **general** — Handles simple Q&A, calculations, file reading. Use for quick answers that don't need web search or document creation.

Routing rules (in priority order):
- If the task mentions BOTH (searching/finding information) AND (creating/generating a file) → **research_then_generate** (ALWAYS chain when both are needed)
- If the task is about a topic that requires current/recent data AND asks for a document → **research_then_generate**
- If the user asks to create/generate a document about a topic that needs web data (sports, news, events, stocks, weather) → **research_then_generate**
- If the user asks ONLY a factual question about recent events (no document) → **research_only**
- If the user asks ONLY to create/generate a document about a well-known static topic → **generate_document**
- If the user asks a simple calculation or general knowledge question → **general**

Key signals for research_then_generate:
- Any mention of file format (PPT, PDF, DOCX, slides, presentation, report) PLUS a topic needing current data
- "make a ppt on...", "create a presentation about..." + any current/dynamic topic
- Sports results, match scores, recent news, stock prices, weather, current events + document creation

Output format — respond with ONLY a JSON object (no markdown, no explanation):
{{
  "intent": "research_only" | "generate_document" | "research_then_generate" | "general",
  "format": "pdf" | "pptx" | "docx" | null,
  "research_queries": ["query1", "query2"] | null,
  "depth": "shallow" | "deep",
  "reasoning": "one-line explanation of routing decision"
}}

Rules for the JSON:
- "format": set when document generation is needed, null otherwise
- "research_queries": suggested search queries for the research agent (1-3 queries).
  - ALWAYS include the current year ({year}) in queries about recent/current events. Never use outdated years.
  - For sports/news/results queries: generate MULTIPLE angles to distinguish results from schedules.
    Example for "IPL last week": ["IPL 2026 match results scores last week", "IPL 2026 points table standings May {year}", "IPL 2026 week 8 winners scorecard"]
  - Never generate only one query for sports, news, or events — always include a results/scores variant and a standings/summary variant.
- "depth": "shallow" for simple lookups (1 search), "deep" for comprehensive research (multiple searches + page fetches).
  - Always use "deep" for sports results, recent news, or any topic where the user says "last week", "recent", "latest", "results", or "scores".
"""


@dataclass
class RoutingPlan:
    """The supervisor's routing decision."""
    intent: str  # research_only, generate_document, research_then_generate, general
    format: str | None  # pdf, pptx, docx, or None
    research_queries: list[str] | None
    depth: str  # shallow or deep
    reasoning: str


class SupervisorAgent:
    """Lightweight agent that classifies tasks and produces a routing plan."""

    agent_name = "supervisor"

    def __init__(self) -> None:
        self.cfg = get_config()

    async def route(self, task: str) -> RoutingPlan:
        """Classify the task and return a routing plan."""
        messages = [
            {"role": "system", "content": _build_routing_prompt()},
            {"role": "user", "content": task},
        ]

        llm_kwargs: dict[str, Any] = {
            "model": self.cfg.llm.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 512,  # Routing is a small JSON output
        }
        # Gemini 2.5 Pro needs thinking budget or returns empty
        if self.cfg.llm.thinking_budget:
            llm_kwargs["thinking"] = {"type": "enabled", "budget_tokens": min(self.cfg.llm.thinking_budget, 2048)}

        response = None
        for _attempt in range(3):
            try:
                response = await litellm.acompletion(**llm_kwargs)
            except Exception as e:
                logger.warning(f"[supervisor] LLM call error (attempt {_attempt+1}): {e}")
                await asyncio.sleep(2 ** _attempt)
                continue
            if response and response.choices:
                break
            logger.warning(f"[supervisor] Empty choices (attempt {_attempt+1}/3)")
            await asyncio.sleep(2 ** _attempt)

        if not response or not response.choices:
            logger.error("[supervisor] LLM returned no response, using keyword fallback")
            return self._keyword_fallback(task)

        content = response.choices[0].message.content or ""
        logger.info(f"[supervisor] Raw LLM response: {content[:200]}")

        # Parse JSON from response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"[supervisor] Failed to parse routing JSON: {content[:200]}")
            return self._keyword_fallback(task)

        plan = RoutingPlan(
            intent=data.get("intent", "general"),
            format=data.get("format"),
            research_queries=data.get("research_queries"),
            depth=data.get("depth", "shallow"),
            reasoning=data.get("reasoning", ""),
        )
        logger.info(f"[supervisor] Routed: intent={plan.intent}, format={plan.format}")
        return plan

    def _keyword_fallback(self, task: str) -> RoutingPlan:
        """Rule-based fallback router when LLM fails."""
        from .skill_loader import detect_format
        from datetime import date

        task_lower = task.lower()
        fmt = detect_format(task)
        year = date.today().year

        needs_research = any(kw in task_lower for kw in (
            "search", "find", "look up", "latest", "recent", "last week",
            "current", "today", "news", "ipl", "match", "score", "stock",
            "weather", "price",
        ))
        needs_doc = fmt is not None or any(kw in task_lower for kw in (
            "create", "generate", "make", "build", "ppt", "pdf", "docx",
            "presentation", "slides", "report", "document",
        ))

        if needs_research and needs_doc:
            intent = "research_then_generate"
        elif needs_research:
            intent = "research_only"
        elif needs_doc:
            intent = "generate_document"
        else:
            intent = "general"

        # Generate research queries from the task
        research_queries = None
        if needs_research:
            is_sports_news = any(kw in task_lower for kw in (
                "ipl", "match", "score", "result", "winner", "cricket",
                "football", "soccer", "sports", "news", "stock", "weather",
            ))
            if is_sports_news:
                # Generate multiple angles: results + standings + summary
                research_queries = [
                    f"{task} results scores {year}",
                    f"{task} standings summary {year}",
                ]
            else:
                research_queries = [f"{task} {year}"]

        is_sports_news = any(kw in task_lower for kw in (
            "ipl", "match", "score", "result", "winner", "cricket",
            "football", "soccer", "sports", "news", "stock", "weather",
            "last week", "recent", "latest",
        ))
        depth = "deep" if (needs_research and needs_doc) or is_sports_news else "shallow"

        logger.info(f"[supervisor] Keyword fallback: intent={intent}, format={fmt}, depth={depth}")
        return RoutingPlan(
            intent=intent,
            format=fmt,
            research_queries=research_queries,
            depth=depth,
            reasoning="Keyword fallback — LLM routing failed",
        )
