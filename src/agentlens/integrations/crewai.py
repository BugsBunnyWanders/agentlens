"""CrewAI integration — extends LangChain handler with crew-level span detection."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from agentlens.integrations._base import safe_serialize
from agentlens.sdk.models import SpanKind

try:
    from agentlens.integrations.langchain import AgentLensCallbackHandler
except ImportError:
    raise ImportError(
        "CrewAI integration requires 'langchain-core'. "
        "Install with: pip install agentlens-xray[crewai]"
    )


class CrewAIHandler(AgentLensCallbackHandler):
    """Extended LangChain handler with CrewAI-specific span detection.

    Usage:
        from agentlens.integrations.crewai import CrewAIHandler

        handler = CrewAIHandler(trace_name="my_crew")
        crew = Crew(agents=[...], tasks=[...], callbacks=[handler])
        result = crew.kickoff()
    """

    def __init__(
        self,
        trace_name: str = "crewai",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            trace_name=trace_name,
            metadata={**(metadata or {}), "framework": "crewai"},
        )

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        id_list = serialized.get("id", [])
        name_str = serialized.get("name", "")
        id_str = " ".join(str(s) for s in id_list).lower()

        # Detect CrewAI patterns
        if "crew" in id_str or "crew" in name_str.lower():
            span = self._create_span(
                name_str or "Crew", SpanKind.AGENT, run_id, parent_run_id
            )
            if span:
                span.record_input(safe_serialize(inputs))
            return

        if "task" in id_str or "task" in name_str.lower():
            task_desc = inputs.get("task_description", inputs.get("description", ""))
            span = self._create_span(
                name_str or "Task", SpanKind.CHAIN, run_id, parent_run_id
            )
            if span:
                span.record_input(safe_serialize(inputs))
            return

        if "agent" in id_str:
            role = inputs.get("role", inputs.get("agent_role", ""))
            span_name = role or name_str or "Agent"
            span = self._create_span(
                str(span_name), SpanKind.AGENT, run_id, parent_run_id
            )
            if span:
                span.record_input(safe_serialize(inputs))
            return

        # Fall back to default LangChain handling
        super().on_chain_start(
            serialized, inputs, run_id=run_id, parent_run_id=parent_run_id, **kwargs
        )
