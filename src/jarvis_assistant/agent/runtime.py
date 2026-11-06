from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..ai import ChatMessage
from ..audit import AuditEvent, AuditLogger
from ..improvement import (
    ImprovementQueue,
    UpgradeIntentHandler,
)
from ..router import ProviderRouter
from ..tools import ToolRegistry
from .command_response import CommandResponder
from .companion_voice import CompanionVoiceIntents, SAVED_ROUTINE_REQUEST
from .conversation import ConversationResponder
from .context import ContextCollector, ContextSnapshot
from .intent_pipeline import DirectIntentPipeline
from .multitask import MultitaskPlanner
from .notes import NoteIntentHandler, NoteStore
from .proactive import ProactiveControlHandler, ProactiveEngine, UnfinishedTaskStore
from .reminders import ReminderIntentHandler, ReminderStore
from .runtime_result import AgentTurnResult
from .tool_execution import ToolExecutionService


class AgentRuntime:
    def __init__(
        self,
        router: ProviderRouter,
        tools: ToolRegistry,
        audit: AuditLogger,
        persona_style: str = "cinematic",
        improvement_queue: ImprovementQueue | None = None,
        root: Path | None = None,
        now: Callable[[], object] | None = None,
        voice_status_provider: Callable[[], str] | None = None,
    ) -> None:
        self.router = router
        self.tools = tools
        self.audit = audit
        self.persona_style = persona_style
        self.conversation = ConversationResponder(audit, persona_style=persona_style)
        self.improvement_queue = improvement_queue or ImprovementQueue(root)
        self.upgrade_intents = UpgradeIntentHandler(self.improvement_queue)
        self.root = root
        self.now = now
        self.multitask_planner = MultitaskPlanner(self.tools)
        base_root = root or Path.cwd()
        self.unfinished_tasks = UnfinishedTaskStore(base_root / "tasks" / "unfinished.jsonl")
        self.tool_execution = ToolExecutionService(tools, audit, unfinished_tasks=self.unfinished_tasks)
        self.notes = NoteStore(base_root / "notes" / "agent_notes.jsonl")
        self.note_intents = NoteIntentHandler(self.notes)
        self.reminders = ReminderStore(base_root / "reminders" / "reminders.jsonl")
        self.reminder_intents = ReminderIntentHandler(self.reminders, now=self._current_time)
        self.proactive = ProactiveEngine(
            self.reminders,
            base_root / "reminders" / "proactive_state.json",
            improvements=self.improvement_queue,
            unfinished_tasks=self.unfinished_tasks,
            notes=self.notes,
            audit_path=getattr(audit, "path", None),
        )
        self.companion_voice = CompanionVoiceIntents(
            reminders=self.reminders,
            notes=self.notes,
            unfinished_tasks=self.unfinished_tasks,
            proactive=self.proactive,
            improvement_queue=self.improvement_queue,
            audit_path=getattr(audit, "path", None),
            now=self._current_time,
            voice_status_provider=voice_status_provider,
        )
        self.proactive_controls = ProactiveControlHandler(self.proactive, now=self._current_time)
        self.context_collector = ContextCollector(
            settings=self.router.settings,
            tools=self.tools,
            reminders=self.reminders,
            notes=self.notes,
            unfinished_tasks=self.unfinished_tasks,
            improvement_queue=self.improvement_queue,
            now=self._current_time,
        )
        self.latest_context: ContextSnapshot | None = None
        self.direct_intents = DirectIntentPipeline(
            [
                self.proactive_controls.handle,
                self.reminder_intents.handle,
                self.note_intents.handle,
            ]
        )
        self.commands = CommandResponder(
            tools=self.tools,
            execution=self.tool_execution,
            multitask_planner=self.multitask_planner,
            upgrade_intents=self.upgrade_intents,
            persona_style=persona_style,
        )

    def prepare(self, text: str, base_messages: list[ChatMessage]) -> AgentTurnResult:
        decision = self.router.route(text)
        self.latest_context = self.context_collector.collect(
            text,
            base_messages,
            include_approved_knowledge=not decision.cloud_data_sent,
        )
        routine_label = self._accepted_routine_request(text)
        if routine_label is not None:
            routine_response = self.commands.respond(
                routine_label,
                base_messages,
                provider=decision.provider,
                cloud_data_sent=decision.cloud_data_sent,
            )
            if routine_response is not None:
                return routine_response
        companion_response = self.companion_voice.handle(text)
        if companion_response is not None:
            return AgentTurnResult(
                provider=decision.provider,
                messages=base_messages,
                direct_response=companion_response,
                cloud_data_sent=decision.cloud_data_sent,
            )
        direct_response = self.direct_intents.handle(text)
        if direct_response is not None:
            return AgentTurnResult(
                provider=decision.provider,
                messages=base_messages,
                direct_response=direct_response,
                cloud_data_sent=decision.cloud_data_sent,
            )
        command_response = self.commands.respond(
            text,
            base_messages,
            provider=decision.provider,
            cloud_data_sent=decision.cloud_data_sent,
        )
        if command_response is not None and command_response.direct_response is not None:
            return command_response

        return self.conversation.respond(
            text,
            base_messages,
            provider=decision.provider,
            cloud_data_sent=decision.cloud_data_sent,
            tool_results=command_response.tool_results if command_response is not None else [],
            interpretation=command_response.interpretation if command_response is not None else None,
            context=self.latest_context,
        )

    def _current_time(self):
        if self.now is not None:
            value = self.now()
            if hasattr(value, "tzinfo"):
                return value
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)

    def check_proactive(self) -> list[str]:
        notices = self.proactive.check(self._current_time())
        for notice in notices:
            self.audit.log(
                AuditEvent(
                    user_request=f"proactive:{notice.id.split(':', 1)[0]}",
                    provider="local",
                    tools_called=["proactive_notice"],
                    outcome=f"{notice.reason}: {notice.message}",
                )
            )
        return [notice.message for notice in notices]

    def _accepted_routine_request(self, text: str) -> str | None:
        if not SAVED_ROUTINE_REQUEST.matches(text):
            return None
        return self.proactive.latest_accepted_routine_label()
