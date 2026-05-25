"""Multi-agent architecture: Supervisor + specialized sub-agents."""
from .base import BaseAgent, AgentStep, AgentResult, TokenUsage
from .supervisor import SupervisorAgent
from .research import ResearchAgent
from .doc_generator import DocGeneratorAgent
from .general import GeneralAgent

__all__ = [
    "BaseAgent",
    "AgentStep",
    "AgentResult",
    "TokenUsage",
    "SupervisorAgent",
    "ResearchAgent",
    "DocGeneratorAgent",
    "GeneralAgent",
]
