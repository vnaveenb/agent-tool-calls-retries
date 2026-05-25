from __future__ import annotations

import yaml
from pathlib import Path
from pydantic import BaseModel


class LLMConfig(BaseModel):
    model: str = "gemini/gemini-2.5-flash"
    temperature: float = 0.0
    max_tokens: int = 1024
    thinking_budget: int | None = None  # For thinking models (e.g. Gemini 2.5)


class AgentConfig(BaseModel):
    max_steps: int = 10
    traces_dir: str = "./traces"


class SubAgentConfig(BaseModel):
    """Per-sub-agent overrides (optional)."""
    max_steps: int | None = None
    max_tokens: int | None = None
    model: str | None = None


class AgentsConfig(BaseModel):
    """Configuration for the multi-agent orchestrator."""
    use_orchestrator: bool = True  # False = legacy single-agent mode
    supervisor: SubAgentConfig = SubAgentConfig(max_tokens=512)
    research: SubAgentConfig = SubAgentConfig(max_steps=5, max_tokens=4096)
    doc_generator: SubAgentConfig = SubAgentConfig(max_steps=10, max_tokens=16384)
    general: SubAgentConfig = SubAgentConfig(max_steps=8, max_tokens=4096)


class ReadFileToolConfig(BaseModel):
    sandbox_dir: str = "./data"


class PythonReplToolConfig(BaseModel):
    timeout_seconds: int = 10


class ToolsConfig(BaseModel):
    read_file: ReadFileToolConfig = ReadFileToolConfig()
    python_repl: PythonReplToolConfig = PythonReplToolConfig()


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    agent: AgentConfig = AgentConfig()
    agents: AgentsConfig = AgentsConfig()
    tools: ToolsConfig = ToolsConfig()


_config: AppConfig | None = None


def get_config(path: str = "config.yaml") -> AppConfig:
    global _config
    if _config is None:
        cfg_path = Path(path)
        if cfg_path.exists():
            with open(cfg_path) as f:
                raw = yaml.safe_load(f) or {}
            _config = AppConfig(**raw)
        else:
            _config = AppConfig()
    return _config


def reload_config(path: str = "config.yaml") -> AppConfig:
    """Force reload from disk — used by POST /reload-config."""
    global _config
    _config = None
    return get_config(path)
