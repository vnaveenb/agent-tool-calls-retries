"""Document Generator Agent — creates styled PDF/PPTX/DOCX files with skill-injected prompts."""
from __future__ import annotations

from ..tools import TOOL_REGISTRY
from .base import BaseAgent
from .skill_loader import get_doc_system_prompt, detect_format

# Fallback prompt when no skill file is found
_FALLBACK_DOC_PROMPT = """You are a document generation agent. Create professional documents using Python.

Rules:
- Save all files to `./data/`
- Use python_repl to execute code
- Final answer MUST include: [FILE: ./data/filename.ext]
- Pre-installed: reportlab, python-pptx, python-docx, openpyxl, matplotlib, Pillow
- NEVER access filesystem outside ./data/
- NEVER make network connections or run shell commands
"""


class DocGeneratorAgent(BaseAgent):
    """Agent specialized in creating styled documents (PDF, PPTX, DOCX).

    System prompt is built from base_instructions + format-specific skill,
    enabling Gemini's implicit context caching for repeated requests.
    """

    agent_name = "doc_generator"

    def __init__(self, fmt: str | None = None) -> None:
        """Initialize with optional format hint.

        Args:
            fmt: Document format ('pdf', 'pptx', 'docx'). If None, uses fallback prompt.
        """
        # Build system prompt from skill files
        if fmt:
            system_prompt = get_doc_system_prompt(fmt)
            if not system_prompt.strip():
                system_prompt = _FALLBACK_DOC_PROMPT
        else:
            system_prompt = _FALLBACK_DOC_PROMPT

        # Select tools: python_repl + read_file
        tools = []
        for name in ("python_repl", "read_file"):
            if name in TOOL_REGISTRY:
                tools.append(TOOL_REGISTRY[name])

        super().__init__(
            system_prompt=system_prompt,
            tools=tools,
            max_steps=10,
            max_tokens=16384,  # Large budget for code generation
        )

    @classmethod
    def for_task(cls, task: str) -> "DocGeneratorAgent":
        """Factory: auto-detect format from task and build the agent."""
        fmt = detect_format(task)
        return cls(fmt=fmt)
