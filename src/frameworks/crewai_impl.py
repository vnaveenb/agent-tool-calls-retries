"""CrewAI integration — replaces the imperative Orchestrator with a role-based crew.

Tools are thin wrappers around the existing ToolDef functions. Agents are defined
with CrewAI's role/goal/backstory semantics. Tasks are composed dynamically at
runtime based on the request, mirroring the supervisor's routing logic.

crew.kickoff() is synchronous, so it is offloaded to a thread pool via
run_in_executor to keep the FastAPI event loop unblocked.

Requires: crewai>=0.90.0
"""
from __future__ import annotations

import asyncio
import uuid

try:
    from crewai import Agent, Task, Crew, Process
    from crewai.tools import tool as crewai_tool
except ImportError as _err:
    raise ImportError(
        "CrewAI is not installed. Run: pip install 'crewai>=0.90.0'"
    ) from _err

from ..config import get_config
from ..agents.skill_loader import detect_format

# ── Tool adapters ─────────────────────────────────────────────
# Wrap existing ToolResult-returning functions as plain str-returning
# CrewAI tools via the @crewai_tool decorator.

def _r(result) -> str:
    """Convert ToolResult to str for CrewAI."""
    return result.output if result.success else f"ERROR: {result.error}"


@crewai_tool("Calculator")
def crewai_calculator(expression: str) -> str:
    """Evaluate a safe mathematical expression (arithmetic only)."""
    from ..tools.calculator import calculate
    return _r(calculate(expression))


@crewai_tool("WebSearch")
def crewai_web_search(query: str) -> str:
    """Search the web using the best available provider (Tavily → Serper → DuckDuckGo)."""
    from ..tools.web_search import web_search
    return _r(web_search(query))


@crewai_tool("HttpGet")
def crewai_http_get(url: str) -> str:
    """Fetch the text content of a URL (HTTPS only, 8000-char limit)."""
    from ..tools.http_get import http_get
    return _r(http_get(url))


@crewai_tool("ReadFile")
def crewai_read_file(path: str) -> str:
    """Read a file from the ./data/ sandbox directory."""
    from ..tools.read_file import read_file
    return _r(read_file(path))


@crewai_tool("PythonRepl")
def crewai_python_repl(code: str) -> str:
    """Execute Python code in a sandboxed subprocess (30s timeout, ./data/ only)."""
    from ..tools.python_repl import python_repl
    return _r(python_repl(code))


# ── Agent factories ───────────────────────────────────────────
# Constructed fresh per request so config hot-reload is respected.

def _make_researcher() -> Agent:
    cfg = get_config()
    model = cfg.agents.research.model or cfg.llm.model
    return Agent(
        role="Research Specialist",
        goal=(
            "Gather comprehensive, accurate, and up-to-date information from the web. "
            "Always cite sources and distinguish between confirmed facts and inferences."
        ),
        backstory=(
            "You are a seasoned research analyst who excels at finding reliable information "
            "quickly. You know how to craft targeted search queries and verify data quality."
        ),
        tools=[crewai_web_search, crewai_http_get],
        llm=model,
        verbose=True,
    )


def _make_doc_writer() -> Agent:
    cfg = get_config()
    return Agent(
        role="Document Writer",
        goal=(
            "Create professional, well-styled documents (PDF, PPTX, DOCX) using Python. "
            "Files must be saved to ./data/ and the path confirmed in the output."
        ),
        backstory=(
            "You are a document specialist who writes clean Python code using reportlab, "
            "python-pptx, and python-docx to produce polished business documents."
        ),
        tools=[crewai_python_repl, crewai_read_file],
        llm=cfg.llm.model,
        verbose=True,
    )


def _make_general_assistant() -> Agent:
    cfg = get_config()
    return Agent(
        role="General Assistant",
        goal="Answer questions accurately, perform calculations, and read files when needed.",
        backstory=(
            "You are a versatile assistant capable of Q&A, arithmetic, "
            "and light research. You keep answers concise and factual."
        ),
        tools=[crewai_calculator, crewai_web_search, crewai_read_file],
        llm=cfg.llm.model,
        verbose=True,
    )


# ── Dynamic task composition ──────────────────────────────────

def _build_crew(task: str) -> Crew:
    """Build a Crew whose tasks and agents are chosen based on the task content."""
    task_lower = task.lower()

    needs_research = any(kw in task_lower for kw in (
        "search", "find", "look up", "latest", "recent", "last week",
        "current", "today", "news", "ipl", "match", "score", "stock",
        "weather", "price",
    ))
    needs_doc = detect_format(task) is not None or any(kw in task_lower for kw in (
        "create", "generate", "make", "build", "ppt", "pdf", "docx",
        "presentation", "slides", "report", "document",
    ))

    researcher = _make_researcher()
    doc_writer = _make_doc_writer()
    general = _make_general_assistant()

    if needs_research and needs_doc:
        research_task = Task(
            description=f"Research this topic thoroughly and return detailed findings:\n\n{task}",
            expected_output="Comprehensive research findings with specific facts, dates, and source URLs",
            agent=researcher,
        )
        doc_task = Task(
            description=(
                f"Using the research findings provided, create the requested document.\n\n"
                f"Original request: {task}"
            ),
            expected_output="Confirmation of the generated file path (e.g., Saved to ./data/report.pdf)",
            agent=doc_writer,
            context=[research_task],
        )
        return Crew(
            agents=[researcher, doc_writer],
            tasks=[research_task, doc_task],
            process=Process.sequential,
            verbose=True,
        )

    if needs_research:
        research_task = Task(
            description=f"Research and answer the following:\n\n{task}",
            expected_output="Clear, factual answer with sources",
            agent=researcher,
        )
        return Crew(
            agents=[researcher],
            tasks=[research_task],
            process=Process.sequential,
            verbose=True,
        )

    if needs_doc:
        doc_task = Task(
            description=f"Create the requested document:\n\n{task}",
            expected_output="Confirmation of the generated file path",
            agent=doc_writer,
        )
        return Crew(
            agents=[doc_writer],
            tasks=[doc_task],
            process=Process.sequential,
            verbose=True,
        )

    general_task = Task(
        description=task,
        expected_output="Clear, concise answer",
        agent=general,
    )
    return Crew(
        agents=[general],
        tasks=[general_task],
        process=Process.sequential,
        verbose=True,
    )


# ── Public API ────────────────────────────────────────────────

async def run_crewai_task(task: str) -> dict:
    """Run a task through a dynamically composed CrewAI crew.

    crew.kickoff() is synchronous — offloaded to the default thread pool so
    the FastAPI event loop remains responsive during long-running crew execution.
    """
    crew = _build_crew(task)

    loop = asyncio.get_event_loop()
    crew_result = await loop.run_in_executor(None, crew.kickoff)

    answer = str(crew_result)

    return {
        "run_id": str(uuid.uuid4()),
        "answer": answer,
        "steps": [],
        "total_steps": 0,
        "total_tokens": {"input": 0, "output": 0},
        "model": get_config().llm.model,
        "framework": "crewai",
    }
