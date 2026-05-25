"""Tests for the ReAct agent — uses mocked LiteLLM responses."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.agent import ReActAgent, AgentResult


def _make_llm_response(content: str = None, tool_calls: list = None):
    """Helper to build a mock LiteLLM response."""
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls

    if tool_calls:
        message.model_dump.return_value = {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        }
    else:
        message.model_dump.return_value = {
            "role": "assistant",
            "content": content,
        }

    choice = MagicMock()
    choice.message = message

    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50

    return response


def _make_tool_call(id: str, name: str, arguments: dict):
    tc = MagicMock()
    tc.id = id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    return tc


class TestAgent:
    @patch("src.agent.litellm.acompletion")
    def test_single_tool_call(self, mock_completion, tmp_path, monkeypatch):
        """Agent calls calculator then produces final answer."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(
            agent=AgentConfig(traces_dir=str(tmp_path / "traces"))
        )

        # First call: LLM decides to use calculator
        tool_call = _make_tool_call("call_1", "calculator", {"expression": "6 * 7"})
        resp1 = _make_llm_response(content="I need to calculate 6 * 7", tool_calls=[tool_call])

        # Second call: LLM provides final answer
        resp2 = _make_llm_response(content="The answer is 42.")

        mock_completion.side_effect = [resp1, resp2]

        agent = ReActAgent()
        result = asyncio.run(agent.run("What is 6 times 7?"))

        assert result.answer == "The answer is 42."
        assert result.total_steps == 1
        assert result.steps[0].tool == "calculator"
        assert result.steps[0].result == "42"
        assert (tmp_path / "traces" / f"{result.run_id}.json").exists()

        config_mod._config = None

    @patch("src.agent.litellm.acompletion")
    def test_tool_chain(self, mock_completion, tmp_path):
        """Agent chains two tool calls."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(
            agent=AgentConfig(traces_dir=str(tmp_path / "traces"))
        )

        # Step 1: calculator call
        tc1 = _make_tool_call("call_1", "calculator", {"expression": "100 * 2"})
        resp1 = _make_llm_response(content="First calculation", tool_calls=[tc1])

        # Step 2: another calculator call
        tc2 = _make_tool_call("call_2", "calculator", {"expression": "200 + 50"})
        resp2 = _make_llm_response(content="Second calculation", tool_calls=[tc2])

        # Step 3: final answer
        resp3 = _make_llm_response(content="The result is 250.")

        mock_completion.side_effect = [resp1, resp2, resp3]

        agent = ReActAgent()
        result = asyncio.run(agent.run("Calculate 100*2 then add 50"))

        assert result.answer == "The result is 250."
        assert result.total_steps == 2
        assert result.steps[0].result == "200"
        assert result.steps[1].result == "250"

        config_mod._config = None

    @patch("src.agent.litellm.acompletion")
    def test_max_steps_guard(self, mock_completion, tmp_path):
        """Agent stops after max_steps and reports."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(
            agent=AgentConfig(max_steps=2, traces_dir=str(tmp_path / "traces"))
        )

        # Both steps call a tool — never gives final answer
        tc = _make_tool_call("call_x", "calculator", {"expression": "1+1"})
        resp = _make_llm_response(content="Thinking...", tool_calls=[tc])

        mock_completion.side_effect = [resp, resp, resp]  # extra in case

        agent = ReActAgent()
        result = asyncio.run(agent.run("Keep calculating forever"))

        assert "Max steps" in result.answer or result.total_steps == 2

        config_mod._config = None

    @patch("src.agent.litellm.acompletion")
    def test_unknown_tool_error_observation(self, mock_completion, tmp_path):
        """Agent handles unknown tool gracefully."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(
            agent=AgentConfig(traces_dir=str(tmp_path / "traces"))
        )

        # LLM calls a non-existent tool
        tc = _make_tool_call("call_1", "nonexistent_tool", {"arg": "val"})
        resp1 = _make_llm_response(content="Let me use a tool", tool_calls=[tc])

        # Then gives final answer
        resp2 = _make_llm_response(content="I couldn't find that tool, but the answer is unknown.")

        mock_completion.side_effect = [resp1, resp2]

        agent = ReActAgent()
        result = asyncio.run(agent.run("Do something impossible"))

        assert result.total_steps == 1
        assert "ERROR" in result.steps[0].result
        assert "Unknown tool" in result.steps[0].result

        config_mod._config = None
