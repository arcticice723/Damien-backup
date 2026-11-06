from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .ai import ChatMessage
from .agent import AgentRuntime
from .audit import AuditEvent, AuditLogger
from .interpretation import Interpretation
from .improvement import ImprovementQueue
from .router import ProviderRouter
from .runtime import APP_ROOT
from .tools import ToolRegistry, ToolResult


@dataclass(frozen=True)
class OrchestrationResult:
    provider: str
    messages: list[ChatMessage]
    direct_response: str | None = None
    tool_results: list[ToolResult] = field(default_factory=list)
    cloud_data_sent: bool = False
    interpretation: Interpretation | None = None


class AssistantOrchestrator:
    def __init__(
        self,
        router: ProviderRouter,
        tools: ToolRegistry,
        audit: AuditLogger,
        persona_style: str = "cinematic",
        improvement_queue: ImprovementQueue | None = None,
        root: Path | None = None,
        voice_status_provider: Callable[[], str] | None = None,
    ) -> None:
        self.router = router
        self.tools = tools
        self.audit = audit
        self.improvement_queue = improvement_queue or ImprovementQueue(root or APP_ROOT)
        self.agent = AgentRuntime(
            router,
            tools,
            audit,
            persona_style=persona_style,
            improvement_queue=self.improvement_queue,
            root=root or APP_ROOT,
            voice_status_provider=voice_status_provider,
        )

    def prepare(self, text: str, base_messages: list[ChatMessage]) -> OrchestrationResult:
        result = self.agent.prepare(text, base_messages)
        return OrchestrationResult(
            provider=result.provider,
            messages=result.messages,
            direct_response=result.direct_response,
            tool_results=result.tool_results,
            cloud_data_sent=result.cloud_data_sent,
            interpretation=result.interpretation,
        )

    def check_proactive(self) -> list[str]:
        return self.agent.check_proactive()

    def log_final(self, text: str, result: OrchestrationResult, outcome: str) -> None:
        self.audit.log(
            AuditEvent(
                user_request=text,
                provider=result.provider,
                tools_called=[tool.name for tool in result.tool_results],
                cloud_data_sent=result.cloud_data_sent,
                confirmations_requested=[tool.name for tool in result.tool_results if tool.confirmation_required],
                outcome=outcome[:500],
            )
        )
