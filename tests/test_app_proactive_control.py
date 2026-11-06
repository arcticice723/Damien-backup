import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from jarvis_assistant.app_proactive_control import (
    ProactiveController,
    proactive_settings_update,
    proactive_voice_settings_update,
    should_speak_proactive_notice,
    update_loaded_setting,
)


class FakeStatus:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class FakeHistory:
    def __init__(self) -> None:
        self.assistant_messages: list[str] = []

    def add_assistant(self, text: str) -> None:
        self.assistant_messages.append(text)


class FakeBool:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value

    def set(self, value: bool) -> None:
        self.value = value


class FakeApp:
    def __init__(self, proactive_voice_enabled: bool = True, tts_engine: str = "piper") -> None:
        self.settings = SimpleNamespace(
            proactive_enabled=True,
            proactive_voice_enabled=proactive_voice_enabled,
            tts_engine=tts_engine,
            reminder_check_seconds=30,
        )
        self.status = FakeStatus()
        self.proactive_summary = FakeStatus()
        self.history = FakeHistory()
        self.proactive_enabled = FakeBool(True)
        self.proactive_voice_enabled = FakeBool(True)
        self.lines: list[tuple[str, str]] = []
        self.spoken: list[str] = []
        self.events = SimpleNamespace(put=lambda _event: None)
        self.orchestrator = SimpleNamespace(check_proactive=lambda: [])
        self.proactive_loop = None
        self.quitting = False
        self.connection_logs: list[str] = []

    def _append_line(self, speaker: str, text: str) -> None:
        self.lines.append((speaker, text))

    def _speak(self, text: str) -> None:
        self.spoken.append(text)

    def _log_connection(self, text: str) -> None:
        self.connection_logs.append(text)


class ImmediateThread:
    def __init__(self, target, args=(), daemon=False) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        self.target(*self.args)


class StoppableLoop:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


@dataclass(frozen=True)
class FrozenSettings:
    proactive_enabled: bool
    proactive_voice_enabled: bool = True


class AppProactiveControlTests(unittest.TestCase):
    def test_proactive_settings_update_saves_active_companion_flag(self):
        self.assertEqual(proactive_settings_update(True), {"proactive_enabled": True})
        self.assertEqual(proactive_settings_update(False), {"proactive_enabled": False})

    def test_proactive_voice_settings_update_saves_speak_up_flag(self):
        self.assertEqual(proactive_voice_settings_update(True), {"proactive_voice_enabled": True})
        self.assertEqual(proactive_voice_settings_update(False), {"proactive_voice_enabled": False})

    def test_update_loaded_setting_replaces_frozen_settings(self):
        app = SimpleNamespace(settings=FrozenSettings(proactive_enabled=True))

        update_loaded_setting(app, "proactive_enabled", False)

        self.assertFalse(app.settings.proactive_enabled)

    def test_should_speak_proactive_notice_requires_voice_and_tts_engine(self):
        self.assertTrue(should_speak_proactive_notice(True, "piper"))
        self.assertFalse(should_speak_proactive_notice(False, "piper"))
        self.assertFalse(should_speak_proactive_notice(True, "off"))

    def test_show_notice_reports_when_damien_spoke_up(self):
        app = FakeApp(proactive_voice_enabled=True, tts_engine="piper")

        with patch("jarvis_assistant.app_proactive_control.threading.Thread", ImmediateThread):
            ProactiveController(app).show_notice("Reminder: stretch.")

        self.assertEqual(app.lines, [("Damien", "Reminder: stretch.")])
        self.assertEqual(app.history.assistant_messages, ["Reminder: stretch."])
        self.assertEqual(app.spoken, ["Reminder: stretch."])
        self.assertEqual(app.status.value, "Proactive notice spoken.")

    def test_show_notice_uses_live_proactive_voice_toggle(self):
        app = FakeApp(proactive_voice_enabled=True, tts_engine="piper")
        app.proactive_voice_enabled.set(False)

        with patch("jarvis_assistant.app_proactive_control.threading.Thread", ImmediateThread):
            ProactiveController(app).show_notice("Reminder: stretch.")

        self.assertEqual(app.spoken, [])
        self.assertEqual(app.status.value, "Proactive notice.")

    def test_toggle_proactive_checks_saves_active_companion_status(self):
        app = FakeApp()
        app.settings.proactive_enabled = True
        app.proactive_enabled.set(False)

        with patch("jarvis_assistant.app_proactive_control.update_settings") as update_settings:
            ProactiveController(app).toggle_proactive_checks()

        update_settings.assert_called_once_with({"proactive_enabled": False})
        self.assertFalse(app.settings.proactive_enabled)
        self.assertEqual(app.status.value, "Active companion checks are off.")
        self.assertEqual(app.proactive_summary.value, "Active companion checks off; speak-up notices on")

    def test_toggle_proactive_checks_stops_existing_loop_when_disabled(self):
        app = FakeApp()
        app.proactive_enabled.set(False)
        loop = StoppableLoop()
        app.proactive_loop = loop

        with patch("jarvis_assistant.app_proactive_control.update_settings"):
            ProactiveController(app).toggle_proactive_checks()

        self.assertTrue(loop.stopped)
        self.assertIsNone(app.proactive_loop)
        self.assertEqual(app.status.value, "Active companion checks are off.")

    def test_toggle_proactive_checks_starts_loop_when_enabled_during_session(self):
        app = FakeApp()
        app.settings.proactive_enabled = False
        app.proactive_enabled.set(True)
        started_loops = []

        class FakeLoop:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

            def start(self) -> None:
                started_loops.append(self.kwargs)

        with (
            patch("jarvis_assistant.app_proactive_control.update_settings"),
            patch("jarvis_assistant.app_proactive_control.ProactiveLoop", FakeLoop),
        ):
            ProactiveController(app).toggle_proactive_checks()

        self.assertEqual(len(started_loops), 1)
        self.assertEqual(app.status.value, "Active companion checks are on.")
        self.assertEqual(app.proactive_summary.value, "Active companion checks on; speak-up notices on")

    def test_start_loop_does_not_duplicate_existing_active_loop(self):
        app = FakeApp()
        started_loops = []

        class FakeLoop:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

            def start(self) -> None:
                started_loops.append(self)

        with patch("jarvis_assistant.app_proactive_control.ProactiveLoop", FakeLoop):
            controller = ProactiveController(app)
            controller.start_loop()
            controller.start_loop()

        self.assertEqual(len(started_loops), 1)
        self.assertIs(app.proactive_loop, started_loops[0])

    def test_toggle_proactive_voice_saves_speak_up_status(self):
        app = FakeApp()
        app.settings.proactive_voice_enabled = False
        app.proactive_voice_enabled.set(True)

        with patch("jarvis_assistant.app_proactive_control.update_settings") as update_settings:
            ProactiveController(app).toggle_proactive_voice()

        update_settings.assert_called_once_with({"proactive_voice_enabled": True})
        self.assertTrue(app.settings.proactive_voice_enabled)
        self.assertEqual(app.status.value, "Damien will speak proactive notices aloud.")
        self.assertEqual(app.proactive_summary.value, "Active companion checks on; speak-up notices on")

    def test_toggle_proactive_voice_reports_silent_when_tts_engine_is_off(self):
        app = FakeApp(tts_engine="off")
        app.proactive_voice_enabled.set(True)

        with patch("jarvis_assistant.app_proactive_control.update_settings") as update_settings:
            ProactiveController(app).toggle_proactive_voice()

        update_settings.assert_called_once_with({"proactive_voice_enabled": True})
        self.assertEqual(app.status.value, "Voice output is off, so proactive notices will stay silent.")

    def test_toggle_proactive_voice_updates_speak_up_readiness_when_disabled(self):
        app = FakeApp()
        app.settings.proactive_voice_enabled = True
        app.proactive_voice_enabled.set(False)

        with patch("jarvis_assistant.app_proactive_control.update_settings"):
            ProactiveController(app).toggle_proactive_voice()

        self.assertEqual(app.proactive_summary.value, "Active companion checks on; speak-up notices off")


if __name__ == "__main__":
    unittest.main()
