import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis_assistant.agent.notes import NoteStore
from jarvis_assistant.agent.proactive import ProactiveControlHandler, ProactiveEngine, UnfinishedTaskStore
from jarvis_assistant.agent.reminders import ReminderStore
from jarvis_assistant.ai import ChatMessage
from jarvis_assistant.improvement import ImprovementQueue, SelfRepairManager

from tests.test_agent_runtime import build_runtime


class AgentProactiveTests(unittest.TestCase):
    def test_proactive_engine_surfaces_due_reminder_once(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reminders = ReminderStore(root / "reminders.jsonl")
            reminders.create("stretch", now)
            engine = ProactiveEngine(reminders=reminders, state_path=root / "proactive.json")

            first = engine.check(now)
            second = engine.check(now)

        self.assertEqual([notice.message for notice in first], ["Reminder: stretch"])
        self.assertEqual(second, [])

    def test_proactive_engine_respects_notice_guardrail_without_marking_delivered(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        allow_notices = False
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reminders = ReminderStore(root / "reminders.jsonl")
            reminders.create("stretch", now)

            def notice_allowed(_notice):
                return allow_notices

            engine = ProactiveEngine(
                reminders=reminders,
                state_path=root / "proactive.json",
                notice_allowed=notice_allowed,
            )

            blocked = engine.check(now)
            allow_notices = True
            allowed = engine.check(now)
            repeated = engine.check(now)

        self.assertEqual(blocked, [])
        self.assertEqual([notice.message for notice in allowed], ["Reminder: stretch"])
        self.assertEqual(repeated, [])

    def test_proactive_engine_surfaces_upgrade_opportunity_once(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reminders = ReminderStore(root / "reminders.jsonl")
            improvements = ImprovementQueue(root)
            improvements.log(
                request="open the smart lights",
                reason="Damien does not have a smart-home connector yet.",
                suggestion="Add a smart-home device connector.",
            )
            engine = ProactiveEngine(
                reminders=reminders,
                state_path=root / "proactive.json",
                improvements=improvements,
            )

            first = engine.check(now)
            second = engine.check(now)

        self.assertEqual(
            [notice.message for notice in first],
            ["Opportunity: Add a smart-home device connector."],
        )
        self.assertEqual(second, [])

    def test_agent_runtime_can_snooze_upgrade_opportunity_with_not_now(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.improvement_queue.log(
                request="open the smart lights",
                reason="Damien does not have a smart-home connector yet.",
                suggestion="Add a smart-home device connector.",
            )

            first = runtime.check_proactive()
            snoozed = runtime.prepare("not now", [ChatMessage("user", "not now")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Opportunity: Add a smart-home device connector."])
        self.assertEqual(snoozed.direct_response, "I will remind you later.")
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_proactive_engine_surfaces_started_repair_once(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reminders = ReminderStore(root / "reminders.jsonl")
            repair_manager = SelfRepairManager(root, runner=lambda command, cwd, transcript: None)
            improvements = ImprovementQueue(root, repair_manager=repair_manager)
            improvements.log(
                request="Damien should operate this app for me",
                reason="No safe UI automation tool exists.",
                suggestion="Add a safe UI automation tool.",
            )
            engine = ProactiveEngine(
                reminders=reminders,
                state_path=root / "proactive.json",
                improvements=improvements,
            )

            first = engine.check(now)
            second = engine.check(now)

        self.assertEqual(
            [notice.message for notice in first],
            ["Repair started: Add a safe UI automation tool."],
        )
        self.assertEqual([notice.reason for notice in first], ["self_repair_started"])
        self.assertEqual(second, [])

    def test_proactive_engine_surfaces_finished_repair_once(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reminders = ReminderStore(root / "reminders.jsonl")
            repair_manager = SelfRepairManager(root, runner=lambda command, cwd, transcript: None)
            improvements = ImprovementQueue(root, repair_manager=repair_manager)
            improvements.log(
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
                "- Change: Damien now treats a matching visible game window as a successful handoff.\n"
                "- Verification: full test suite passed.\n",
                encoding="utf-8",
            )
            engine = ProactiveEngine(
                reminders=reminders,
                state_path=root / "proactive.json",
                improvements=improvements,
            )

            first = engine.check(now)
            second = engine.check(now)

        self.assertEqual(
            [notice.message for notice in first],
            ["Repair finished: Damien now treats a matching visible game window as a successful handoff."],
        )
        self.assertEqual([notice.reason for notice in first], ["self_repair_finished"])
        self.assertEqual(second, [])

    def test_proactive_engine_surfaces_finished_repair_after_started_notice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reminders = ReminderStore(root / "reminders.jsonl")
            repair_manager = SelfRepairManager(root, runner=lambda command, cwd, transcript: None)
            improvements = ImprovementQueue(root, repair_manager=repair_manager)
            improvements.log(
                request="Take Apex Legends to lobby",
                reason="Could not confirm lobby status.",
                suggestion="Improve game lobby status detection for Apex Legends.",
            )
            engine = ProactiveEngine(
                reminders=reminders,
                state_path=root / "proactive.json",
                improvements=improvements,
            )
            started = engine.check(now)
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

            finished = engine.check(now + timedelta(minutes=1))
            repeated = engine.check(now + timedelta(minutes=2))

        self.assertEqual([notice.reason for notice in started], ["self_repair_started"])
        self.assertEqual(
            [notice.message for notice in finished],
            ["Repair finished: Damien now treats a matching visible game window as a successful handoff."],
        )
        self.assertEqual([notice.reason for notice in finished], ["self_repair_finished"])
        self.assertEqual(repeated, [])

    def test_proactive_engine_surfaces_unfinished_task_once(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reminders = ReminderStore(root / "reminders.jsonl")
            tasks = UnfinishedTaskStore(root / "tasks" / "unfinished.jsonl")
            tasks.add("Finish setting up the Discord call", "Waiting for the voice channel to connect.")
            engine = ProactiveEngine(
                reminders=reminders,
                state_path=root / "proactive.json",
                unfinished_tasks=tasks,
            )

            first = engine.check(now)
            second = engine.check(now)

        self.assertEqual(
            [notice.message for notice in first],
            ["Unfinished: Finish setting up the Discord call - Waiting for the voice channel to connect."],
        )
        self.assertEqual([notice.reason for notice in first], ["unfinished_task"])
        self.assertEqual(second, [])

    def test_proactive_engine_surfaces_time_sensitive_saved_note_once(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes = NoteStore(root / "notes.jsonl")
            notes.add("package arrives today")
            notes.add("garage remote is in my backpack")
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
                notes=notes,
            )

            first = engine.check(now)
            second = engine.check(now)

        self.assertEqual([notice.message for notice in first], ["Heads up: package arrives today"])
        self.assertEqual([notice.reason for notice in first], ["saved_note_opportunity"])
        self.assertEqual(second, [])

    def test_proactive_engine_surfaces_repeated_routine_once_from_audit_history(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audit_path = root / "logs" / "audit.jsonl"
            audit_path.parent.mkdir(parents=True)
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
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
                audit_path=audit_path,
            )

            first = engine.check(now)
            second = engine.check(now)

        self.assertEqual(
            [notice.message for notice in first],
            ["Routine: You often ask me to open roblox and start my lobby. I can help make that quicker."],
        )
        self.assertEqual([notice.reason for notice in first], ["repeated_routine"])
        self.assertEqual(second, [])

    def test_unfinished_task_store_can_complete_latest_open_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks = UnfinishedTaskStore(root / "tasks" / "unfinished.jsonl")
            tasks.add("Finish setting up the Discord call", "Waiting for the voice channel to connect.")

            completed = tasks.complete_latest()

        self.assertIsNotNone(completed)
        self.assertEqual(completed.title, "Finish setting up the Discord call")
        self.assertEqual(tasks.open(), [])

    def test_unfinished_task_store_reuses_matching_open_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tasks = UnfinishedTaskStore(root / "tasks" / "unfinished.jsonl")

            first = tasks.add("Follow up on: take me to the lobby", "The lobby did not appear yet.")
            second = tasks.add("Follow up on: take me to the lobby", "The lobby did not appear yet.")

            open_tasks = tasks.open()

        self.assertEqual(first.id, second.id)
        self.assertEqual([task.title for task in open_tasks], ["Follow up on: take me to the lobby"])

    def test_agent_runtime_can_clear_latest_unfinished_task(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.unfinished_tasks.add(
                "Finish setting up the Discord call",
                "Waiting for the voice channel to connect.",
            )

            cleared = runtime.prepare(
                "clear that unfinished task",
                [ChatMessage("user", "clear that unfinished task")],
            )
            notices = runtime.check_proactive()

        self.assertIn("Cleared unfinished task", cleared.direct_response)
        self.assertEqual(notices, [])

    def test_agent_runtime_can_list_unfinished_tasks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.unfinished_tasks.add(
                "Follow up on: take me to the lobby",
                "The app window did not show the expected lobby yet.",
            )

            result = runtime.prepare(
                "what is unfinished",
                [ChatMessage("user", "what is unfinished")],
            )

        self.assertIn("Unfinished tasks:", result.direct_response)
        self.assertIn("1. Follow up on: take me to the lobby - The app window did not show", result.direct_response)

    def test_agent_runtime_speaks_up_for_time_sensitive_saved_note(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            saved = runtime.prepare(
                "remember that package arrives today",
                [ChatMessage("user", "remember that package arrives today")],
            )
            notices = runtime.check_proactive()
            later = runtime.check_proactive()

        self.assertEqual(saved.direct_response, "Saved note: package arrives today")
        self.assertEqual(notices, ["Heads up: package arrives today"])
        self.assertEqual(later, [])

    def test_agent_runtime_can_snooze_time_sensitive_saved_note_heads_up(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.prepare(
                "remember that package arrives today",
                [ChatMessage("user", "remember that package arrives today")],
            )

            first = runtime.check_proactive()
            snoozed = runtime.prepare("not now", [ChatMessage("user", "not now")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Heads up: package arrives today"])
        self.assertEqual(snoozed.direct_response, "I will remind you later.")
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, ["Heads up: package arrives today"])

    def test_agent_runtime_can_snooze_note_heads_up_with_about_that_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.prepare(
                "remember that package arrives today",
                [ChatMessage("user", "remember that package arrives today")],
            )

            first = runtime.check_proactive()
            snoozed = runtime.prepare(
                "remind me about that in 10 minutes",
                [ChatMessage("user", "remind me about that in 10 minutes")],
            )
            runtime.now = lambda: now + timedelta(minutes=9)
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=11)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Heads up: package arrives today"])
        self.assertEqual(snoozed.direct_response, "I will remind you in 10 minutes.")
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, ["Heads up: package arrives today"])

    def test_agent_runtime_can_snooze_note_heads_up_with_about_that_later(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.prepare(
                "remember that package arrives today",
                [ChatMessage("user", "remember that package arrives today")],
            )

            first = runtime.check_proactive()
            snoozed = runtime.prepare(
                "remind me about that later",
                [ChatMessage("user", "remind me about that later")],
            )
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Heads up: package arrives today"])
        self.assertEqual(snoozed.direct_response, "I will remind you later.")
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, ["Heads up: package arrives today"])

    def test_agent_runtime_can_dismiss_time_sensitive_saved_note_heads_up(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.prepare(
                "remember that package arrives today",
                [ChatMessage("user", "remember that package arrives today")],
            )

            first = runtime.check_proactive()
            dismissed = runtime.prepare("dismiss that", [ChatMessage("user", "dismiss that")])
            later = runtime.check_proactive()

        self.assertEqual(first, ["Heads up: package arrives today"])
        self.assertEqual(dismissed.direct_response, "Dismissed that.")
        self.assertEqual(later, [])

    def test_agent_runtime_can_stop_reminding_about_latest_unfinished_task_without_completing_it(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.unfinished_tasks.add(
                "Follow up on: take me to the lobby",
                "The app window did not show the expected lobby yet.",
            )

            first = runtime.check_proactive()
            stopped = runtime.prepare(
                "stop reminding me about that",
                [ChatMessage("user", "stop reminding me about that")],
            )
            later = runtime.check_proactive()
            open_tasks = runtime.unfinished_tasks.open()

        self.assertEqual(len(first), 1)
        self.assertIn("I will stop reminding you about that", stopped.direct_response)
        self.assertEqual(later, [])
        self.assertEqual([task.title for task in open_tasks], ["Follow up on: take me to the lobby"])

    def test_agent_runtime_can_stop_reminding_about_due_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            stopped = runtime.prepare(
                "stop reminding me about that",
                [ChatMessage("user", "stop reminding me about that")],
            )
            later = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIn("I will stop reminding you about that", stopped.direct_response)
        self.assertEqual(later, [])

    def test_agent_runtime_can_dismiss_active_due_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            dismissed = runtime.prepare("dismiss that", [ChatMessage("user", "dismiss that")])
            later = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIsNotNone(dismissed.direct_response)
        self.assertIn("Dismissed", dismissed.direct_response)
        self.assertEqual(later, [])

    def test_agent_runtime_can_drop_active_due_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            dismissed = runtime.prepare("drop it", [ChatMessage("user", "drop it")])
            later = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIsNotNone(dismissed.direct_response)
        self.assertIn("Dismissed", dismissed.direct_response)
        self.assertEqual(later, [])

    def test_agent_runtime_can_snooze_latest_unfinished_notice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.unfinished_tasks.add(
                "Follow up on: take me to the lobby",
                "The app window did not show the expected lobby yet.",
            )

            first = runtime.check_proactive()
            snoozed = runtime.prepare("not now", [ChatMessage("user", "not now")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(len(first), 1)
        self.assertIn("I will remind you later", snoozed.direct_response)
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_agent_runtime_snoozes_unfinished_notice_after_due_reminder_is_dismissed(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)
            runtime.unfinished_tasks.add(
                "Follow up on: take me to the lobby",
                "The app window did not show the expected lobby yet.",
            )

            first = runtime.check_proactive()
            dismissed = runtime.prepare("dismiss that", [ChatMessage("user", "dismiss that")])
            snoozed = runtime.prepare("not now", [ChatMessage("user", "not now")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first[0], "Reminder: stretch")
        self.assertEqual(dismissed.direct_response, "Dismissed that.")
        self.assertEqual(snoozed.direct_response, "I will remind you later.")
        self.assertEqual(during_snooze, [])
        self.assertIn("Unfinished: Follow up on: take me to the lobby", after_snooze[0])

    def test_agent_runtime_can_snooze_latest_unfinished_notice_for_custom_minutes(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.unfinished_tasks.add(
                "Follow up on: take me to the lobby",
                "The app window did not show the expected lobby yet.",
            )

            first = runtime.check_proactive()
            snoozed = runtime.prepare("remind me in 10 minutes", [ChatMessage("user", "remind me in 10 minutes")])
            runtime.now = lambda: now + timedelta(minutes=9)
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=11)
            after_snooze = runtime.check_proactive()

        self.assertEqual(len(first), 1)
        self.assertIn("I will remind you in 10 minutes", snoozed.direct_response)
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_agent_runtime_can_snooze_due_reminder_for_custom_minutes(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            snoozed = runtime.prepare("remind me in 10 minutes", [ChatMessage("user", "remind me in 10 minutes")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=11)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIn("I will remind you in 10 minutes", snoozed.direct_response)
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_agent_runtime_can_snooze_due_reminder_with_not_now(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            snoozed = runtime.prepare("not now", [ChatMessage("user", "not now")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIsNotNone(snoozed.direct_response)
        self.assertIn("I will remind you later", snoozed.direct_response)
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_agent_runtime_can_snooze_due_reminder_with_give_me_a_bit(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            snoozed = runtime.prepare("give me a bit", [ChatMessage("user", "give me a bit")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIsNotNone(snoozed.direct_response)
        self.assertIn("I will remind you later", snoozed.direct_response)
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_agent_runtime_can_snooze_due_reminder_with_snooze_that(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            snoozed = runtime.prepare("snooze that", [ChatMessage("user", "snooze that")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIsNotNone(snoozed.direct_response)
        self.assertIn("I will remind you later", snoozed.direct_response)
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_agent_runtime_can_snooze_due_reminder_with_snooze_this(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now)

            first = runtime.check_proactive()
            snoozed = runtime.prepare("snooze this", [ChatMessage("user", "snooze this")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertIsNotNone(snoozed.direct_response)
        self.assertIn("I will remind you later", snoozed.direct_response)
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_proactive_control_handler_can_pause_notices(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("be quiet for an hour")

        self.assertIn("quiet for an hour", result.lower())

    def test_proactive_control_handler_can_hold_off_for_a_bit(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("hold off for a bit")
            quiet_until = engine.active_quiet_until(now)

        self.assertEqual(result, "I will stay quiet for 30 minutes.")
        self.assertEqual(quiet_until, now + timedelta(minutes=30))

    def test_proactive_control_handler_can_give_space_for_a_bit(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("give me some space for a bit")
            quiet_until = engine.active_quiet_until(now)

        self.assertEqual(result, "I will stay quiet for 30 minutes.")
        self.assertEqual(quiet_until, now + timedelta(minutes=30))

    def test_proactive_control_handler_can_hold_off_for_minutes(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("hold off for 10 minutes")
            quiet_until = engine.active_quiet_until(now)

        self.assertEqual(result, "I will stay quiet for 10 minutes.")
        self.assertEqual(quiet_until, now + timedelta(minutes=10))

    def test_proactive_control_handler_can_hold_off_as_request_for_minutes(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("can you hold off for 10 minutes")
            quiet_until = engine.active_quiet_until(now)

        self.assertEqual(result, "I will stay quiet for 10 minutes.")
        self.assertEqual(quiet_until, now + timedelta(minutes=10))

    def test_proactive_control_handler_can_give_space_for_minutes(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("give me some space for 10 minutes")
            quiet_until = engine.active_quiet_until(now)

        self.assertEqual(result, "I will stay quiet for 10 minutes.")
        self.assertEqual(quiet_until, now + timedelta(minutes=10))

    def test_proactive_control_handler_can_give_space_as_request_for_minutes(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("can you give me some space for 10 minutes")
            quiet_until = engine.active_quiet_until(now)

        self.assertEqual(result, "I will stay quiet for 10 minutes.")
        self.assertEqual(quiet_until, now + timedelta(minutes=10))

    def test_proactive_control_handler_can_resume_notices_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)
            handler.handle("be quiet for an hour")

            result = handler.handle("you can speak up again")
            state = json.loads((root / "proactive.json").read_text(encoding="utf-8"))

        self.assertEqual(result, "I can speak up again.")
        self.assertEqual(state.get("quiet_until"), "")

    def test_proactive_control_handler_reports_ready_to_speak_up(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("are you in quiet mode")

        self.assertEqual(result, "I am ready to speak up.")

    def test_proactive_control_handler_reports_watching_out_when_ready(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)

            result = handler.handle("are you watching out for me")

        self.assertEqual(result, "I am ready to speak up.")

    def test_proactive_control_handler_reports_current_quiet_mode(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)
            handler.handle("be quiet for an hour")

            result = handler.handle("can you speak up")

        self.assertEqual(result, "I am staying quiet until 01:00 PM.")

    def test_proactive_control_handler_reports_watching_out_while_quiet(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = ProactiveEngine(
                reminders=ReminderStore(root / "reminders.jsonl"),
                state_path=root / "proactive.json",
            )
            handler = ProactiveControlHandler(engine, now=lambda: now)
            handler.handle("be quiet for an hour")

            result = handler.handle("are you watching out for me")

        self.assertEqual(result, "I am staying quiet until 01:00 PM.")

    def test_agent_runtime_can_pause_proactive_suggestions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

        self.assertIn("quiet for an hour", result.direct_response.lower())

    def test_agent_runtime_can_resume_proactive_suggestions_by_voice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

            result = runtime.prepare(
                "you can speak up again",
                [ChatMessage("user", "you can speak up again")],
            )

        self.assertEqual(result.direct_response, "I can speak up again.")

    def test_agent_runtime_can_report_quiet_mode_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.prepare("be quiet for an hour", [ChatMessage("user", "be quiet for an hour")])

            result = runtime.prepare(
                "are you in quiet mode",
                [ChatMessage("user", "are you in quiet mode")],
            )

        self.assertEqual(result.direct_response, "I am staying quiet until 01:00 PM.")

    def test_agent_runtime_can_report_watching_out_by_voice(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            result = runtime.prepare(
                "are you watching out for me",
                [ChatMessage("user", "are you watching out for me")],
            )

        self.assertEqual(result.direct_response, "I am ready to speak up.")

    def test_agent_runtime_can_dismiss_latest_upgrade_opportunity(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.improvement_queue.log(
                request="control the lights",
                reason="No smart-home connector exists.",
                suggestion="Add a smart-home connector.",
            )

            dismissed = runtime.prepare(
                "dismiss that upgrade opportunity",
                [ChatMessage("user", "dismiss that upgrade opportunity")],
            )
            notices = runtime.check_proactive()

        self.assertIn("dismissed", dismissed.direct_response.lower())
        self.assertEqual(notices, [])

    def test_agent_runtime_can_stop_suggesting_latest_upgrade_opportunity(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = build_runtime(root)
            runtime.now = lambda: now
            runtime.improvement_queue.log(
                request="control the lights",
                reason="No smart-home connector exists.",
                suggestion="Add a smart-home connector.",
            )

            stopped = runtime.prepare(
                "stop suggesting that",
                [ChatMessage("user", "stop suggesting that")],
            )
            notices = runtime.check_proactive()

        self.assertIn("I will stop suggesting that", stopped.direct_response)
        self.assertEqual(notices, [])

    def test_agent_runtime_can_accept_latest_routine_suggestion(self):
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
            runtime.check_proactive()

            accepted = runtime.prepare(
                "yes make that quicker",
                [ChatMessage("user", "yes make that quicker")],
            )
            state = json.loads((root / "reminders" / "proactive_state.json").read_text(encoding="utf-8"))

        self.assertIn("I will remember that routine", accepted.direct_response)
        self.assertEqual(
            state["accepted_routines"],
            [{"id": state["delivered"][0], "label": "open roblox and start my lobby"}],
        )

    def test_agent_runtime_can_dismiss_latest_routine_suggestion_with_that(self):
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
            runtime.check_proactive()

            dismissed = runtime.prepare(
                "dismiss that",
                [ChatMessage("user", "dismiss that")],
            )

        self.assertEqual(dismissed.direct_response, "Dismissed that.")

    def test_agent_runtime_can_snooze_latest_routine_suggestion_with_not_now(self):
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

            first = runtime.check_proactive()
            snoozed = runtime.prepare("not now", [ChatMessage("user", "not now")])
            during_snooze = runtime.check_proactive()
            runtime.now = lambda: now + timedelta(minutes=31)
            after_snooze = runtime.check_proactive()

        self.assertEqual(
            first,
            ["Routine: You often ask me to open roblox and start my lobby. I can help make that quicker."],
        )
        self.assertEqual(snoozed.direct_response, "I will remind you later.")
        self.assertEqual(during_snooze, [])
        self.assertEqual(after_snooze, first)

    def test_agent_runtime_can_stop_suggesting_latest_routine(self):
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

            first = runtime.check_proactive()
            stopped = runtime.prepare(
                "stop suggesting that",
                [ChatMessage("user", "stop suggesting that")],
            )
            later = runtime.check_proactive()

        self.assertEqual(
            first,
            ["Routine: You often ask me to open roblox and start my lobby. I can help make that quicker."],
        )
        self.assertEqual(stopped.direct_response, "I will stop suggesting that.")
        self.assertEqual(later, [])

    def test_agent_runtime_can_list_accepted_routines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "reminders" / "proactive_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "delivered": ["routine:lobby"],
                        "accepted_routines": [{"id": "routine:lobby", "label": "open roblox and start my lobby"}],
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = build_runtime(root)

            result = runtime.prepare(
                "what routines do you remember",
                [ChatMessage("user", "what routines do you remember")],
            )

        self.assertEqual(result.direct_response, "Saved routines:\n1. open roblox and start my lobby")

    def test_agent_runtime_can_forget_saved_routine_by_number(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_path = root / "reminders" / "proactive_state.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "delivered": ["routine:lobby", "routine:time"],
                        "accepted_routines": [
                            {"id": "routine:lobby", "label": "open roblox and start my lobby"},
                            {"id": "routine:time", "label": "what time is it"},
                        ],
                    },
                    ensure_ascii=True,
                )
                + "\n",
                encoding="utf-8",
            )
            runtime = build_runtime(root)

            forgotten = runtime.prepare(
                "forget saved routine 1",
                [ChatMessage("user", "forget saved routine 1")],
            )
            listed = runtime.prepare(
                "list saved routines",
                [ChatMessage("user", "list saved routines")],
            )

        self.assertEqual(forgotten.direct_response, "Forgot saved routine: open roblox and start my lobby")
        self.assertEqual(listed.direct_response, "Saved routines:\n1. what time is it")


if __name__ == "__main__":
    unittest.main()
