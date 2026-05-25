"""Skill Loader — loads skill files and caches them for system prompt injection.

Skills are loaded once at startup and served as static prefixes in sub-agent
system prompts. This enables Gemini's implicit context caching (identical prefix
across requests gets cached automatically on Google's backend).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"
BASE_INSTRUCTIONS_FILE = SKILLS_DIR / "base_instructions.md"

VALID_FORMATS = {"pdf", "pptx", "docx"}

# In-memory cache: loaded once, reused across all requests
_cache: dict[str, str] = {}


def _load_file(path: Path) -> str:
    """Read a file, return empty string if not found."""
    if not path.exists():
        logger.warning(f"Skill file not found: {path}")
        return ""
    return path.read_text(encoding="utf-8")


def get_base_instructions() -> str:
    """Load shared document generation instructions (cached)."""
    if "base" not in _cache:
        _cache["base"] = _load_file(BASE_INSTRUCTIONS_FILE)
    return _cache["base"]


def get_skill(fmt: str) -> str:
    """Load format-specific skill content (cached).

    Args:
        fmt: One of 'pdf', 'pptx', 'docx'
    """
    fmt = fmt.lower().strip()
    if fmt not in VALID_FORMATS:
        logger.warning(f"Unknown skill format: {fmt}")
        return ""

    if fmt not in _cache:
        skill_file = SKILLS_DIR / f"{fmt}.md"
        _cache[fmt] = _load_file(skill_file)
    return _cache[fmt]


def get_doc_system_prompt(fmt: str) -> str:
    """Build the full document generation system prompt.

    Concatenates: base_instructions + format-specific skill.
    The result is a STATIC prefix (identical across requests for the same format)
    enabling Gemini's implicit context caching.
    """
    base = get_base_instructions()
    skill = get_skill(fmt)

    parts = []
    if base:
        parts.append(base)
    if skill:
        parts.append(f"\n\n---\n\n## {fmt.upper()} Skill Reference\n\n{skill}")

    return "\n".join(parts)


def detect_format(task: str) -> str | None:
    """Auto-detect the output format from the task text.

    Returns 'pdf', 'pptx', 'docx', or None if not a document task.
    """
    task_lower = task.lower()

    # Check for explicit format mentions
    if any(kw in task_lower for kw in ("pptx", "ppt", "powerpoint", "presentation", "slides")):
        return "pptx"
    if any(kw in task_lower for kw in ("docx", "word doc", "word document")):
        return "docx"
    if any(kw in task_lower for kw in ("pdf",)):
        return "pdf"

    # Heuristic: "create a document" without format → docx
    if any(kw in task_lower for kw in ("create a doc", "generate a doc", "write a doc")):
        return "docx"

    return None


def clear_cache() -> None:
    """Clear the in-memory skill cache (for testing or hot-reload)."""
    _cache.clear()
