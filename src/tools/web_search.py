from __future__ import annotations

import logging
import os

from .base import ToolResult

logger = logging.getLogger(__name__)


def _search_tavily(query: str) -> ToolResult | None:
    """Search using Tavily API (built for AI agents). Returns None if unavailable."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query, max_results=5, include_answer=True)

        formatted = []
        # Tavily provides a direct AI-generated answer
        if response.get("answer"):
            formatted.append(f"**Answer**: {response['answer']}\n")

        for i, r in enumerate(response.get("results", []), 1):
            title = r.get("title", "No title")
            content = r.get("content", "No snippet")
            url = r.get("url", "")
            formatted.append(f"{i}. {title}\n   {content}\n   {url}")

        if formatted:
            return ToolResult(success=True, output="\n\n".join(formatted))
        return ToolResult(success=True, output="No results found.")

    except ImportError:
        logger.debug("tavily package not installed, falling back to DDG")
        return None
    except Exception as e:
        logger.warning(f"Tavily search failed: {e}, falling back to DDG")
        return None


def _search_serper(query: str) -> ToolResult | None:
    """Search using Serper.dev (Google SERP). Returns None if unavailable."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return None

    try:
        import httpx
        response = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        formatted = []
        # Answer box
        if "answerBox" in data:
            ab = data["answerBox"]
            formatted.append(f"**Answer**: {ab.get('answer') or ab.get('snippet', '')}\n")

        for i, r in enumerate(data.get("organic", [])[:5], 1):
            title = r.get("title", "No title")
            snippet = r.get("snippet", "No snippet")
            link = r.get("link", "")
            formatted.append(f"{i}. {title}\n   {snippet}\n   {link}")

        if formatted:
            return ToolResult(success=True, output="\n\n".join(formatted))
        return ToolResult(success=True, output="No results found.")

    except Exception as e:
        logger.warning(f"Serper search failed: {e}, falling back to DDG")
        return None


def _search_ddg(query: str) -> ToolResult:
    """Fallback: Search using DuckDuckGo (no API key needed)."""
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=5)

        if not results:
            return ToolResult(success=True, output="No results found.")

        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            body = r.get("body", "No snippet")
            href = r.get("href", "")
            formatted.append(f"{i}. {title}\n   {body}\n   {href}")

        return ToolResult(success=True, output="\n\n".join(formatted))

    except Exception as e:
        return ToolResult(success=False, output="", error=f"Search failed: {e}")


def web_search(query: str) -> ToolResult:
    """Search the web using the best available provider.

    Priority: Tavily → Serper → DuckDuckGo (fallback)
    Set TAVILY_API_KEY or SERPER_API_KEY in .env for better results.
    """
    # Try Tavily first (best for AI agents)
    result = _search_tavily(query)
    if result is not None:
        return result

    # Try Serper (Google results)
    result = _search_serper(query)
    if result is not None:
        return result

    # Fallback to DuckDuckGo
    return _search_ddg(query)
