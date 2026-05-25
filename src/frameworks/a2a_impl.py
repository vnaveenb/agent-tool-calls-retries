"""Google A2A (Agent-to-Agent) protocol — server-side implementation.

Makes this agent A2A-compatible so any A2A orchestrator can call it via
standard JSON-RPC 2.0 without custom integration code.

Spec reference: https://google.github.io/A2A/
Protocol: JSON-RPC 2.0 over HTTP POST /a2a
Discovery: GET /.well-known/agent.json → AgentCard
"""
from __future__ import annotations

import uuid

from ..orchestrator import Orchestrator

_MAX_TASK_LENGTH = 25_000


def _build_agent_card(base_url: str) -> dict:
    """Return the A2A AgentCard served at /.well-known/agent.json."""
    return {
        "name": "ReAct Multi-Agent System",
        "description": (
            "A production-grade ReAct agent with tool calling, exponential backoff retries, "
            "and a multi-agent orchestrator (supervisor → research / doc-generation / general). "
            "Handles web research, professional document generation (PDF/PPTX/DOCX), and Q&A."
        ),
        "url": base_url,
        "version": "1.0.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "research",
                "name": "Web Research",
                "description": (
                    "Search the web via Tavily/Serper/DuckDuckGo and synthesise findings "
                    "from multiple sources with citations."
                ),
                "inputModes": ["text"],
                "outputModes": ["text"],
                "examples": [
                    "Search for the latest AI market trends in 2026",
                    "Find current IPL 2026 standings and match results",
                ],
            },
            {
                "id": "document-generation",
                "name": "Document Generation",
                "description": (
                    "Generate styled PDF, PPTX, or DOCX files using Python libraries "
                    "(reportlab, python-pptx, python-docx). Can research first then generate."
                ),
                "inputModes": ["text"],
                "outputModes": ["text"],
                "examples": [
                    "Create a PDF report on climate change",
                    "Make a PPTX presentation on AI trends with current data",
                ],
            },
            {
                "id": "general-qa",
                "name": "General Q&A",
                "description": (
                    "Answer factual questions, perform mathematical calculations, "
                    "and read files from the data sandbox."
                ),
                "inputModes": ["text"],
                "outputModes": ["text"],
                "examples": [
                    "What is 15 * 7?",
                    "Summarise what you know about retrieval-augmented generation",
                ],
            },
        ],
    }


async def handle_a2a_request(body: dict, base_url: str) -> dict:
    """Handle an A2A JSON-RPC 2.0 task request.

    Expected envelope::

        {
          "jsonrpc": "2.0",
          "method": "tasks/send",
          "id": "<caller-chosen-id>",
          "params": {
            "id": "<task-uuid>",
            "message": {
              "role": "user",
              "parts": [{"text": "...user task..."}]
            }
          }
        }

    Returns an A2A result envelope on success, or a JSON-RPC error object on failure.
    """
    jsonrpc_id = body.get("id")
    method = body.get("method", "")

    if method != "tasks/send":
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: '{method}'. Supported: 'tasks/send'",
            },
        }

    params = body.get("params", {})
    task_id = params.get("id") or str(uuid.uuid4())
    message = params.get("message", {})
    parts = message.get("parts", [])

    task_text = " ".join(
        p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p
    ).strip()

    if not task_text:
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "error": {
                "code": -32600,
                "message": "Invalid request: no text found in message parts",
            },
        }

    if len(task_text) > _MAX_TASK_LENGTH:
        return {
            "jsonrpc": "2.0",
            "id": jsonrpc_id,
            "error": {
                "code": -32600,
                "message": f"Task too long ({len(task_text)} chars). Maximum is {_MAX_TASK_LENGTH}.",
            },
        }

    orchestrator = Orchestrator()
    result = await orchestrator.run(task_text)

    return {
        "jsonrpc": "2.0",
        "id": jsonrpc_id,
        "result": {
            "id": task_id,
            "status": {"state": "completed"},
            "artifacts": [
                {
                    "name": "answer",
                    "parts": [{"text": result.answer}],
                }
            ],
            "metadata": {
                "run_id": result.run_id,
                "agents_used": result.agents_used,
                "total_steps": result.total_steps,
                "model": result.model,
                "framework": "a2a",
            },
        },
    }
