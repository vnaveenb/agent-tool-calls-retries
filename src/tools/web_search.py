from __future__ import annotations

from duckduckgo_search import DDGS

from .base import ToolResult


def web_search(query: str) -> ToolResult:
    """Search DuckDuckGo and return top-3 results."""
    try:
        results = DDGS().text(query, max_results=3)

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
