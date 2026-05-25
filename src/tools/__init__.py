"""Tool registry — central registration of all available tools."""
from __future__ import annotations

from .base import ToolDef, ToolResult, ToolError, tool_def_to_litellm_schema
from .calculator import calculate
from .web_search import web_search
from .http_get import http_get
from .read_file import read_file
from .python_repl import python_repl
from .read_skill import read_skill  # Available but not auto-registered (Gemini multi-turn issue)


TOOL_REGISTRY: dict[str, ToolDef] = {}


def _register(tool: ToolDef) -> None:
    TOOL_REGISTRY[tool.name] = tool


# ── Register all tools ────────────────────────────────────────

_register(ToolDef(
    name="calculator",
    description="Evaluate a mathematical expression. Supports +, -, *, /, //, %, ** and parentheses.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "The arithmetic expression to evaluate, e.g. '(2 + 3) * 4'",
            }
        },
        "required": ["expression"],
    },
    fn=calculate,
))

_register(ToolDef(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns top 3 results with title, snippet, and URL.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            }
        },
        "required": ["query"],
    },
    fn=web_search,
))

_register(ToolDef(
    name="http_get",
    description="Fetch the content of a URL. Returns the text content (truncated to 4000 chars). Only http/https allowed.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch (must start with http:// or https://).",
            }
        },
        "required": ["url"],
    },
    fn=http_get,
))

_register(ToolDef(
    name="read_file",
    description="Read a file from the data directory. Path is relative to the sandbox.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path within the data directory.",
            }
        },
        "required": ["path"],
    },
    fn=read_file,
))

_register(ToolDef(
    name="python_repl",
    description="Execute Python code and return the output. Use print() to see results. Has a timeout limit.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute.",
            }
        },
        "required": ["code"],
    },
    fn=python_repl,
))

# NOTE: read_skill is NOT registered as a tool because Gemini 2.5 Flash
# returns empty choices on the follow-up call after receiving large tool results.
# The compact styling guidelines in the system prompt are sufficient.
# The skill files (skills/*.md) remain as detailed reference documentation.
# To re-enable: uncomment the _register block below.
#
# _register(ToolDef(
#     name="read_skill",
#     description="Load optional advanced styling reference for document generation.",
#     parameters={
#         "type": "object",
#         "properties": {
#             "skill": {"type": "string", "enum": ["pdf", "pptx", "docx"]}
#         },
#         "required": ["skill"],
#     },
#     fn=read_skill,
# ))


def get_tool(name: str) -> ToolDef | None:
    """Get a tool by name, or None if not found."""
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[ToolDef]:
    """Return all registered tools."""
    return list(TOOL_REGISTRY.values())
