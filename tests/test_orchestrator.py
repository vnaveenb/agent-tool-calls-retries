"""Tests for the multi-agent orchestrator — supervisor routing + sub-agent execution."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.agents.supervisor import SupervisorAgent, RoutingPlan
from src.agents.skill_loader import detect_format, get_doc_system_prompt, clear_cache
from src.orchestrator import Orchestrator, OrchestratorResult


# ── Supervisor Routing Tests ──────────────────────────────────────


class TestSupervisorRouting:
    """Test that the supervisor produces correct routing plans."""

    def _mock_llm_response(self, content: str):
        """Build a mock LiteLLM response with given content."""
        message = MagicMock()
        message.content = content
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        return response

    @patch("src.agents.supervisor.litellm.acompletion")
    def test_routes_to_general(self, mock_completion, tmp_path):
        """Simple math question routes to general agent."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(agent=AgentConfig(traces_dir=str(tmp_path / "traces")))

        routing_json = json.dumps({
            "intent": "general",
            "format": None,
            "research_queries": None,
            "depth": "shallow",
            "reasoning": "Simple calculation",
        })
        mock_completion.return_value = self._mock_llm_response(routing_json)

        supervisor = SupervisorAgent()
        plan = asyncio.run(supervisor.route("What is 6 * 7?"))

        assert plan.intent == "general"
        assert plan.format is None
        config_mod._config = None

    @patch("src.agents.supervisor.litellm.acompletion")
    def test_routes_to_research(self, mock_completion, tmp_path):
        """Current events question routes to research."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(agent=AgentConfig(traces_dir=str(tmp_path / "traces")))

        routing_json = json.dumps({
            "intent": "research_only",
            "format": None,
            "research_queries": ["IPL 2026 latest results"],
            "depth": "shallow",
            "reasoning": "User wants current sports data",
        })
        mock_completion.return_value = self._mock_llm_response(routing_json)

        supervisor = SupervisorAgent()
        plan = asyncio.run(supervisor.route("What were the latest IPL match results?"))

        assert plan.intent == "research_only"
        assert plan.research_queries == ["IPL 2026 latest results"]
        config_mod._config = None

    @patch("src.agents.supervisor.litellm.acompletion")
    def test_routes_to_research_then_generate(self, mock_completion, tmp_path):
        """Research + document creation chains two agents."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(agent=AgentConfig(traces_dir=str(tmp_path / "traces")))

        routing_json = json.dumps({
            "intent": "research_then_generate",
            "format": "pptx",
            "research_queries": ["IPL 2026 week 3 matches results scores"],
            "depth": "deep",
            "reasoning": "User wants research on IPL then a PPT created",
        })
        mock_completion.return_value = self._mock_llm_response(routing_json)

        supervisor = SupervisorAgent()
        plan = asyncio.run(supervisor.route(
            "Search for last week's IPL matches and create a PPT about them"
        ))

        assert plan.intent == "research_then_generate"
        assert plan.format == "pptx"
        assert plan.depth == "deep"
        config_mod._config = None

    @patch("src.agents.supervisor.litellm.acompletion")
    def test_routes_to_doc_generator(self, mock_completion, tmp_path):
        """Direct document creation routes to doc_generator."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(agent=AgentConfig(traces_dir=str(tmp_path / "traces")))

        routing_json = json.dumps({
            "intent": "generate_document",
            "format": "pdf",
            "research_queries": None,
            "depth": "shallow",
            "reasoning": "User wants a PDF created from their own knowledge",
        })
        mock_completion.return_value = self._mock_llm_response(routing_json)

        supervisor = SupervisorAgent()
        plan = asyncio.run(supervisor.route("Create a PDF about Python best practices"))

        assert plan.intent == "generate_document"
        assert plan.format == "pdf"
        config_mod._config = None

    @patch("src.agents.supervisor.litellm.acompletion")
    def test_fallback_on_invalid_json(self, mock_completion, tmp_path):
        """Supervisor falls back to general if LLM returns invalid JSON."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(agent=AgentConfig(traces_dir=str(tmp_path / "traces")))

        mock_completion.return_value = self._mock_llm_response("This is not JSON at all")

        supervisor = SupervisorAgent()
        plan = asyncio.run(supervisor.route("something weird"))

        assert plan.intent == "general"
        assert "fallback" in plan.reasoning.lower()
        config_mod._config = None


# ── Skill Loader Tests ────────────────────────────────────────────


class TestSkillLoader:
    """Test format detection and skill loading."""

    def test_detect_pptx(self):
        assert detect_format("Create a PPT about AI") == "pptx"
        assert detect_format("make a powerpoint presentation") == "pptx"
        assert detect_format("generate slides on topic X") == "pptx"

    def test_detect_pdf(self):
        assert detect_format("Create a PDF report") == "pdf"

    def test_detect_docx(self):
        assert detect_format("Create a Word document") == "docx"
        assert detect_format("generate a docx file") == "docx"

    def test_detect_none(self):
        assert detect_format("What is 2+2?") is None
        assert detect_format("Search for latest news") is None

    def test_get_doc_system_prompt_loads_skills(self):
        """Skill loader returns non-empty content for valid formats."""
        clear_cache()
        prompt = get_doc_system_prompt("pptx")
        # Should contain base instructions + pptx skill
        assert "document generation" in prompt.lower() or "PPTX" in prompt
        clear_cache()


# ── Orchestrator Integration Tests ────────────────────────────────


class TestOrchestrator:
    """Test orchestrator routing and chaining (mocked LLM calls)."""

    def _mock_llm_response(self, content: str = None, tool_calls: list = None):
        """Build a mock LiteLLM response."""
        message = MagicMock()
        message.content = content
        message.tool_calls = tool_calls
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        response.usage = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        return response

    def _mock_tool_call(self, id: str, name: str, arguments: dict):
        tc = MagicMock()
        tc.id = id
        tc.function = MagicMock()
        tc.function.name = name
        tc.function.arguments = json.dumps(arguments)
        return tc

    @patch("litellm.acompletion")
    def test_general_route_end_to_end(self, mock_llm, tmp_path):
        """Full flow: supervisor → general agent → answer."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(agent=AgentConfig(traces_dir=str(tmp_path / "traces")))

        # Call 1: Supervisor routing
        routing_json = json.dumps({
            "intent": "general",
            "format": None,
            "research_queries": None,
            "depth": "shallow",
            "reasoning": "Simple math",
        })
        supervisor_resp = self._mock_llm_response(content=routing_json)

        # Call 2: General agent calls calculator
        tc = self._mock_tool_call("call_1", "calculator", {"expression": "6 * 7"})
        agent_resp1 = self._mock_llm_response(content="Calculating", tool_calls=[tc])

        # Call 3: General agent final answer
        agent_resp2 = self._mock_llm_response(content="The answer is 42.")

        mock_llm.side_effect = [supervisor_resp, agent_resp1, agent_resp2]

        orchestrator = Orchestrator()
        result = asyncio.run(orchestrator.run("What is 6 * 7?"))

        assert result.answer == "The answer is 42."
        assert "general" in result.agents_used
        assert result.supervisor_plan["intent"] == "general"
        assert (tmp_path / "traces" / f"{result.run_id}.json").exists()

        config_mod._config = None

    @patch("litellm.acompletion")
    def test_research_then_generate_chain(self, mock_llm, tmp_path):
        """Full flow: supervisor → research → doc_generator."""
        import src.config as config_mod
        from src.config import AppConfig, AgentConfig

        config_mod._config = AppConfig(agent=AgentConfig(traces_dir=str(tmp_path / "traces")))

        # Call 1: Supervisor routing
        routing_json = json.dumps({
            "intent": "research_then_generate",
            "format": "pptx",
            "research_queries": ["IPL 2026 matches this week"],
            "depth": "deep",
            "reasoning": "Research then create PPT",
        })
        supervisor_resp = self._mock_llm_response(content=routing_json)

        # Call 2: Research agent does web_search
        tc_search = self._mock_tool_call("call_1", "web_search", {"query": "IPL 2026 matches"})
        research_resp1 = self._mock_llm_response(content="Searching", tool_calls=[tc_search])

        # Call 3: Research agent final answer
        research_resp2 = self._mock_llm_response(
            content="## Key Findings\n- MI beat CSK by 5 wickets\n- RCB won against DC"
        )

        # Call 4: Doc generator calls python_repl
        tc_repl = self._mock_tool_call("call_2", "python_repl", {"code": "print('created ppt')"})
        doc_resp1 = self._mock_llm_response(content="Generating PPT", tool_calls=[tc_repl])

        # Call 5: Doc generator final answer
        doc_resp2 = self._mock_llm_response(content="[FILE: ./data/ipl_matches.pptx]")

        mock_llm.side_effect = [supervisor_resp, research_resp1, research_resp2, doc_resp1, doc_resp2]

        orchestrator = Orchestrator()
        result = asyncio.run(orchestrator.run(
            "Search for last week IPL matches and create a PPT about them"
        ))

        assert "[FILE:" in result.answer
        assert "research" in result.agents_used
        assert "doc_generator" in result.agents_used
        assert result.supervisor_plan["intent"] == "research_then_generate"
        assert len(result.agents_used) == 2

        config_mod._config = None
