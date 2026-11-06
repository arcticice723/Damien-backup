from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .ai import ChatMessage


SYSTEM_PROMPT = (
    "You are Damien, a private local Windows desktop assistant. "
    "Give highly useful, accurate answers that are easy to understand when read aloud. "
    "Write like you are speaking to the user in the room, not like you are texting. "
    "Prefer short spoken sentences, clear transitions, contractions, and plain phrasing. "
    "For simple requests, answer in one or two natural sentences. "
    "Do not use Markdown emphasis, headings, or numbered lists in ordinary spoken replies. "
    "If structure is genuinely needed, use clean plain text that still sounds natural aloud. "
    "Never answer with generic filler such as 'As a Windows desktop assistant' or a broad Windows help menu. "
    "If a requested ability is not wired in, say that clearly and suggest the missing Damien upgrade. "
    "Use lists only when they make the answer easier to hear or scan. "
    "Keep the cinematic aide feel subtle: calm, capable, and lightly personable. "
    "Use approved tools only when they directly satisfy the user request. "
    "Never claim to delete files, install software, change system settings, send messages, or buy anything."
)


class ConversationHistory:
    def __init__(self, path: Path, max_turns: int = 12) -> None:
        self.path = path
        self.max_turns = max_turns
        self.messages: list[ChatMessage] = [ChatMessage("system", SYSTEM_PROMPT)]
        self._load()

    def add_user(self, content: str) -> None:
        self._append(ChatMessage("user", content))

    def add_assistant(self, content: str) -> None:
        self._append(ChatMessage("assistant", content))

    def add_tool(self, content: str) -> None:
        self._append(ChatMessage("tool", content))

    def for_provider(self) -> list[ChatMessage]:
        return self.messages[:1] + self.messages[1:][-self.max_turns * 2 :]

    def _append(self, message: ChatMessage) -> None:
        self.messages.append(message)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": message.role,
            "content": message.content,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("role") in {"user", "assistant", "tool"} and record.get("content"):
                self.messages.append(ChatMessage(record["role"], record["content"]))
