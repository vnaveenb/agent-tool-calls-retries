from __future__ import annotations

from pathlib import Path

from .base import ToolResult
from ..config import get_config


def read_file(path: str) -> ToolResult:
    """Read a file within the configured sandbox directory.

    Rejects any path that attempts to escape the sandbox via traversal.
    """
    cfg = get_config()
    sandbox = Path(cfg.tools.read_file.sandbox_dir).resolve()

    try:
        target = (sandbox / path).resolve()
    except (ValueError, OSError) as e:
        return ToolResult(success=False, output="", error=f"Invalid path: {e}")

    # Sandbox escape check
    if not str(target).startswith(str(sandbox)):
        return ToolResult(
            success=False,
            output="",
            error="Access denied: path is outside the allowed sandbox directory.",
        )

    if not target.exists():
        return ToolResult(success=False, output="", error=f"File not found: {path}")

    if not target.is_file():
        return ToolResult(success=False, output="", error=f"Not a file: {path}")

    try:
        content = target.read_text(encoding="utf-8")
        return ToolResult(success=True, output=content)
    except UnicodeDecodeError:
        return ToolResult(success=False, output="", error="File is not valid UTF-8 text.")
    except PermissionError:
        return ToolResult(success=False, output="", error="Permission denied.")
