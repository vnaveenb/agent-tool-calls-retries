# Agent with Tool Calls + Retries

> A production-grade ReAct agent with structured tool calling, exponential backoff retries, and full execution tracing — hot-swappable LLMs via LiteLLM.

![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-009688?logo=fastapi&logoColor=white)
![LiteLLM](https://img.shields.io/badge/LLM-LiteLLM_1.83-purple)
![Tests](https://img.shields.io/badge/Tests-31%20passed-brightgreen)

---

## What This Does

A ReAct (Reasoning + Acting) agent loop that:

1. Receives a user task via API
2. Reasons about which tool to call (via LLM with native function calling)
3. Executes the tool with exponential backoff retries
4. Observes the result (success or error fed back as context)
5. Repeats until the task is complete or max steps reached
6. Saves a full execution trace as JSON

Every tool call gets retry logic with exponential backoff. Every step is traced with timestamps and latency. The LLM is hot-swappable via `config.yaml` — same pattern as Project 1.

**Why this matters for interviews:** Most agents people demo are single-step. This one handles failures, chains tools across multiple steps, and produces a full execution trace — which is what production agents actually need.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure your LLM API key
cp .env.example .env
# Edit .env with your GEMINI_API_KEY (or OPENAI_API_KEY, etc.)

# 3. Start the server
uvicorn src.api:app --reload --port 8000

# 4. Test it
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d '{"task": "What is (15 + 27) * 3?"}'
```

Or open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## High-Level Design (HLD)

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Layer                             │
│   POST /run  │  GET /trace/{id}  │  GET /tools  │  GET /health  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ReAct Agent Loop                            │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │  LiteLLM    │───▶│  Tool Router │───▶│  Retry Decorator  │  │
│  │ acompletion │    │  (registry)  │    │  (exp. backoff)   │  │
│  └─────────────┘    └──────────────┘    └───────────────────┘  │
│         │                                        │              │
│         │         ┌──────────────────────────────┘              │
│         ▼         ▼                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Tool Executor                         │   │
│  │  calculator │ web_search │ http_get │ read_file │ repl   │   │
│  └─────────────────────────────────────────────────────────┘   │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────┐                                           │
│  │  Trace Logger    │──▶  traces/{run_id}.json                  │
│  └─────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Role |
|-----------|------|------|
| Config Loader | `src/config.py` | Pydantic models, `get_config()`/`reload_config()` singleton |
| Tool Definitions | `src/tools/base.py` | `ToolDef`, `ToolResult`, `ToolError` dataclasses + LiteLLM schema converter |
| Retry Decorator | `src/retry.py` | `@with_retry()` async decorator with exponential backoff + jitter |
| Tool Registry | `src/tools/__init__.py` | Central `TOOL_REGISTRY` dict, `get_tool()`, `list_tools()` |
| Agent Core | `src/agent.py` | `ReActAgent.run()` — async loop, message building, trace saving |
| API Layer | `src/api.py` | FastAPI endpoints, CORS, request/response handling |

---

## Architecture

### ReAct Loop Flow

```
User Task
    │
    ▼
┌──────────────────────────────────────────────┐
│  Agent Loop (max_steps = 10)                 │
│                                              │
│  Step N:                                     │
│    ├── LLM: decides tool_name + args         │
│    │        (via native function calling)     │
│    ├── Executor: run tool with retry(4x)     │
│    ├── Observation: tool result or error     │
│    └── If no tool_call → Final Answer, stop  │
└──────────────────────────────────────────────┘
    │
    ▼
AgentResult {
  run_id, answer, steps[],
  total_steps, total_tokens, model
}
```

### Retry Logic

```
Tool call attempt
    │
    ├── Success → return ToolResult(success=True)
    │
    └── Exception raised
          ├── Attempt 1: wait 1.0s + jitter → retry
          ├── Attempt 2: wait 2.0s + jitter → retry
          ├── Attempt 3: wait 4.0s + jitter → retry
          └── Attempt 4: raise ToolError
                → agent observes "ERROR: ..." and adapts
```

The backoff formula: `delay = base_delay × 2^attempt + random(0, 0.5)`

The agent sees errors as observations and can choose a different tool or approach — it doesn't crash.

### Data Flow Example (Verified)

```
POST /run { "task": "What is (15 + 27) * 3?" }

Step 1: LLM → tool_call: calculator(expression="(15 + 27) * 3")
        Executor → ToolResult(success=True, output="126")
        Observation fed back to LLM

Step 2: LLM → no tool_call, content="126"
        → Final Answer

Response: {
  "run_id": "39c48570-...",
  "answer": "126",
  "steps": [{ "tool": "calculator", "result": "126", "latency_ms": 0 }],
  "total_steps": 1,
  "total_tokens": { "input": 851, "output": 68 },
  "model": "gemini/gemini-2.5-flash"
}
```

### Multi-Step Tool Chain (Verified)

```
POST /run { "task": "Use Python to calculate the first 10 fibonacci numbers,
                     then use the calculator to multiply the 10th number by 3" }

Step 1: LLM → python_repl(code="...fibonacci...")
        Observation: "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]\n34"

Step 2: LLM → calculator(expression="34 * 3")
        Observation: "102"

Step 3: LLM → Final Answer:
        "The first 10 Fibonacci numbers are [0,1,1,2,3,5,8,13,21,34].
         The 10th is 34. 34 × 3 = 102."
```

---

## Tools

| Tool | Implementation | Security |
|------|---------------|----------|
| `calculator` | AST whitelist visitor — only allows numbers and arithmetic ops | No `eval()` on raw input; rejects function calls, variables, strings |
| `web_search` | `duckduckgo_search.DDGS().text()` — top 3 results | Retry on rate limits |
| `http_get` | `httpx.get()` with timeout + truncation to 4000 chars | SSRF prevention: only `http://` and `https://` schemes allowed |
| `read_file` | Reads files relative to configurable sandbox directory | `Path.resolve()` sandbox escape check; rejects `../` traversal |
| `python_repl` | `subprocess.run()` with configurable timeout | Process killed on timeout; demo-grade (no network isolation) |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run` | Submit a task → returns answer + full execution trace |
| `GET` | `/trace/{run_id}` | Retrieve persisted JSON trace by run ID |
| `GET` | `/tools` | List all tools with names, descriptions, JSON schemas |
| `GET` | `/health` | Status, active model, max_steps, tool count |
| `POST` | `/reload-config` | Hot-swap LLM model without server restart |

### Example Response

```json
{
  "run_id": "0f42b955-7695-487c-9d30-061fe1bfb6e4",
  "answer": "The first 10 Fibonacci numbers are [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]. The 10th is 34. 34 multiplied by 3 is 102.",
  "steps": [
    {
      "step": 1,
      "thought": "Calling python_repl",
      "tool": "python_repl",
      "args": { "code": "..." },
      "result": "[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]\n34",
      "latency_ms": 37,
      "timestamp": "2026-05-24T08:34:57.651960+00:00"
    },
    {
      "step": 2,
      "thought": "Calling calculator",
      "tool": "calculator",
      "args": { "expression": "34 * 3" },
      "result": "102",
      "latency_ms": 0,
      "timestamp": "2026-05-24T08:34:58.753743+00:00"
    }
  ],
  "total_steps": 2,
  "total_tokens": { "input": 1649, "output": 408 },
  "model": "gemini/gemini-2.5-flash"
}
```

---

## Framework Integrations

The same agents, tools, and retry logic are exposed through three additional orchestration layers — running in parallel alongside the custom implementation. This demonstrates familiarity with industry frameworks while keeping the comparison clean: identical inputs, identical tools, different routing philosophy.

### Architecture

```
User Request
     │
     ├─ POST /run ──────────────────────── Custom Orchestrator (imperative Python)
     │                                               │
     ├─ POST /langgraph/run ── LangGraph ────────────┤
     │                         StateGraph            │  ResearchAgent
     ├─ POST /crewai/run ───── CrewAI Crew ──────────┤  DocGeneratorAgent
     │                                               │  GeneralAgent
     └─ POST /a2a ─────────── JSON-RPC 2.0 ─────────┘
              │
              └─ GET /.well-known/agent.json → AgentCard (A2A discovery)
```

### Comparison

| | **Custom** | **LangGraph** | **CrewAI** | **Google A2A** |
|---|---|---|---|---|
| Orchestration | Imperative Python (`if/elif`) | Declarative `StateGraph` | Role-based `Crew` | JSON-RPC 2.0 protocol |
| Routing | Supervisor LLM + keyword override | Conditional graph edges | Dynamic task composition | Delegates to Custom Orchestrator |
| New agents / tools? | No | No — wraps existing | No — wraps existing | No — wraps existing |
| Endpoint | `POST /run` | `POST /langgraph/run` | `POST /crewai/run` | `POST /a2a` |
| Discovery | — | — | — | `GET /.well-known/agent.json` |
| Key portfolio value | Baseline | Graph inspectable via `draw_mermaid()` | Role/goal/backstory semantics | Cross-agent interoperability |

### LangGraph (`POST /langgraph/run`)

Replaces the orchestrator's `if/elif` intent chain with a `StateGraph`. Each existing agent (SupervisorAgent, ResearchAgent, DocGeneratorAgent, GeneralAgent) becomes a graph node. Conditional edges handle routing: supervisor → research / doc / general, and research → doc (for `research_then_generate`) or END (for `research_only`).

The key portfolio value: the graph is fully inspectable and visualisable.
```python
from src.frameworks.langgraph_impl import get_graph
print(get_graph().get_graph().draw_mermaid())
```

### CrewAI (`POST /crewai/run`)

Replaces Python class instantiation with role-based agent definitions (role, goal, backstory). Tools are thin adapters converting `ToolResult → str` via the `@tool` decorator. Tasks are composed dynamically at runtime based on the request content, using the same keyword detection logic as the supervisor.

`crew.kickoff()` is synchronous and is offloaded to a thread pool (`run_in_executor`) so the FastAPI event loop stays unblocked during long crew runs.

### Google A2A (`POST /a2a`)

Makes this agent compliant with the [Google A2A protocol](https://google.github.io/A2A/) — an open JSON-RPC 2.0 standard for agent-to-agent communication. Any A2A-compatible orchestration system can now call this agent without custom integration code.

```bash
# Discover the agent
curl http://localhost:8000/.well-known/agent.json

# Send an A2A task
curl -X POST http://localhost:8000/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "id": "req-1",
    "params": {
      "id": "task-abc",
      "message": {
        "role": "user",
        "parts": [{"text": "What is 42 + 8?"}]
      }
    }
  }'
```

The A2A implementation is protocol-only (no `google-adk` dependency) — just plain JSON-RPC 2.0 over FastAPI, making it lightweight and easy to audit.

---

## Project Structure

```
04-agent-tool-calls-retries/
├── config.yaml              # LLM + agent + tool settings (hot-swappable)
├── .env.example             # API key template
├── .gitignore
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py            # Pydantic config loader (get_config / reload_config)
│   ├── retry.py             # @with_retry async decorator (exp backoff + jitter)
│   ├── agent.py             # ReActAgent — async loop, LiteLLM acompletion, tracing
│   ├── api.py               # FastAPI endpoints
│   └── tools/
│       ├── __init__.py      # TOOL_REGISTRY, get_tool(), list_tools()
│       ├── base.py          # ToolDef, ToolResult, ToolError, schema converter
│       ├── calculator.py    # AST-whitelisted arithmetic eval
│       ├── web_search.py    # DuckDuckGo top-3 results
│       ├── http_get.py      # URL fetcher (SSRF-safe, truncated)
│       ├── read_file.py     # Sandboxed file reader
│       └── python_repl.py   # Subprocess Python execution with timeout
├── traces/                  # Persisted JSON execution traces
├── data/                    # Sandbox directory for read_file tool
├── tests/
│   ├── test_tools.py        # 12 tool tests (injection, sandbox escape, etc.)
│   ├── test_retry.py        # 5 retry tests (backoff timing, exhaustion)
│   └── test_agent.py        # 4 agent tests (mock LLM, tool chain, max steps)
└── examples/
    ├── single_tool.py       # Quick demo: one tool call
    └── tool_chain.py        # Multi-step chaining demo
```

---

## Configuration

### config.yaml

```yaml
llm:
  model: gemini/gemini-2.5-flash   # Hot-swap: change and POST /reload-config
  temperature: 0.0
  max_tokens: 1024

agent:
  max_steps: 10
  traces_dir: ./traces

tools:
  read_file:
    sandbox_dir: ./data
  python_repl:
    timeout_seconds: 10
```

Swap `model` to any LiteLLM-supported provider:
- `gpt-4o` (OpenAI)
- `gemini/gemini-2.5-flash` (Google)
- `ollama/llama3` (Local, no API key)
- `mistral/mistral-large` (Mistral)

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| LiteLLM native `tools=` param | Uses OpenAI-compatible function calling — no brittle text parsing |
| Async agent loop (`litellm.acompletion`) | Non-blocking under FastAPI; multi-step runs can take 10-30s |
| AST whitelist for calculator | Prevents code injection — no raw `eval()` (OWASP compliant) |
| `http_get` URL scheme validation | Prevents SSRF — only http/https allowed |
| `read_file` sandbox via `Path.resolve()` | Prevents path traversal attacks |
| Traces as JSON files | Simple, inspectable, no DB dependency |
| Errors as observations | Agent recovers from tool failures instead of crashing |
| Retry with jitter | Prevents thundering herd on shared rate-limited APIs |

---

## Test Coverage

```
tests/test_tools.py    — 12 tests (calculator safe/unsafe, SSRF, sandbox escape, REPL)
tests/test_retry.py    —  5 tests (success, recovery, exhaustion, timing, async)
tests/test_agent.py    —  4 tests (single tool, chain, max steps, unknown tool)
─────────────────────────────────────────────────────────────
Total:                   31 tests passed
```

Run tests:
```bash
python -m pytest tests/ -v
```

---

## Upgrade Path

This project is the foundation for:

- **Project 5 — Multi-Agent Orchestrator**: supervisor agent delegates to specialized sub-agents built on this same loop
- **Project 17 — Web & Computer Use Agent**: extend `tools/` with Playwright browser actions (click, type, screenshot) and wire into the same ReAct loop

---

## Connection to Project 1

Project 4 is standalone — but optionally, the RAG pipeline from Project 1 can be registered as a tool, giving the agent access to your vector-indexed knowledge base:

```python
from src.tools.base import ToolDef
from projects.01_rag_app.src.pipeline import RAGPipeline

rag_tool = ToolDef(
    name="knowledge_search",
    description="Search internal documents for factual information",
    parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    fn=lambda query: RAGPipeline().query(query).answer,
)
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| litellm | 1.83.7 | LLM gateway — unified API for all providers |
| fastapi | 0.136.1 | API framework |
| uvicorn | 0.46.0 | ASGI server |
| pydantic | 2.12.5 | Config validation + request models |
| httpx | 0.28.1 | HTTP client for `http_get` tool |
| duckduckgo-search | ≥6.0 | Web search tool backend |
| PyYAML | 6.0.3 | Config file parsing |
| python-dotenv | 1.0.1 | `.env` loading |
| pytest | 9.0.3 | Test framework |
