"""Framework integrations for AgentLens.

Imports are lazy — no framework dependency is required until the class is instantiated.

Usage:
    from agentlens.integrations import LangChainHandler
    from agentlens.integrations import OpenAIAgentsProcessor
    from agentlens.integrations import CrewAIHandler
    from agentlens.integrations import wrap_openai, wrap_anthropic
"""

from __future__ import annotations

_LAZY_IMPORTS = {
    "AgentLensCallbackHandler": ("agentlens.integrations.langchain", "AgentLensCallbackHandler"),
    "LangChainHandler": ("agentlens.integrations.langchain", "AgentLensCallbackHandler"),
    "AgentLensTracingProcessor": ("agentlens.integrations.openai_agents", "AgentLensTracingProcessor"),
    "OpenAIAgentsProcessor": ("agentlens.integrations.openai_agents", "AgentLensTracingProcessor"),
    "install_agentlens_tracing": ("agentlens.integrations.openai_agents", "install_agentlens_tracing"),
    "CrewAIHandler": ("agentlens.integrations.crewai", "CrewAIHandler"),
    "wrap_openai": ("agentlens.integrations.clients", "wrap_openai"),
    "wrap_anthropic": ("agentlens.integrations.clients", "wrap_anthropic"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    raise AttributeError(f"module 'agentlens.integrations' has no attribute {name}")
