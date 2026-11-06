import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jarvis_assistant.app_conversation_control import ConversationController, no_visible_text_fallback


class FakeStatus:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class FakeBool:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value

    def set(self, value: bool) -> None:
        self.value = value


class FakeHistory:
    def __init__(self) -> None:
        self.users: list[str] = []

    def add_user(self, text: str) -> None:
        self.users.append(text)


class FakeEvents:
    def __init__(self) -> None:
        self.items: list[tuple[str, object]] = []

    def put(self, item: tuple[str, object]) -> None:
        self.items.append(item)


class FakeConversationApp:
    def __init__(self, proactive_enabled: bool = False, proactive_voice_enabled: bool = False) -> None:
        self.settings = SimpleNamespace(
            proactive_enabled=proactive_enabled,
            proactive_voice_enabled=proactive_voice_enabled,
        )
        self.proactive_enabled = FakeBool(proactive_enabled)
        self.proactive_voice_enabled = FakeBool(proactive_voice_enabled)
        self.proactive_summary = FakeStatus()
        self.status = FakeStatus()
        self.history = FakeHistory()
        self.events = FakeEvents()
        self.lines: list[tuple[str, str]] = []
        self.stopped_speaking = False
        self.streaming_speech_started = False
        self.proactive_loop_started = False
        self.proactive_loop = None
        self.responded_texts: list[str] = []

    def _stop_speaking(self) -> None:
        self.stopped_speaking = True

    def _append_line(self, speaker: str, text: str) -> None:
        self.lines.append((speaker, text))

    def _start_streaming_speech(self) -> None:
        self.streaming_speech_started = True

    def _start_proactive_loop(self) -> None:
        if self.settings.proactive_enabled:
            self.proactive_loop_started = True

    def _respond(self, text: str) -> None:
        self.responded_texts.append(text)


class StoppableLoop:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class NoopThread:
    def __init__(self, target, args=(), daemon=False) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        pass


class AppConversationControlTests(unittest.TestCase):
    def test_no_visible_text_fallback_keeps_recovery_guidance(self):
        self.assertEqual(
            no_visible_text_fallback(),
            "I reached the local model, but it did not return any visible text. Try again or switch local models in Settings.",
        )

    def test_handle_user_text_turns_on_active_spoken_notices_by_voice(self):
        app = FakeConversationApp()

        with (
            patch("jarvis_assistant.app_conversation_control.threading.Thread", NoopThread),
            patch("jarvis_assistant.config.update_settings") as update_settings,
        ):
            ConversationController(app).handle_user_text("Damien, be active and speak up")

        update_settings.assert_called_once_with({"proactive_enabled": True, "proactive_voice_enabled": True})
        self.assertTrue(app.proactive_enabled.get())
        self.assertTrue(app.proactive_voice_enabled.get())
        self.assertTrue(app.settings.proactive_enabled)
        self.assertTrue(app.settings.proactive_voice_enabled)
        self.assertTrue(app.proactive_loop_started)
        self.assertEqual(app.proactive_summary.value, "Active companion checks on; speak-up notices on")
        self.assertEqual(app.events.items, [("stream_text", "Active companion mode is on. I will watch and speak up."), ("done", None)])
        self.assertEqual(app.history.users, ["Damien, be active and speak up"])

    def test_handle_user_text_accepts_short_active_and_speak_up_phrase(self):
        app = FakeConversationApp()

        with (
            patch("jarvis_assistant.app_conversation_control.threading.Thread", NoopThread),
            patch("jarvis_assistant.config.update_settings") as update_settings,
        ):
            ConversationController(app).handle_user_text("Damien, active and speak up")

        update_settings.assert_called_once_with({"proactive_enabled": True, "proactive_voice_enabled": True})
        self.assertTrue(app.proactive_enabled.get())
        self.assertTrue(app.proactive_voice_enabled.get())
        self.assertEqual(app.responded_texts, [])
        self.assertEqual(app.events.items, [("stream_text", "Active companion mode is on. I will watch and speak up."), ("done", None)])

    def test_handle_remote_user_text_turns_on_active_spoken_notices(self):
        app = FakeConversationApp()

        with (
            patch("jarvis_assistant.app_conversation_control.threading.Thread", NoopThread),
            patch("jarvis_assistant.config.update_settings") as update_settings,
        ):
            ConversationController(app).handle_remote_user_text("remote-1", "Damien, be active and speak up")

        update_settings.assert_called_once_with({"proactive_enabled": True, "proactive_voice_enabled": True})
        self.assertEqual(app.current_remote_request_id, "remote-1")
        self.assertTrue(app.proactive_enabled.get())
        self.assertTrue(app.proactive_voice_enabled.get())
        self.assertEqual(app.responded_texts, [])
        self.assertEqual(app.events.items, [("stream_text", "Active companion mode is on. I will watch and speak up."), ("done", None)])

    def test_handle_user_text_turns_off_active_spoken_notices_by_voice(self):
        app = FakeConversationApp(proactive_enabled=True, proactive_voice_enabled=True)
        loop = StoppableLoop()
        app.proactive_loop = loop

        with (
            patch("jarvis_assistant.app_conversation_control.threading.Thread", NoopThread),
            patch("jarvis_assistant.config.update_settings") as update_settings,
        ):
            ConversationController(app).handle_user_text("Damien, stop speaking up")

        update_settings.assert_called_once_with({"proactive_enabled": False, "proactive_voice_enabled": False})
        self.assertFalse(app.proactive_enabled.get())
        self.assertFalse(app.proactive_voice_enabled.get())
        self.assertFalse(app.settings.proactive_enabled)
        self.assertFalse(app.settings.proactive_voice_enabled)
        self.assertTrue(loop.stopped)
        self.assertIsNone(app.proactive_loop)
        self.assertEqual(app.proactive_summary.value, "Active companion checks off; speak-up notices off")
        self.assertEqual(app.events.items, [("stream_text", "Active companion mode is off. I will stay quiet unless you call me."), ("done", None)])
        self.assertEqual(app.history.users, ["Damien, stop speaking up"])

    def test_handle_user_text_turns_off_active_mode_unless_asked(self):
        app = FakeConversationApp(proactive_enabled=True, proactive_voice_enabled=True)
        loop = StoppableLoop()
        app.proactive_loop = loop

        with (
            patch("jarvis_assistant.app_conversation_control.threading.Thread", NoopThread),
            patch("jarvis_assistant.config.update_settings") as update_settings,
        ):
            ConversationController(app).handle_user_text("Damien, don't speak up unless I ask")

        update_settings.assert_called_once_with({"proactive_enabled": False, "proactive_voice_enabled": False})
        self.assertFalse(app.proactive_enabled.get())
        self.assertFalse(app.proactive_voice_enabled.get())
        self.assertTrue(loop.stopped)
        self.assertIsNone(app.proactive_loop)
        self.assertEqual(app.responded_texts, [])
        self.assertEqual(app.events.items, [("stream_text", "Active companion mode is off. I will stay quiet unless you call me."), ("done", None)])

    def test_handle_user_text_turns_off_active_mode_only_if_asked(self):
        app = FakeConversationApp(proactive_enabled=True, proactive_voice_enabled=True)
        loop = StoppableLoop()
        app.proactive_loop = loop

        with (
            patch("jarvis_assistant.app_conversation_control.threading.Thread", NoopThread),
            patch("jarvis_assistant.config.update_settings") as update_settings,
        ):
            ConversationController(app).handle_user_text("Damien, only speak up if I ask")

        update_settings.assert_called_once_with({"proactive_enabled": False, "proactive_voice_enabled": False})
        self.assertFalse(app.proactive_enabled.get())
        self.assertFalse(app.proactive_voice_enabled.get())
        self.assertTrue(loop.stopped)
        self.assertIsNone(app.proactive_loop)
        self.assertEqual(app.responded_texts, [])
        self.assertEqual(app.events.items, [("stream_text", "Active companion mode is off. I will stay quiet unless you call me."), ("done", None)])

    def test_handle_user_text_turns_off_active_mode_stop_being_active(self):
        app = FakeConversationApp(proactive_enabled=True, proactive_voice_enabled=True)
        loop = StoppableLoop()
        app.proactive_loop = loop

        with (
            patch("jarvis_assistant.app_conversation_control.threading.Thread", NoopThread),
            patch("jarvis_assistant.config.update_settings") as update_settings,
        ):
            ConversationController(app).handle_user_text("Damien, stop being active")

        update_settings.assert_called_once_with({"proactive_enabled": False, "proactive_voice_enabled": False})
        self.assertFalse(app.proactive_enabled.get())
        self.assertFalse(app.proactive_voice_enabled.get())
        self.assertTrue(loop.stopped)
        self.assertIsNone(app.proactive_loop)
        self.assertEqual(app.responded_texts, [])
        self.assertEqual(app.events.items, [("stream_text", "Active companion mode is off. I will stay quiet unless you call me."), ("done", None)])


if __name__ == "__main__":
    unittest.main()
