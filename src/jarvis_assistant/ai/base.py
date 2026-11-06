from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    tool_calls: list[dict] | None = None


@dataclass(frozen=True)
class GenerationStats:
    elapsed_seconds: float
    prompt_eval_count: int = 0
    eval_count: int = 0
    tokens_per_second: float = 0.0


@dataclass(frozen=True)
class ConnectionStatus:
    reachable: bool
    url: str
    detail: str = ""


@dataclass(frozen=True)
class StreamEvent:
    kind: str
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    stats: GenerationStats | None = None


class AIProvider(Protocol):
    def stream(self, messages: list[ChatMessage], tools: list[dict] | None = None) -> Iterable[StreamEvent]:
        """Stream text, optional tool calls, and final timing statistics."""
