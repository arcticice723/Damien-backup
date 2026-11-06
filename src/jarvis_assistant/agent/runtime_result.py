from __future__ import annotations

from dataclasses import dataclass, field

from ..ai import ChatMessage
from ..interpretation import Interpretation
from ..tools import ToolResult


@dataclass(frozen=True)
class AgentTurnResult:
    provider: str
    messages: list[ChatMessage]
    direct_response: str | None = None
    tool_results: list[ToolResult] = field(default_factory=list)
    cloud_data_sent: bool = False
    interpretation: Interpretation | None = None
