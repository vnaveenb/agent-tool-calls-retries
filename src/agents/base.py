"""BaseAgent — common ReAct loop extracted from the original ReActAgent."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import litellm
from dotenv import load_dotenv

from ..config import get_config
from ..retry import with_retry
from ..tools import get_tool, TOOL_REGISTRY
from ..tools.base import ToolDef, ToolResult, ToolError, tool_def_to_litellm_schema

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    input: int = 0
    output: int = 0


@dataclass
class AgentStep:
    step: int
    thought: str
    tool: str
    args: dict[str, Any]
    result: str
    latency_ms: int
    timestamp: str  # ISO 8601


@dataclass
class AgentResult:
    run_id: str
    answer: str
    steps: list[AgentStep]
    total_steps: int
    total_tokens: TokenUsage
    model: str
    agent_name: str = "base"


class BaseAgent:
    """ReAct agent with tool calling, retries, and execution tracing.

    Sub-agents extend this by providing their own system_prompt and tool subset.
    """

    agent_name: str = "base"

    def __init__(
        self,
        system_prompt: str,
        tools: list[ToolDef],
        max_steps: int | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        thinking_budget: int | None = None,
    ) -> None:
        self.cfg = get_config()
        self.system_prompt = system_prompt
        self.tools = tools
        self.max_steps = max_steps or self.cfg.agent.max_steps
        self.model = model or self.cfg.llm.model
        self.max_tokens = max_tokens or self.cfg.llm.max_tokens
        self.temperature = temperature if temperature is not None else self.cfg.llm.temperature
        self.thinking_budget = thinking_budget if thinking_budget is not None else self.cfg.llm.thinking_budget

    async def run(
        self,
        task: str,
        context: str = "",
        on_event: Callable[[dict], None] | None = None,
    ) -> AgentResult:
        """Execute a task using the ReAct loop.

        Args:
            task: The user's task/question.
            context: Optional context from a previous agent (e.g., research results).
            on_event: Optional sync callback called with progress events:
                - {"type": "step", "agent": str, "step": dict}
                - {"type": "retry", "agent": str, "attempt": int, "error": str}
        """
        run_id = str(uuid.uuid4())
        steps: list[AgentStep] = []
        total_tokens = TokenUsage()

        # Build tool schemas for LiteLLM
        tool_schemas = [tool_def_to_litellm_schema(t) for t in self.tools]

        # Build user message with optional context
        user_content = task
        if context:
            user_content = f"## Context (from prior research)\n\n{context}\n\n## Task\n\n{task}"

        # Conversation messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        answer = ""
        for step_num in range(1, self.max_steps + 1):
            # Call LLM (with retry on empty choices)
            response = None
            llm_kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "tools": tool_schemas if tool_schemas else None,
                "tool_choice": "auto",
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            if self.thinking_budget:
                llm_kwargs["thinking"] = {"type": "enabled", "budget_tokens": self.thinking_budget}

            for _attempt in range(5):
                try:
                    response = await litellm.acompletion(**llm_kwargs)
                except Exception as e:
                    logger.warning(f"[{self.agent_name}] LLM call error (attempt {_attempt+1}): {e}")
                    if on_event and _attempt > 0:
                        on_event({"type": "retry", "agent": self.agent_name, "attempt": _attempt + 1, "error": str(e)})
                    await asyncio.sleep(2 ** _attempt)
                    continue
                if response.choices:
                    break
                logger.warning(
                    f"[{self.agent_name}] Empty choices (attempt {_attempt+1}/5), "
                    f"prompt_tokens={response.usage.prompt_tokens}"
                )
                if on_event and _attempt > 0:
                    on_event({"type": "retry", "agent": self.agent_name, "attempt": _attempt + 1, "error": "empty choices"})
                await asyncio.sleep(2 ** _attempt)

            # Track token usage
            if response:
                usage = response.usage
                if usage:
                    total_tokens.input += usage.prompt_tokens or 0
                    total_tokens.output += usage.completion_tokens or 0

            if not response or not response.choices:
                answer = "LLM returned no response. The request may have been too complex or was filtered."
                break

            choice = response.choices[0]
            message = choice.message

            # If no tool calls → final answer
            if not message.tool_calls:
                answer = message.content or "No answer produced."
                break
            else:
                # Append the assistant message with tool_calls
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
                messages.append(assistant_msg)

                # Process each tool call
                for tool_call in message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args_raw = tool_call.function.arguments

                    try:
                        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except json.JSONDecodeError:
                        fn_args = {}

                    thought = message.content or f"Calling {fn_name}"
                    timestamp = datetime.now(timezone.utc).isoformat()
                    start = time.perf_counter()

                    # Execute tool with retry
                    tool_result = await self._execute_tool(fn_name, fn_args)

                    latency_ms = int((time.perf_counter() - start) * 1000)
                    result_text = tool_result.output if tool_result.success else f"ERROR: {tool_result.error}"

                    step = AgentStep(
                        step=step_num,
                        thought=thought,
                        tool=fn_name,
                        args=fn_args,
                        result=result_text,
                        latency_ms=latency_ms,
                        timestamp=timestamp,
                    )
                    steps.append(step)
                    if on_event:
                        on_event({"type": "step", "agent": self.agent_name, "step": asdict(step)})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    })
        else:
            answer = f"Max steps ({self.max_steps}) reached. Last observation: {steps[-1].result if steps else 'none'}"

        result = AgentResult(
            run_id=run_id,
            answer=answer,
            steps=steps,
            total_steps=len(steps),
            total_tokens=total_tokens,
            model=self.model,
            agent_name=self.agent_name,
        )
        return result

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with retry logic."""
        # Check if the tool is in this agent's allowed set
        tool_names = {t.name for t in self.tools}
        if name not in tool_names:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: '{name}'. Available: {list(tool_names)}",
            )

        tool = get_tool(name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{name}' not found in registry.",
            )

        @with_retry(max_attempts=4, base_delay=1.0, jitter=True, tool_name=name)
        def _call() -> ToolResult:
            return tool.fn(**args)

        try:
            return await _call()
        except ToolError as e:
            return ToolResult(success=False, output="", error=e.message)
