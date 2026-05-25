"""Orchestrator — routes tasks through supervisor and chains sub-agents."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from typing import Callable

from .config import get_config
from .agents.base import AgentResult, AgentStep, TokenUsage
from .agents.supervisor import SupervisorAgent, RoutingPlan
from .agents.research import ResearchAgent
from .agents.doc_generator import DocGeneratorAgent
from .agents.general import GeneralAgent
from .agents.skill_loader import detect_format

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    """Unified result from the orchestrator, combining supervisor + sub-agent outputs."""
    run_id: str
    answer: str
    steps: list[AgentStep]
    total_steps: int
    total_tokens: TokenUsage
    model: str
    # Multi-agent metadata
    supervisor_plan: dict[str, Any] = field(default_factory=dict)
    agents_used: list[str] = field(default_factory=list)
    sub_results: list[dict[str, Any]] = field(default_factory=list)


class Orchestrator:
    """Main entry point: routes tasks to specialized agents via a supervisor.

    Flow:
      1. Supervisor classifies the task → RoutingPlan
      2. Execute sub-agent(s) per the plan (possibly chained)
      3. Collect unified trace
    """

    def __init__(self) -> None:
        self.cfg = get_config()
        self.supervisor = SupervisorAgent()

    async def run(
        self,
        task: str,
        on_event: Callable[[dict], None] | None = None,
    ) -> OrchestratorResult:
        """Execute a task through the multi-agent pipeline.

        Args:
            task: The user's task/question.
            on_event: Optional sync callback for real-time progress events.
                Event types: ``phase``, ``step``, ``retry``, ``done``.
        """
        run_id = str(uuid.uuid4())
        all_steps: list[AgentStep] = []
        total_tokens = TokenUsage()
        agents_used: list[str] = []
        sub_results: list[dict[str, Any]] = []

        def _emit(event: dict) -> None:
            if on_event:
                on_event(event)

        # Step 1: Supervisor routing
        _emit({"type": "phase", "phase": "routing", "label": "Routing task…"})
        logger.info(f"[orchestrator] Routing task: {task[:100]}...")
        plan = await self.supervisor.route(task)
        logger.info(f"[orchestrator] Plan: intent={plan.intent}, format={plan.format}, depth={plan.depth}")

        # Step 1.5: Hard fallback — override supervisor if it clearly misrouted
        plan = self._validate_routing(task, plan)
        logger.info(f"[orchestrator] Final plan: intent={plan.intent}, format={plan.format}")

        # Step 2: Execute based on intent
        if plan.intent == "general":
            _emit({"type": "phase", "phase": "general", "label": "Running agent…"})
            result = await self._run_general(task, on_event=on_event)
            all_steps.extend(result.steps)
            total_tokens.input += result.total_tokens.input
            total_tokens.output += result.total_tokens.output
            agents_used.append("general")
            sub_results.append(asdict(result))
            answer = result.answer

        elif plan.intent == "research_only":
            _emit({"type": "phase", "phase": "research", "label": "Researching the web…"})
            result = await self._run_research(task, plan, on_event=on_event)
            all_steps.extend(result.steps)
            total_tokens.input += result.total_tokens.input
            total_tokens.output += result.total_tokens.output
            agents_used.append("research")
            sub_results.append(asdict(result))
            answer = result.answer

        elif plan.intent == "generate_document":
            _emit({"type": "phase", "phase": "generating", "label": "Generating document…"})
            result = await self._run_doc_generator(task, plan, context="", on_event=on_event)
            all_steps.extend(result.steps)
            total_tokens.input += result.total_tokens.input
            total_tokens.output += result.total_tokens.output
            agents_used.append("doc_generator")
            sub_results.append(asdict(result))
            answer = result.answer

        elif plan.intent == "research_then_generate":
            # Chain: research → doc generation
            _emit({"type": "phase", "phase": "research", "label": "Researching the web…"})
            research_result = await self._run_research(task, plan, on_event=on_event)
            all_steps.extend(research_result.steps)
            total_tokens.input += research_result.total_tokens.input
            total_tokens.output += research_result.total_tokens.output
            agents_used.append("research")
            sub_results.append(asdict(research_result))

            # Pass research output as context to doc generator
            _emit({"type": "phase", "phase": "generating", "label": "Generating document…"})
            doc_result = await self._run_doc_generator(
                task, plan, context=research_result.answer, on_event=on_event
            )
            all_steps.extend(doc_result.steps)
            total_tokens.input += doc_result.total_tokens.input
            total_tokens.output += doc_result.total_tokens.output
            agents_used.append("doc_generator")
            sub_results.append(asdict(doc_result))
            answer = doc_result.answer

        else:
            # Unknown intent — fallback to general
            logger.warning(f"[orchestrator] Unknown intent '{plan.intent}', falling back to general")
            _emit({"type": "phase", "phase": "general", "label": "Running agent…"})
            result = await self._run_general(task, on_event=on_event)
            all_steps.extend(result.steps)
            total_tokens.input += result.total_tokens.input
            total_tokens.output += result.total_tokens.output
            agents_used.append("general")
            sub_results.append(asdict(result))
            answer = result.answer

        # Build final result
        orchestrator_result = OrchestratorResult(
            run_id=run_id,
            answer=answer,
            steps=all_steps,
            total_steps=len(all_steps),
            total_tokens=total_tokens,
            model=self.cfg.llm.model,
            supervisor_plan=asdict(plan),
            agents_used=agents_used,
            sub_results=sub_results,
        )

        # Save trace
        self._save_trace(orchestrator_result)

        return orchestrator_result

    async def _run_research(
        self,
        task: str,
        plan: RoutingPlan,
        on_event: Callable[[dict], None] | None = None,
    ) -> AgentResult:
        """Run the research agent with a research-focused task."""
        agent = ResearchAgent(depth=plan.depth)

        # Give the research agent ONLY the research portion, not the full task
        # (avoids it commenting on doc creation it can't do)
        if plan.research_queries:
            queries_hint = "\n".join(f"- {q}" for q in plan.research_queries)
            research_task = (
                f"Research the following topic and provide comprehensive findings:\n\n"
                f"Search queries to execute:\n{queries_hint}\n\n"
                f"Original request context: {task}"
            )
        else:
            research_task = f"Research the following and provide comprehensive findings:\n\n{task}"

        return await agent.run(research_task, on_event=on_event)

    async def _run_doc_generator(
        self,
        task: str,
        plan: RoutingPlan,
        context: str,
        on_event: Callable[[dict], None] | None = None,
    ) -> AgentResult:
        """Run the document generator agent."""
        fmt = plan.format or detect_format(task)
        agent = DocGeneratorAgent(fmt=fmt)
        return await agent.run(task, context=context, on_event=on_event)

    async def _run_general(
        self,
        task: str,
        on_event: Callable[[dict], None] | None = None,
    ) -> AgentResult:
        """Run the general agent."""
        agent = GeneralAgent()
        return await agent.run(task, on_event=on_event)

    def _validate_routing(self, task: str, plan: RoutingPlan) -> RoutingPlan:
        """Hard override: fix obvious misroutes using keyword detection."""
        from datetime import date
        task_lower = task.lower()
        year = date.today().year

        fmt = detect_format(task)
        needs_doc = fmt is not None or any(kw in task_lower for kw in (
            "ppt", "pdf", "docx", "presentation", "slides", "report",
            "create", "generate", "make",
        ))
        needs_research = any(kw in task_lower for kw in (
            "search", "find", "look up", "latest", "recent", "last week",
            "ipl", "match", "score", "news", "stock", "weather",
        ))

        # Fix: supervisor said research_only but task clearly needs a doc
        if plan.intent == "research_only" and needs_doc:
            logger.info("[orchestrator] Override: research_only → research_then_generate")
            plan.intent = "research_then_generate"
            plan.format = fmt or plan.format

        # Fix: supervisor said general but task clearly needs research + doc
        if plan.intent == "general" and needs_research and needs_doc:
            logger.info("[orchestrator] Override: general → research_then_generate")
            plan.intent = "research_then_generate"
            plan.format = fmt or plan.format
            if not plan.research_queries:
                plan.research_queries = [f"{task} {year}"]

        # Fix: supervisor said general but task clearly needs research
        if plan.intent == "general" and needs_research and not needs_doc:
            logger.info("[orchestrator] Override: general → research_only")
            plan.intent = "research_only"
            if not plan.research_queries:
                plan.research_queries = [f"{task} {year}"]

        return plan

    def _save_trace(self, result: OrchestratorResult) -> None:
        """Persist execution trace as JSON."""
        traces_dir = Path(self.cfg.agent.traces_dir)
        traces_dir.mkdir(parents=True, exist_ok=True)

        trace_path = traces_dir / f"{result.run_id}.json"
        trace_data = asdict(result)

        with open(trace_path, "w") as f:
            json.dump(trace_data, f, indent=2, default=str)
