import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import jarvis_assistant.agent as agent_api
import jarvis_assistant.agent.runtime as runtime_api
from jarvis_assistant.agent.command_response import CommandResponder
from jarvis_assistant.agent.context import ContextCollector
from jarvis_assistant.agent.conversation import ConversationResponder
from jarvis_assistant.agent.multitask import MultitaskPlanner
from jarvis_assistant.agent.proactive import UnfinishedTaskStore
from jarvis_assistant.agent.runtime import AgentRuntime
from jarvis_assistant.agent.tool_execution import ToolExecutionService
from jarvis_assistant.ai import ChatMessage
from jarvis_assistant.audit import AuditEvent, AuditLogger
from jarvis_assistant.commands import ApprovedApp, CommandDispatcher
from jarvis_assistant.config import load_settings
from jarvis_assistant.improvement import ImprovementQueue, SelfRepairManager
from jarvis_assistant.memory import LongTermMemory
from jarvis_assistant.retrieval import ApprovedDocumentRetriever
from jarvis_assistant.router import ProviderRouter
from jarvis_assistant.tools import PlannedTool, RiskLevel, ToolRegistry, ToolResult


def build_runtime(root: Path) -> AgentRuntime:
    tools = ToolRegistry(
        CommandDispatcher({}),
        ApprovedDocumentRetriever(root / "docs"),
        LongTermMemory(root / "memory.jsonl", enabled=False),
    )
    return AgentRuntime(
        router=ProviderRouter(load_settings(root / "settings.json")),
        tools=tools,
        audit=AuditLogger(root / "audit.jsonl", enabled=False),
        persona_style="cinematic",
        root=root,
    )


class AgentRuntimeTests(unittest.TestCase):
    def test_command_responder_corrects_stt_noise_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            audit = AuditLogger(root / "audit.jsonl", enabled=False)
            responder = CommandResponder(
                tools=tools,
                execution=ToolExecutionService(tools, audit),
                multitask_planner=MultitaskPlanner(tools),
                upgrade_intents=runtime_api.UpgradeIntentHandler(runtime_api.ImprovementQueue(root)),
            )

            with patch.object(tools.convenience, "local_time", return_value="Local time: Monday at 10:00 AM"):
                result = responder.respond(
                    "what thyme is it",
                    [ChatMessage("user", "what thyme is it")],
                    provider="local",
                    cloud_data_sent=False,
                )

        self.assertIsNotNone(result)
        self.assertEqual(result.direct_response, "Local time: Monday at 10:00 AM")
        self.assertEqual(result.interpretation.corrected, "what time is it")

    def test_conversation_responder_keeps_latest_user_turn_last_and_logs_audit(self):
        class RecordingAudit:
            def __init__(self) -> None:
                self.events: list[AuditEvent] = []

            def log(self, event: AuditEvent) -> None:
                self.events.append(event)

        audit = RecordingAudit()
        responder = ConversationResponder(audit, persona_style="cinematic")

        result = responder.respond(
            "tell me a quick joke",
            [
                ChatMessage("system", "Existing context."),
                ChatMessage("user", "tell me a quick joke"),
            ],
            provider="local",
            cloud_data_sent=False,
            tool_results=[],
            interpretation=None,
        )

        self.assertIsNone(result.direct_response)
        self.assertEqual(result.messages[-1], ChatMessage("user", "tell me a quick joke"))
        self.assertEqual(audit.events[0].outcome, "Routed to model.")

    def test_runtime_logs_unsupported_action_requests_as_upgrade_before_model_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)

            result = runtime.prepare(
                "turn on my bedroom lights",
                [ChatMessage("user", "turn on my bedroom lights")],
            )

            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertIsNotNone(result.direct_response)
        self.assertIn("upgrade for Codex", result.direct_response)
        self.assertEqual(result.messages, [ChatMessage("user", "turn on my bedroom lights")])
        self.assertEqual(records[0]["request"], "turn on my bedroom lights")
        self.assertIn("Add or improve the Damien tool", records[0]["suggestion"])

    def test_runtime_keeps_normal_conversation_on_model_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare("tell me a quick joke", [ChatMessage("user", "tell me a quick joke")])

        self.assertIsNone(result.direct_response)
        self.assertEqual(result.messages[-1], ChatMessage("user", "tell me a quick joke"))

    def test_public_agent_api_does_not_expose_legacy_plan_types(self):
        self.assertFalse(hasattr(agent_api, "AgentContext"))
        self.assertFalse(hasattr(agent_api, "AgentPlan"))
        self.assertFalse(hasattr(agent_api, "AgentPlanKind"))
        self.assertFalse(hasattr(runtime_api, "AgentContext"))
        self.assertFalse(hasattr(runtime_api, "AgentPlan"))
        self.assertFalse(hasattr(runtime_api, "AgentPlanKind"))

    def test_runtime_routes_direct_intents_through_extensible_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.direct_intents.handlers.insert(0, lambda text: "Pipeline handled it." if text == "ping" else None)

            result = runtime.prepare("ping", [ChatMessage("user", "ping")])

        self.assertEqual(result.direct_response, "Pipeline handled it.")
        self.assertEqual(result.messages, [ChatMessage("user", "ping")])

    def test_context_collector_builds_bounded_local_context(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.note_intents.handle("remember that the garage remote is in my backpack")
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            collector = ContextCollector(
                settings=runtime.router.settings,
                tools=runtime.tools,
                reminders=runtime.reminders,
                notes=runtime.notes,
                unfinished_tasks=runtime.unfinished_tasks,
                improvement_queue=runtime.improvement_queue,
                now=runtime._current_time,
                history_limit=2,
            )

            snapshot = collector.collect(
                "what needs my attention",
                [
                    ChatMessage("user", "older"),
                    ChatMessage("assistant", "older reply"),
                    ChatMessage("user", "recent"),
                ],
            )

        self.assertEqual(snapshot.utterance, "what needs my attention")
        self.assertEqual(snapshot.recent_messages, [ChatMessage("assistant", "older reply"), ChatMessage("user", "recent")])
        self.assertIn("proactive_enabled=True", snapshot.settings_summary)
        self.assertIn("local_time:low", snapshot.available_tools)
        self.assertEqual(snapshot.pending_reminders, ["stretch"])
        self.assertEqual(snapshot.saved_notes, ["the garage remote is in my backpack"])
        self.assertEqual(snapshot.unfinished_followups, ["Follow up on: open roblox"])

    def test_runtime_builds_context_snapshot_each_turn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare("tell me a quick joke", [ChatMessage("user", "tell me a quick joke")])

        self.assertIsNotNone(runtime.latest_context)
        self.assertEqual(runtime.latest_context.utterance, "tell me a quick joke")

    def test_runtime_supplies_context_snapshot_to_model_fallback(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.note_intents.handle("remember that the garage remote is in my backpack")
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The lobby was not confirmed.")
            runtime.improvement_queue.log(
                request="open the smart lights",
                reason="No smart-home connector exists.",
                suggestion="Add a smart-home device connector.",
            )

            result = runtime.prepare(
                "talk through my evening with me",
                [ChatMessage("user", "talk through my evening with me")],
            )

        context_messages = [
            message.content
            for message in result.messages
            if message.role == "system" and message.content.startswith("Current local context for Damien:")
        ]
        self.assertEqual(len(context_messages), 1)
        context = context_messages[0]
        self.assertIn("Pending reminders: stretch", context)
        self.assertIn("Saved notes: the garage remote is in my backpack", context)
        self.assertIn("Unfinished follow-ups: Follow up on: open roblox", context)
        self.assertIn("Queued upgrades: Add a smart-home device connector.", context)
        self.assertEqual(result.messages[-1], ChatMessage("user", "talk through my evening with me"))

    def test_runtime_uses_audit_history_for_repeated_routine_notices(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audit_path = root / "audit.jsonl"
            for _ in range(3):
                with audit_path.open("a", encoding="utf-8") as file:
                    file.write(
                        json.dumps(
                            {
                                "user_request": "open roblox and start my lobby",
                                "provider": "local",
                                "tools_called": ["open_approved_app", "take_me_to_lobby"],
                                "outcome": "Roblox opened. Lobby automation started.",
                            },
                            ensure_ascii=True,
                        )
                        + "\n"
                    )
            runtime = build_runtime(root)
            runtime.now = lambda: now

            notices = runtime.check_proactive()

        self.assertEqual(
            notices,
            ["Routine: You often ask me to open roblox and start my lobby. I can help make that quicker."],
        )

    def test_runtime_logs_proactive_notice_reason_to_audit(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl"),
                persona_style="cinematic",
                root=root,
                now=lambda: now,
            )
            runtime.reminders.create("stretch", now)

            notices = runtime.check_proactive()
            payload = json.loads((root / "audit.jsonl").read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(notices, ["Reminder: stretch"])
        self.assertEqual(payload["user_request"], "proactive:reminder")
        self.assertEqual(payload["tools_called"], ["proactive_notice"])
        self.assertEqual(payload["outcome"], "due_reminder: Reminder: stretch")

    def test_runtime_explains_latest_proactive_notice_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl"),
                persona_style="cinematic",
                root=root,
                now=lambda: now,
            )
            runtime.reminders.create("stretch", now)
            runtime.check_proactive()

            result = runtime.prepare(
                "why did you say that",
                [ChatMessage("user", "why did you say that")],
            )

        self.assertEqual(result.direct_response, "I spoke up because a reminder is due: stretch")

    def test_runtime_explains_finished_self_repair_notice_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repair_manager = SelfRepairManager(root, runner=lambda command, cwd, transcript: None)
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=ToolRegistry(
                    CommandDispatcher({}),
                    ApprovedDocumentRetriever(root / "docs"),
                    LongTermMemory(root / "memory.jsonl", enabled=False),
                ),
                audit=AuditLogger(root / "audit.jsonl"),
                persona_style="cinematic",
                root=root,
                improvement_queue=ImprovementQueue(root, repair_manager=repair_manager),
            )
            runtime.now = lambda: now
            runtime.improvement_queue.log(
                request="Take Apex Legends to lobby",
                reason="Could not confirm lobby status.",
                suggestion="Improve game lobby status detection for Apex Legends.",
            )
            repair_log = root / "logs" / "self_repair.jsonl"
            fingerprint = json.loads(repair_log.read_text(encoding="utf-8").splitlines()[-1])["fingerprint"]
            with repair_log.open("a", encoding="utf-8") as file:
                file.write(json.dumps({"fingerprint": fingerprint, "status": "completed"}) + "\n")
            (root / "logs" / "self_repair_notes.md").write_text(
                "# Self Repair Notes\n\n"
                "## Apex lobby status fallback\n\n"
                "- Change: Damien now treats a matching visible game window as a successful handoff.\n",
                encoding="utf-8",
            )
            runtime.check_proactive()

            result = runtime.prepare("why did you say that", [ChatMessage("user", "why did you say that")])

        self.assertEqual(
            result.direct_response,
            "I spoke up because a repair finished: Damien now treats a matching visible game window as a successful handoff.",
        )

    def test_runtime_replays_latest_proactive_notice_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl"),
                persona_style="cinematic",
                root=root,
                now=lambda: now,
            )
            runtime.reminders.create("stretch", now)
            runtime.check_proactive()

            result = runtime.prepare(
                "what did you just say?",
                [ChatMessage("user", "what did you just say?")],
            )

        self.assertEqual(result.direct_response, "I just said: Reminder: stretch")

    def test_runtime_answers_short_thanks_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare("thanks", [ChatMessage("user", "thanks")])

        self.assertEqual(result.direct_response, "Anytime.")

    def test_runtime_answers_thanks_with_wake_name_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare("thanks Damien", [ChatMessage("user", "thanks Damien")])

        self.assertEqual(result.direct_response, "Anytime.")

    def test_runtime_answers_got_it_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare("got it", [ChatMessage("user", "got it")])

        self.assertEqual(result.direct_response, "Got it.")

    def test_runtime_summarizes_active_companion_watchlist_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("move the laundry", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            state_path = root / "reminders" / "proactive_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "delivered": ["routine:roblox"],
                        "accepted_routines": [{"id": "routine:roblox", "label": "open roblox and start my lobby"}],
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = runtime.prepare(
                "what are you keeping track of",
                [ChatMessage("user", "what are you keeping track of")],
            )

        self.assertEqual(
            result.direct_response,
            "I am keeping track of:\n"
            "- 1 pending reminder: move the laundry\n"
            "- 1 unfinished followup: Follow up on: open roblox\n"
            "- 1 saved routine: open roblox and start my lobby",
        )

    def test_runtime_summarizes_active_watchlist_with_companion_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("move the laundry", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            state_path = root / "reminders" / "proactive_state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "delivered": ["routine:roblox"],
                        "accepted_routines": [{"id": "routine:roblox", "label": "open roblox and start my lobby"}],
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )

            result = runtime.prepare(
                "what are you on top of for me?",
                [ChatMessage("user", "what are you on top of for me?")],
            )

        self.assertEqual(
            result.direct_response,
            "I am keeping track of:\n"
            "- 1 pending reminder: move the laundry\n"
            "- 1 unfinished followup: Follow up on: open roblox\n"
            "- 1 saved routine: open roblox and start my lobby",
        )

    def test_runtime_summarizes_saved_notes_in_active_watchlist(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.note_intents.handle("remember that the garage remote is in my backpack")

            result = runtime.prepare(
                "what are you keeping track of",
                [ChatMessage("user", "what are you keeping track of")],
            )

        self.assertEqual(
            result.direct_response,
            "I am keeping track of:\n"
            "- 1 saved note: the garage remote is in my backpack",
        )

    def test_runtime_summarizes_active_watchlist_with_what_are_you_doing_now(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("move the laundry", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what are you doing now?",
                [ChatMessage("user", "what are you doing now?")],
            )

        self.assertEqual(
            result.direct_response,
            "I am keeping track of:\n"
            "- 1 pending reminder: move the laundry\n"
            "- 1 unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_active_watchlist_with_what_are_you_working_on(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("move the laundry", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what are you working on?",
                [ChatMessage("user", "what are you working on?")],
            )

        self.assertEqual(
            result.direct_response,
            "I am keeping track of:\n"
            "- 1 pending reminder: move the laundry\n"
            "- 1 unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_active_watchlist_with_watching_out_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("move the laundry", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what are you watching out for?",
                [ChatMessage("user", "what are you watching out for?")],
            )

        self.assertEqual(
            result.direct_response,
            "I am keeping track of:\n"
            "- 1 pending reminder: move the laundry\n"
            "- 1 unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_answers_clear_watchlist_with_watching_out_phrase(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "what are you watching out for?",
                [ChatMessage("user", "what are you watching out for?")],
            )

        self.assertEqual(result.direct_response, "I am not keeping track of anything active right now.")

    def test_runtime_summarizes_active_watchlist_with_quiet_mode(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

            result = runtime.prepare(
                "what are you doing now?",
                [ChatMessage("user", "what are you doing now?")],
            )

        self.assertEqual(
            result.direct_response,
            "I am keeping track of:\n"
            "- Staying quiet until 01:00 PM",
        )

    def test_runtime_summarizes_items_needing_attention_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.reminders.create("start dinner", now.replace(hour=18))
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.improvement_queue.log(
                request="Damien should handle my lobby faster",
                reason="Repeated manual routine.",
                suggestion="Add a faster lobby routine.",
            )

            result = runtime.prepare(
                "what needs my attention",
                [ChatMessage("user", "what needs my attention")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox\n"
            "- Opportunity: Add a faster lobby routine.",
        )

    def test_runtime_summarizes_attention_items_with_quiet_mode(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

            result = runtime.prepare(
                "what needs my attention",
                [ChatMessage("user", "what needs my attention")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Quiet mode: staying quiet until 01:00 PM",
        )

    def test_runtime_summarizes_time_sensitive_note_as_attention_item(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.note_intents.handle("remember that package arrives today")

            result = runtime.prepare(
                "what needs my attention",
                [ChatMessage("user", "what needs my attention")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Heads up: package arrives today",
        )

    def test_runtime_summarizes_attention_items_with_natural_handle_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what do I need to handle?",
                [ChatMessage("user", "what do I need to handle?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_counts_items_waiting_for_attention_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.note_intents.handle("remember that package arrives today")

            result = runtime.prepare(
                "how much is waiting?",
                [ChatMessage("user", "how much is waiting?")],
            )

        self.assertEqual(result.direct_response, "3 things need your attention. First: stretch")

    def test_runtime_counts_no_items_waiting_for_attention_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "how much is waiting?",
                [ChatMessage("user", "how much is waiting?")],
            )

        self.assertEqual(result.direct_response, "Nothing needs your attention right now.")

    def test_runtime_counts_one_item_waiting_for_attention_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            result = runtime.prepare(
                "how much is waiting?",
                [ChatMessage("user", "how much is waiting?")],
            )

        self.assertEqual(result.direct_response, "1 thing needs your attention. First: stretch")

    def test_runtime_reads_attention_items_aloud_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "read it to me",
                [ChatMessage("user", "read it to me")],
            )

        self.assertEqual(
            result.direct_response,
            "Reading what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_reads_attention_items_aloud_when_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "read what is waiting",
                [ChatMessage("user", "read what is waiting")],
            )

        self.assertEqual(result.direct_response, "Nothing needs your attention right now.")

    def test_runtime_summarizes_attention_items_with_whats_next_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what's next?",
                [ChatMessage("user", "what's next?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_whats_waiting_for_me_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what's waiting for me?",
                [ChatMessage("user", "what's waiting for me?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_anything_going_on_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "anything going on?",
                [ChatMessage("user", "anything going on?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_need_anything_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "need anything from me?",
                [ChatMessage("user", "need anything from me?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_need_me_for_anything_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "do you need me for anything?",
                [ChatMessage("user", "do you need me for anything?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_do_i_need_to_do_anything_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "do I need to do anything?",
                [ChatMessage("user", "do I need to do anything?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_anything_i_should_handle_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "is there anything I should handle?",
                [ChatMessage("user", "is there anything I should handle?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_answers_nothing_for_do_i_need_to_do_anything_when_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "do I need to do anything?",
                [ChatMessage("user", "do I need to do anything?")],
            )

        self.assertEqual(result.direct_response, "Nothing needs your attention right now.")

    def test_runtime_answers_what_should_i_handle_first_with_top_attention_item(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what should I handle first?",
                [ChatMessage("user", "what should I handle first?")],
            )

        self.assertEqual(result.direct_response, "First: stretch")

    def test_runtime_explains_why_top_attention_item_is_first(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.prepare(
                "what should I handle first?",
                [ChatMessage("user", "what should I handle first?")],
            )

            result = runtime.prepare(
                "why that first?",
                [ChatMessage("user", "why that first?")],
            )

        self.assertEqual(result.direct_response, "Because it is due now: stretch")

    def test_runtime_answers_what_should_i_handle_next_after_handling_first_item(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.prepare("handle the first one", [ChatMessage("user", "handle the first one")])

            result = runtime.prepare(
                "what should I handle next?",
                [ChatMessage("user", "what should I handle next?")],
            )

        self.assertEqual(result.direct_response, "Next: Follow up on: open roblox")

    def test_runtime_answers_what_should_i_handle_next_when_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "what should I handle next?",
                [ChatMessage("user", "what should I handle next?")],
            )

        self.assertEqual(result.direct_response, "Nothing needs your attention right now.")

    def test_runtime_answers_what_else_after_handling_first_item(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.prepare("handle the first one", [ChatMessage("user", "handle the first one")])

            result = runtime.prepare(
                "what else?",
                [ChatMessage("user", "what else?")],
            )

        self.assertEqual(result.direct_response, "Next: Follow up on: open roblox")

    def test_runtime_answers_what_else_when_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "what else?",
                [ChatMessage("user", "what else?")],
            )

        self.assertEqual(result.direct_response, "Nothing needs your attention right now.")

    def test_runtime_answers_what_should_i_handle_first_when_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "what should I handle first?",
                [ChatMessage("user", "what should I handle first?")],
            )

        self.assertEqual(result.direct_response, "Nothing needs your attention right now.")

    def test_runtime_explains_no_first_attention_item_when_clear(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "why that first?",
                [ChatMessage("user", "why that first?")],
            )

        self.assertEqual(result.direct_response, "Nothing needs your attention right now.")

    def test_runtime_answers_what_should_i_handle_first_with_note_heads_up(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.note_intents.handle("remember that package arrives today")

            result = runtime.prepare(
                "what should I handle first?",
                [ChatMessage("user", "what should I handle first?")],
            )

        self.assertEqual(result.direct_response, "First: package arrives today")

    def test_runtime_explains_why_note_heads_up_is_first(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.note_intents.handle("remember that package arrives today")

            result = runtime.prepare(
                "why that first?",
                [ChatMessage("user", "why that first?")],
            )

        self.assertEqual(result.direct_response, "Because it is time-sensitive: package arrives today")

    def test_runtime_summarizes_attention_items_with_stt_eye_for_i(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what should eye look at?",
                [ChatMessage("user", "what should eye look at?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_on_my_plate_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what's on my plate?",
                [ChatMessage("user", "what's on my plate?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_wake_name_prefix(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "Damien, what's on my plate?",
                [ChatMessage("user", "Damien, what's on my plate?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_hey_wake_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "Hey Damien, what's on my plate?",
                [ChatMessage("user", "Hey Damien, what's on my plate?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_okay_wake_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "Okay Damien, what's on my plate?",
                [ChatMessage("user", "Okay Damien, what's on my plate?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_wake_name_and_polite_prefix(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "Damien, please what's on my plate?",
                [ChatMessage("user", "Damien, please what's on my plate?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_summarizes_attention_items_with_compound_polite_prefix(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "Damien, can you please what's on my plate?",
                [ChatMessage("user", "Damien, can you please what's on my plate?")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_attention_check_skips_dismissed_due_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            runtime.check_proactive()
            runtime.prepare("dismiss that", [ChatMessage("user", "dismiss that")])
            result = runtime.prepare(
                "what needs my attention",
                [ChatMessage("user", "what needs my attention")],
            )

        self.assertEqual(
            result.direct_response,
            "Here is what needs attention:\n"
            "- Unfinished followup: Follow up on: open roblox",
        )

    def test_runtime_gives_start_my_day_brief_by_voice(self):
        now = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("take vitamins", now)
            runtime.reminders.create("start dinner", now.replace(hour=18, minute=0))
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "start my day",
                [ChatMessage("user", "start my day")],
            )

        self.assertEqual(
            result.direct_response,
            "Good morning. Here's your brief:\n"
            "- Due now: take vitamins\n"
            "- Later today: start dinner at 06:00 PM\n"
            "- Still open: Follow up on: open roblox",
        )

    def test_runtime_gives_start_my_day_brief_without_apostrophe(self):
        now = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("take vitamins", now)

            result = runtime.prepare(
                "whats my day look like?",
                [ChatMessage("user", "whats my day look like?")],
            )

        self.assertEqual(
            result.direct_response,
            "Good morning. Here's your brief:\n"
            "- Due now: take vitamins",
        )

    def test_runtime_gives_start_my_day_brief_with_quiet_mode(self):
        now = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

            result = runtime.prepare(
                "start my day",
                [ChatMessage("user", "start my day")],
            )

        self.assertEqual(
            result.direct_response,
            "Good morning. Here's your brief:\n"
            "- Quiet mode: staying quiet until 09:30 AM",
        )

    def test_runtime_start_my_day_skips_dismissed_due_reminder(self):
        now = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("take vitamins", now)
            runtime.reminders.create("start dinner", now.replace(hour=18, minute=0))

            runtime.check_proactive()
            runtime.prepare("dismiss that", [ChatMessage("user", "dismiss that")])
            result = runtime.prepare(
                "start my day",
                [ChatMessage("user", "start my day")],
            )

        self.assertEqual(
            result.direct_response,
            "Good morning. Here's your brief:\n"
            "- Later today: start dinner at 06:00 PM",
        )

    def test_runtime_gives_end_my_day_recap_by_voice(self):
        now = datetime(2026, 7, 27, 21, 15, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("pack lunch", now.replace(day=28, hour=9, minute=0))
            runtime.reminders.create("pay bill", now.replace(day=29, hour=10, minute=0))
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "wrap up my day",
                [ChatMessage("user", "wrap up my day")],
            )

        self.assertEqual(
            result.direct_response,
            "Here's your evening recap:\n"
            "- Tomorrow: pack lunch at 09:00 AM\n"
            "- Still open: Follow up on: open roblox",
        )

    def test_runtime_gives_end_my_day_recap_with_quiet_mode(self):
        now = datetime(2026, 7, 27, 21, 15, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

            result = runtime.prepare(
                "wrap up my day",
                [ChatMessage("user", "wrap up my day")],
            )

        self.assertEqual(
            result.direct_response,
            "Here's your evening recap:\n"
            "- Quiet mode: staying quiet until 10:15 PM",
        )

    def test_runtime_resumes_proactive_voice_with_natural_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

            result = runtime.prepare(
                "you don't need to be quiet anymore",
                [ChatMessage("user", "you don't need to be quiet anymore")],
            )

        self.assertEqual(result.direct_response, "I can speak up again.")
        self.assertIsNone(runtime.proactive.active_quiet_until(now))

    def test_runtime_marks_due_attention_item_handled_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "that's handled",
                [ChatMessage("user", "that's handled")],
            )

            due_after = runtime.reminders.due(now)
            unfinished_after = runtime.unfinished_tasks.open()

        self.assertEqual(result.direct_response, "Handled: stretch")
        self.assertEqual(due_after, [])
        self.assertEqual([task.title for task in unfinished_after], ["Follow up on: open roblox"])

    def test_runtime_handles_first_attention_item_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.prepare("what did I miss?", [ChatMessage("user", "what did I miss?")])

            result = runtime.prepare(
                "handle the first one",
                [ChatMessage("user", "handle the first one")],
            )

            due_after = runtime.reminders.due(now)
            unfinished_after = runtime.unfinished_tasks.open()

        self.assertEqual(result.direct_response, "Handled: stretch")
        self.assertEqual(due_after, [])
        self.assertEqual([task.title for task in unfinished_after], ["Follow up on: open roblox"])

    def test_runtime_handles_first_unfinished_followup_when_due_reminder_is_dismissed(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.check_proactive()
            runtime.prepare("dismiss that", [ChatMessage("user", "dismiss that")])

            result = runtime.prepare(
                "take care of the first one",
                [ChatMessage("user", "take care of the first one")],
            )

            due_after = runtime.reminders.due(now)
            unfinished_after = runtime.unfinished_tasks.open()

        self.assertEqual(result.direct_response, "Handled: Follow up on: open roblox")
        self.assertEqual([reminder.message for reminder in due_after], ["stretch"])
        self.assertEqual(unfinished_after, [])

    def test_runtime_handles_unfinished_followup_after_dismissing_due_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            runtime.check_proactive()
            runtime.prepare("dismiss that", [ChatMessage("user", "dismiss that")])
            handled = runtime.prepare("that's handled", [ChatMessage("user", "that's handled")])
            due_after = runtime.reminders.due(now)
            unfinished_after = runtime.unfinished_tasks.open()

        self.assertEqual(handled.direct_response, "Handled: Follow up on: open roblox")
        self.assertEqual([reminder.message for reminder in due_after], ["stretch"])
        self.assertEqual(unfinished_after, [])

    def test_runtime_handles_unfinished_followup_with_took_care_phrase(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            handled = runtime.prepare("I took care of it", [ChatMessage("user", "I took care of it")])
            unfinished_after = runtime.unfinished_tasks.open()

        self.assertEqual(handled.direct_response, "Handled: Follow up on: open roblox")
        self.assertEqual(unfinished_after, [])

    def test_runtime_handles_time_sensitive_note_heads_up_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.note_intents.handle("remember that package arrives today")

            first = runtime.check_proactive()
            handled = runtime.prepare("that's handled", [ChatMessage("user", "that's handled")])
            later = runtime.check_proactive()

        self.assertEqual(first, ["Heads up: package arrives today"])
        self.assertEqual(handled.direct_response, "Handled: package arrives today")
        self.assertEqual(later, [])

    def test_runtime_can_undo_handled_time_sensitive_note_heads_up_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.note_intents.handle("remember that package arrives today")
            runtime.check_proactive()
            runtime.prepare("that's handled", [ChatMessage("user", "that's handled")])

            result = runtime.prepare("undo that", [ChatMessage("user", "undo that")])
            after_undo = runtime.check_proactive()

        self.assertEqual(result.direct_response, "Restored heads up: package arrives today")
        self.assertEqual(after_undo, ["Heads up: package arrives today"])

    def test_runtime_can_undo_handled_due_reminder_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.prepare("that's handled", [ChatMessage("user", "that's handled")])

            result = runtime.prepare(
                "undo that",
                [ChatMessage("user", "undo that")],
            )

            due_after = runtime.reminders.due(now)

        self.assertEqual(result.direct_response, "Restored reminder: stretch")
        self.assertEqual([reminder.message for reminder in due_after], ["stretch"])

    def test_runtime_can_undo_handled_unfinished_followup_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.prepare("that's handled", [ChatMessage("user", "that's handled")])

            result = runtime.prepare(
                "undo that",
                [ChatMessage("user", "undo that")],
            )

            open_after = runtime.unfinished_tasks.open()

        self.assertEqual(result.direct_response, "Restored followup: Follow up on: open roblox")
        self.assertEqual([task.title for task in open_after], ["Follow up on: open roblox"])

    def test_runtime_explains_companion_voice_phrases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "what can I say to you",
                [ChatMessage("user", "what can I say to you")],
            )

        self.assertEqual(
            result.direct_response,
            "You can say things like: start my day, what needs my attention, snooze that, dismiss that, "
            "that's handled, undo that, what are you doing now, be quiet for an hour, "
            "be active and speak up, stop speaking up, are you in quiet mode, you can speak up again, "
            "or wrap up my day.",
        )

    def test_runtime_tailors_voice_help_when_attention_is_waiting(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")

            result = runtime.prepare(
                "what can I say to you",
                [ChatMessage("user", "what can I say to you")],
            )

        self.assertEqual(
            result.direct_response,
            "You can say: what's first, why that first, that's handled, snooze that, dismiss that, "
            "what are you doing now, be active and speak up, stop speaking up, or be quiet for an hour.",
        )

    def test_runtime_answers_presence_check_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "are you there?",
                [ChatMessage("user", "are you there?")],
            )

        self.assertEqual(
            result.direct_response,
            "I am here. Say what needs my attention, what are you doing now, or what can I say to you.",
        )

    def test_runtime_answers_presence_check_with_first_attention_item(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            result = runtime.prepare(
                "are you there?",
                [ChatMessage("user", "are you there?")],
            )

        self.assertEqual(result.direct_response, "I am here. First: stretch")

    def test_runtime_answers_im_back_with_first_attention_item(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            result = runtime.prepare(
                "I'm back",
                [ChatMessage("user", "I'm back")],
            )

        self.assertEqual(result.direct_response, "Welcome back. First: stretch")

    def test_runtime_answers_im_back_when_nothing_is_waiting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "I'm back",
                [ChatMessage("user", "I'm back")],
            )

        self.assertEqual(result.direct_response, "Welcome back. Nothing needs your attention right now.")

    def test_runtime_catches_user_up_on_what_they_missed(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add("Follow up on: open roblox", "The app window did not show the lobby yet.")
            runtime.note_intents.handle("remember that package arrives today")

            result = runtime.prepare(
                "what did I miss?",
                [ChatMessage("user", "what did I miss?")],
            )

        self.assertEqual(
            result.direct_response,
            "While you were away:\n"
            "- Due reminder: stretch\n"
            "- Unfinished followup: Follow up on: open roblox\n"
            "- Heads up: package arrives today",
        )

    def test_runtime_catches_user_up_when_nothing_changed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "what did I miss?",
                [ChatMessage("user", "what did I miss?")],
            )

        self.assertEqual(result.direct_response, "You did not miss anything that needs your attention.")

    def test_runtime_answers_voice_readiness_check_from_provider(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
                voice_status_provider=lambda: "Voice ready: microphone, wake phrase, and speaker are available.",
            )

            result = runtime.prepare(
                "are you ready to listen and talk",
                [ChatMessage("user", "are you ready to listen and talk")],
            )

        self.assertEqual(result.direct_response, "Voice ready: microphone, wake phrase, and speaker are available.")

    def test_runtime_answers_are_you_listening_with_voice_readiness(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
                voice_status_provider=lambda: "Voice ready: microphone, wake phrase, and speaker are available.",
            )

            result = runtime.prepare(
                "are you listening?",
                [ChatMessage("user", "are you listening?")],
            )

        self.assertEqual(result.direct_response, "Voice ready: microphone, wake phrase, and speaker are available.")

    def test_runtime_answers_speak_up_notice_check_with_voice_readiness(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
                voice_status_provider=lambda: (
                    "Voice ready: microphone, wake phrase, and speaker are available. "
                    "Active companion checks on; speak-up notices off."
                ),
            )

            result = runtime.prepare(
                "are you speaking notices aloud?",
                [ChatMessage("user", "are you speaking notices aloud?")],
            )

        self.assertEqual(
            result.direct_response,
            "Voice ready: microphone, wake phrase, and speaker are available. "
            "Active companion checks on; speak-up notices off.",
        )

    def test_runtime_answers_are_you_active_with_voice_readiness(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
                voice_status_provider=lambda: (
                    "Voice status: Microphone ready; Wake phrase on; Voice ready; "
                    "Active companion checks on; speak-up notices on."
                ),
            )

            result = runtime.prepare(
                "are you active?",
                [ChatMessage("user", "are you active?")],
            )

        self.assertEqual(
            result.direct_response,
            "Voice status: Microphone ready; Wake phrase on; Voice ready; "
            "Active companion checks on; speak-up notices on.",
        )

    def test_runtime_answers_active_and_speaking_up_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            runtime = AgentRuntime(
                router=ProviderRouter(load_settings(root / "settings.json")),
                tools=tools,
                audit=AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
                voice_status_provider=lambda: (
                    "Voice status: Microphone ready; Wake phrase on; Voice ready; "
                    "Active companion checks on; speak-up notices on."
                ),
            )

            result = runtime.prepare(
                "are you active and speaking up?",
                [ChatMessage("user", "are you active and speaking up?")],
            )

        self.assertEqual(
            result.direct_response,
            "Voice status: Microphone ready; Wake phrase on; Voice ready; "
            "Active companion checks on; speak-up notices on.",
        )

    def test_runtime_answers_with_me_presence_check_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare(
                "you with me?",
                [ChatMessage("user", "you with me?")],
            )

        self.assertEqual(
            result.direct_response,
            "I am here. Say what needs my attention, what are you doing now, or what can I say to you.",
        )

    def test_runtime_runs_latest_accepted_routine_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "reminders" / "proactive_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "delivered": ["routine:local-time"],
                        "accepted_routines": [{"id": "routine:local-time", "label": "what time is it"}],
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = build_runtime(root)

            with patch.object(runtime.tools.convenience, "local_time", return_value="Local time: Monday at 10:00 AM"):
                result = runtime.prepare("do my saved routine", [ChatMessage("user", "do my saved routine")])

        self.assertEqual(result.direct_response, "Local time: Monday at 10:00 AM")
        self.assertEqual([tool.name for tool in result.tool_results], ["local_time"])

    def test_runtime_runs_latest_accepted_routine_with_natural_phrase(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "reminders" / "proactive_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "delivered": ["routine:local-time"],
                        "accepted_routines": [{"id": "routine:local-time", "label": "what time is it"}],
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = build_runtime(root)

            with patch.object(runtime.tools.convenience, "local_time", return_value="Local time: Monday at 10:00 AM"):
                result = runtime.prepare("run my routine", [ChatMessage("user", "run my routine")])

        self.assertEqual(result.direct_response, "Local time: Monday at 10:00 AM")
        self.assertEqual([tool.name for tool in result.tool_results], ["local_time"])

    def test_runtime_runs_latest_accepted_routine_with_companion_phrase(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "reminders" / "proactive_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "delivered": ["routine:local-time"],
                        "accepted_routines": [{"id": "routine:local-time", "label": "what time is it"}],
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = build_runtime(root)

            with patch.object(runtime.tools.convenience, "local_time", return_value="Local time: Monday at 10:00 AM"):
                result = runtime.prepare("kick off my routine", [ChatMessage("user", "kick off my routine")])

        self.assertEqual(result.direct_response, "Local time: Monday at 10:00 AM")
        self.assertEqual([tool.name for tool in result.tool_results], ["local_time"])

    def test_tool_execution_service_runs_plan_and_logs_audit(self):
        class RecordingAudit:
            def __init__(self) -> None:
                self.events: list[AuditEvent] = []

            def log(self, event: AuditEvent) -> None:
                self.events.append(event)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            audit = RecordingAudit()
            service = ToolExecutionService(tools, audit)
            planned = tools.plan("what time is it")

            with patch.object(tools.convenience, "local_time", return_value="Local time: Monday at 10:00 AM"):
                result = service.execute_one(
                    planned,
                    user_request="what time is it",
                    provider="local",
                    cloud_data_sent=False,
                    outcome="Local time: Monday at 10:00 AM",
                )

        self.assertEqual(result.content, "Local time: Monday at 10:00 AM")
        self.assertEqual(audit.events[0].tools_called, ["local_time"])
        self.assertEqual(audit.events[0].outcome, "Local time: Monday at 10:00 AM")

    def test_tool_execution_service_records_failed_low_risk_action_as_unfinished_task(self):
        class RecordingAudit:
            def __init__(self) -> None:
                self.events: list[AuditEvent] = []

            def log(self, event: AuditEvent) -> None:
                self.events.append(event)

        class FailingTools:
            def execute(self, planned: PlannedTool) -> ToolResult:
                return ToolResult(
                    planned.name,
                    planned.risk,
                    "The app window did not show the expected lobby yet.",
                    executed=False,
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unfinished = UnfinishedTaskStore(root / "tasks" / "unfinished.jsonl")
            service = ToolExecutionService(FailingTools(), RecordingAudit(), unfinished_tasks=unfinished)
            planned = PlannedTool("take_me_to_lobby", RiskLevel.LOW, "Run the last game lobby automation.")

            service.execute_one(
                planned,
                user_request="take me to the lobby",
                provider="local",
                cloud_data_sent=False,
            )

            open_tasks = unfinished.open()

        self.assertEqual([task.title for task in open_tasks], ["Follow up on: take me to the lobby"])
        self.assertEqual([task.detail for task in open_tasks], ["The app window did not show the expected lobby yet."])

    def test_multitask_planner_finds_multiple_low_risk_plans(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({"notepad": ApprovedApp("Notepad", "notepad.exe")}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            planner = MultitaskPlanner(tools)

            plans = planner.plan("open notepad and what time is it")

        self.assertEqual([plan.name for plan in plans], ["open_approved_app", "local_time"])

    def test_routes_existing_tool_fast_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            with patch.object(runtime.tools.convenience, "local_time", return_value="Local time: Monday at 10:00 AM"):
                result = runtime.prepare("what time is it", [ChatMessage("user", "what time is it")])

        self.assertEqual(result.direct_response, "Local time: Monday at 10:00 AM")
        self.assertEqual([tool.name for tool in result.tool_results], ["local_time"])

    def test_runtime_routes_confirmation_prefixed_media_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            with patch.object(runtime.tools.convenience, "media_control", return_value="Media pause.") as media:
                result = runtime.prepare("Yes. And pause my video.", [ChatMessage("user", "Yes. And pause my video.")])

        self.assertEqual(result.direct_response, "Media pause.")
        self.assertEqual([tool.name for tool in result.tool_results], ["media_control"])
        media.assert_called_once_with("pause")

    def test_keeps_plain_conversation_for_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare("tell me a quick joke", [ChatMessage("user", "tell me a quick joke")])

        self.assertIsNone(result.direct_response)
        self.assertEqual(result.messages[-1], ChatMessage("user", "tell me a quick joke"))


if __name__ == "__main__":
    unittest.main()
