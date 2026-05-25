"""Tool: read_skill — Load a document-generation skill guide on demand."""
from __future__ import annotations

from pathlib import Path

from .base import ToolResult


SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"

VALID_SKILLS = {"pdf", "pptx", "docx"}


def read_skill(skill: str) -> ToolResult:
    """Read a skill guide file for document generation.

    Returns the markdown content of the skill guide for the requested format.
    Only pdf, pptx, and docx skills are available.
    """
    skill = skill.lower().strip()

    if skill not in VALID_SKILLS:
        return ToolResult(
            success=False,
            output="",
            error=f"Unknown skill '{skill}'. Available skills: {', '.join(sorted(VALID_SKILLS))}",
        )

    skill_file = SKILLS_DIR / f"{skill}.md"

    if not skill_file.exists():
        return ToolResult(
            success=False,
            output="",
            error=f"Skill file not found: {skill}.md",
        )

    try:
        content = skill_file.read_text(encoding="utf-8")
        return ToolResult(success=True, output=content)
    except Exception as e:
        return ToolResult(success=False, output="", error=f"Error reading skill: {e}")
