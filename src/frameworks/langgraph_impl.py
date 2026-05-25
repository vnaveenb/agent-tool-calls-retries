"""LangGraph integration — replaces the imperative Orchestrator with a declarative StateGraph.

The graph nodes call the same existing agents (ResearchAgent, DocGeneratorAgent,
GeneralAgent, SupervisorAgent) as-is. LangGraph provides only the routing layer,
making the agent flow inspectable and visualisable.

Visualise the graph:
    from src.frameworks.langgraph_impl import get_graph
    print(get_graph().get_graph().draw_mermaid())

Requires: langgraph>=0.2.0, langchain>=0.3.0
"""
from __future__ import annotations

import uuid
from typing import Optional

from ..config import get_config

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict

try:
    from langgraph.graph import StateGraph, END
except ImportError as _err:
    raise ImportError(
        "LangGraph is not installed. Run: pip install 'langgraph>=0.2.0' 'langchain>=0.3.0'"
    ) from _err


# ── State ─────────────────────────────────────────────────────

class AgentState(TypedDict):
    task: str
    intent: str              # populated by supervisor_node
    research_context: str    # populated by research_node
    format: Optional[str]    # populated by supervisor_node (pdf/pptx/docx or None)
    answer: str              # populated by the terminal node
    depth: str               # populated by supervisor_node (shallow/deep)


# ── Nodes ─────────────────────────────────────────────────────

async def supervisor_node(state: AgentState) -> dict:
    """Route the task using the existing SupervisorAgent."""
    from ..agents.supervisor import SupervisorAgent
    plan = await SupervisorAgent().route(state["task"])
    return {
        "intent": plan.intent,
        "format": plan.format,
        "depth": plan.depth,
    }


async def research_node(state: AgentState) -> dict:
    """Gather information using the existing ResearchAgent."""
    from ..agents.research import ResearchAgent
    result = await ResearchAgent(depth=state.get("depth", "shallow")).run(state["task"])
    return {"research_context": result.answer}


async def doc_node(state: AgentState) -> dict:
    """Generate a document using the existing DocGeneratorAgent."""
    from ..agents.doc_generator import DocGeneratorAgent
    result = await DocGeneratorAgent(fmt=state.get("format")).run(
        state["task"],
        context=state.get("research_context", ""),
    )
    return {"answer": result.answer}


async def general_node(state: AgentState) -> dict:
    """Handle Q&A and calculations using the existing GeneralAgent."""
    from ..agents.general import GeneralAgent
    result = await GeneralAgent().run(state["task"])
    return {"answer": result.answer}


# ── Edge routing functions ────────────────────────────────────

def _route_after_supervisor(state: AgentState) -> str:
    intent = state.get("intent", "general")
    if intent in ("research_only", "research_then_generate"):
        return "research"
    if intent == "generate_document":
        return "doc"
    return "general"


def _route_after_research(state: AgentState) -> str:
    if state.get("intent") == "research_then_generate":
        return "doc"
    return END  # research_only — terminal


# ── Graph construction ────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("research",   research_node)
    g.add_node("doc",        doc_node)
    g.add_node("general",    general_node)

    g.set_entry_point("supervisor")

    g.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {"research": "research", "doc": "doc", "general": "general"},
    )

    g.add_conditional_edges(
        "research",
        _route_after_research,
        {"doc": "doc", END: END},
    )

    g.add_edge("doc",     END)
    g.add_edge("general", END)

    return g.compile()


_graph = None


def get_graph():
    """Return the compiled graph (singleton — built once on first call)."""
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ── Public API ────────────────────────────────────────────────

async def run_langgraph_task(task: str) -> dict:
    """Run a task through the LangGraph graph and return a result dict.

    The response shape is a superset of the /run endpoint so it is
    compatible with the existing frontend.
    """
    graph = get_graph()

    initial_state: AgentState = {
        "task": task,
        "intent": "",
        "research_context": "",
        "format": None,
        "answer": "",
        "depth": "shallow",
    }

    final_state = await graph.ainvoke(initial_state)

    return {
        "run_id": str(uuid.uuid4()),
        "answer": final_state.get("answer", ""),
        # LangGraph's ainvoke returns final state only — sub-agent steps are not surfaced here.
        "steps": [],
        "total_steps": 0,
        "total_tokens": {"input": 0, "output": 0},
        "model": get_config().llm.model,
        "framework": "langgraph",
        "intent": final_state.get("intent", ""),
    }
