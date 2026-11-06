from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..ai import ChatMessage
from ..improvement import ImprovementQueue
from ..tools import ToolRegistry
from .notes import NoteStore
from .proactive import UnfinishedTaskStore
from .reminders import ReminderStore


@dataclass(frozen=True)
class ContextSnapshot:
    utterance: str
    recent_messages: list[ChatMessage]
    settings_summary: str
    available_tools: list[str]
    pending_reminders: list[str]
    saved_notes: list[str]
    unfinished_followups: list[str]
    queued_upgrades: list[str]
    approved_knowledge: list[str] = field(default_factory=list)


class ContextCollector:
    def __init__(
        self,
        *,
        settings: object,
        tools: ToolRegistry,
        reminders: ReminderStore,
        notes: NoteStore,
        unfinished_tasks: UnfinishedTaskStore,
        improvement_queue: ImprovementQueue,
        now: Callable[[], object],
        history_limit: int = 6,
        item_limit: int = 5,
    ) -> None:
        self.settings = settings
        self.tools = tools
        self.reminders = reminders
        self.notes = notes
        self.unfinished_tasks = unfinished_tasks
        self.improvement_queue = improvement_queue
        self.now = now
        self.history_limit = history_limit
        self.item_limit = item_limit

    def collect(
        self,
        utterance: str,
        messages: list[ChatMessage],
        *,
        include_approved_knowledge: bool = True,
    ) -> ContextSnapshot:
        now = self.now()
        return ContextSnapshot(
            utterance=utterance,
            recent_messages=messages[-self.history_limit :],
            settings_summary=self._settings_summary(),
            available_tools=self._available_tools(),
            pending_reminders=[record.message for record in self.reminders.pending(now)[-self.item_limit :]],
            saved_notes=[record.content for record in self.notes.list_recent(limit=self.item_limit)],
            unfinished_followups=[record.title for record in self.unfinished_tasks.open()[-self.item_limit :]],
            queued_upgrades=self._queued_upgrades(),
            approved_knowledge=self._approved_knowledge(utterance) if include_approved_knowledge else [],
        )

    def _approved_knowledge(self, utterance: str) -> list[str]:
        if not getattr(self.settings, "enable_retrieval", False):
            return []
        try:
            return self.tools.retriever.search(utterance, limit=3)
        except Exception:
            return []

    def _settings_summary(self) -> str:
        fields = [
            "free_only_mode",
            "enable_cloud_provider",
            "proactive_enabled",
            "proactive_voice_enabled",
            "reminder_check_seconds",
            "remote_brain_base_url",
        ]
        return "; ".join(f"{field}={getattr(self.settings, field, '')}" for field in fields)

    def _available_tools(self) -> list[str]:
        samples = {
            "local_time": "what time is it",
            "system_status": "system status",
            "list_notes": "show my notes",
            "list_approved_apps": "what apps can you open",
            "blocked_high_risk_action": "delete all files",
        }
        tools: list[str] = []
        for label, prompt in samples.items():
            planned = self.tools.plan(prompt)
            if planned is None:
                continue
            tools.append(f"{label}:{planned.risk.value}")
        return tools

    def _queued_upgrades(self) -> list[str]:
        latest = self.improvement_queue.latest()
        if latest is None:
            return []
        suggestion = str(latest.get("suggestion", "")).strip()
        return [suggestion] if suggestion else []
