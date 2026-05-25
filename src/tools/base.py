from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDef:
    """Definition of a tool the agent can call."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    fn: Callable[..., "ToolResult"]


@dataclass
class ToolResult:
    """Result returned by a tool execution."""
    success: bool
    output: str
    error: str | None = None


class ToolError(Exception):
    """Raised when a tool fails after all retry attempts."""

    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"Tool '{tool_name}' failed: {message}")


def tool_def_to_litellm_schema(tool: ToolDef) -> dict[str, Any]:
    """Convert a ToolDef to the OpenAI function-calling format used by LiteLLM."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }
