import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis_assistant.agent.reminders import ReminderIntentHandler, ReminderStore, parse_reminder
from jarvis_assistant.ai import ChatMessage

from tests.test_agent_runtime import build_runtime


class AgentReminderTests(unittest.TestCase):
    def test_parse_relative_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me in 20 minutes to check the oven", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, now + timedelta(minutes=20))

    def test_parse_trailing_relative_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me to check the oven in 20 minutes", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, now + timedelta(minutes=20))

    def test_parse_tomorrow_morning_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me tomorrow morning to check the oven", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc))

    def test_parse_trailing_tomorrow_morning_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me to check the oven tomorrow morning", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc))

    def test_parse_trailing_tomorrow_at_time_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me to check the oven tomorrow at 9 AM", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc))

    def test_parse_tonight_reminder_uses_this_evening_when_future(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me tonight to check the oven", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, datetime(2026, 7, 27, 20, 0, tzinfo=timezone.utc))

    def test_parse_tonight_reminder_rolls_forward_when_past(self):
        now = datetime(2026, 7, 27, 21, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me tonight to check the oven", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, datetime(2026, 7, 28, 20, 0, tzinfo=timezone.utc))

    def test_parse_this_evening_reminder_uses_today_when_future(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me this evening to check the oven", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, datetime(2026, 7, 27, 18, 0, tzinfo=timezone.utc))

    def test_parse_this_evening_reminder_rolls_forward_when_past(self):
        now = datetime(2026, 7, 27, 19, 0, tzinfo=timezone.utc)

        parsed = parse_reminder("remind me this evening to check the oven", now)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "check the oven")
        self.assertEqual(parsed.due_at, datetime(2026, 7, 28, 18, 0, tzinfo=timezone.utc))

    def test_reminder_intent_handler_asks_and_accepts_short_followup(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ReminderStore(Path(temp_dir) / "reminders.jsonl")
            handler = ReminderIntentHandler(store, now=lambda: now)

            asked = handler.handle("remind me to check the oven")
            created = handler.handle("in 20 minutes")
            pending = store.pending(now)

        self.assertIn("When should I remind you", asked)
        self.assertIn("Reminder set", created)
        self.assertEqual([reminder.message for reminder in pending], ["check the oven"])

    def test_agent_runtime_creates_lists_and_completes_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            created = runtime.prepare(
                "remind me in 20 minutes to stretch",
                [ChatMessage("user", "remind me in 20 minutes to stretch")],
            )
            listed = runtime.prepare("list reminders", [ChatMessage("user", "list reminders")])
            completed = runtime.prepare("complete reminder 1", [ChatMessage("user", "complete reminder 1")])

        self.assertIn("Reminder set", created.direct_response)
        self.assertIn("stretch", listed.direct_response)
        self.assertIn("Completed reminder", completed.direct_response)

    def test_agent_runtime_creates_reminder_with_wake_name_prefix(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            created = runtime.prepare(
                "Damien, remind me in 20 minutes to stretch",
                [ChatMessage("user", "Damien, remind me in 20 minutes to stretch")],
            )
            pending = runtime.reminders.pending(now)

        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["stretch"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_creates_reminder_with_polite_wake_prefix(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            created = runtime.prepare(
                "Hey Damien, please remind me in 20 minutes to stretch",
                [ChatMessage("user", "Hey Damien, please remind me in 20 minutes to stretch")],
            )
            pending = runtime.reminders.pending(now)

        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["stretch"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_creates_reminder_with_would_you_mind_request(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            created = runtime.prepare(
                "would you mind reminding me in 20 minutes to stretch",
                [ChatMessage("user", "would you mind reminding me in 20 minutes to stretch")],
            )
            pending = runtime.reminders.pending(now)

        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["stretch"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_creates_reminder_with_natural_tell_me_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            created = runtime.prepare(
                "tell me in 20 minutes to stretch",
                [ChatMessage("user", "tell me in 20 minutes to stretch")],
            )
            pending = runtime.reminders.pending(now)

        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["stretch"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_creates_reminder_with_nudge_phrase(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            created = runtime.prepare(
                "give me a nudge in 20 minutes to stretch",
                [ChatMessage("user", "give me a nudge in 20 minutes to stretch")],
            )
            pending = runtime.reminders.pending(now)

        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["stretch"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_can_dismiss_current_due_reminder_without_number(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now
            runtime.reminders.create("stretch", now - timedelta(minutes=1))
            runtime.reminders.create("drink water", now + timedelta(minutes=10))

            dismissed = runtime.prepare(
                "dismiss that reminder",
                [ChatMessage("user", "dismiss that reminder")],
            )
            pending = runtime.reminders.pending(now)

        self.assertIn("Completed reminder: stretch", dismissed.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["drink water"])

    def test_reminder_like_command_without_time_asks_followup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            result = runtime.prepare("remind me to check the oven", [ChatMessage("user", "remind me to check the oven")])

        self.assertIn("When should I remind you", result.direct_response)

    def test_agent_runtime_uses_short_followup_to_schedule_pending_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            asked = runtime.prepare(
                "remind me to check the oven",
                [ChatMessage("user", "remind me to check the oven")],
            )
            created = runtime.prepare("in 20 minutes", [ChatMessage("user", "in 20 minutes")])
            pending = runtime.reminders.pending(now)

        self.assertIn("When should I remind you", asked.direct_response)
        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["check the oven"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_uses_give_me_followup_to_schedule_pending_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            asked = runtime.prepare(
                "remind me to check the oven",
                [ChatMessage("user", "remind me to check the oven")],
            )
            created = runtime.prepare("give me 20 minutes", [ChatMessage("user", "give me 20 minutes")])
            pending = runtime.reminders.pending(now)

        self.assertIn("When should I remind you", asked.direct_response)
        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["check the oven"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_uses_polite_followup_to_schedule_pending_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            asked = runtime.prepare(
                "remind me to check the oven",
                [ChatMessage("user", "remind me to check the oven")],
            )
            created = runtime.prepare("in 20 minutes please", [ChatMessage("user", "in 20 minutes please")])
            pending = runtime.reminders.pending(now)

        self.assertIn("When should I remind you", asked.direct_response)
        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["check the oven"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_uses_from_now_followup_to_schedule_pending_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            asked = runtime.prepare(
                "remind me to check the oven",
                [ChatMessage("user", "remind me to check the oven")],
            )
            created = runtime.prepare("20 minutes from now", [ChatMessage("user", "20 minutes from now")])
            pending = runtime.reminders.pending(now)

        self.assertIn("When should I remind you", asked.direct_response)
        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["check the oven"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), now + timedelta(minutes=20))

    def test_agent_runtime_uses_tomorrow_time_followup_to_schedule_pending_reminder(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))
            runtime.now = lambda: now

            asked = runtime.prepare(
                "remind me to check the oven",
                [ChatMessage("user", "remind me to check the oven")],
            )
            created = runtime.prepare("at 9 AM tomorrow", [ChatMessage("user", "at 9 AM tomorrow")])
            pending = runtime.reminders.pending(now)

        self.assertIn("When should I remind you", asked.direct_response)
        self.assertIsNotNone(created.direct_response)
        self.assertIn("Reminder set", created.direct_response)
        self.assertEqual([reminder.message for reminder in pending], ["check the oven"])
        self.assertEqual(datetime.fromisoformat(pending[0].due_at), datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc))

    def test_agent_runtime_can_cancel_pending_reminder_followup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            asked = runtime.prepare(
                "remind me to check the oven",
                [ChatMessage("user", "remind me to check the oven")],
            )
            canceled = runtime.prepare("never mind", [ChatMessage("user", "never mind")])
            later = runtime.prepare("in 20 minutes", [ChatMessage("user", "in 20 minutes")])

        self.assertIn("When should I remind you", asked.direct_response)
        self.assertIsNotNone(canceled.direct_response)
        self.assertIn("Canceled", canceled.direct_response)
        self.assertIsNone(later.direct_response)

    def test_reminder_store_due_returns_pending_due_records(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ReminderStore(Path(temp_dir) / "reminders.jsonl")
            store.create("stretch", now - timedelta(minutes=1))
            store.create("drink water", now + timedelta(minutes=10))

            due = store.due(now)

        self.assertEqual([reminder.message for reminder in due], ["stretch"])


if __name__ == "__main__":
    unittest.main()
