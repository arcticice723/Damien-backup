import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jarvis_assistant.app_lifecycle import (
    AppLifecycleController,
    remote_status_payload,
    resolve_remote_pin,
    start_minimized_status_text,
    tray_status_text,
)


class AppLifecycleTests(unittest.TestCase):
    def test_resolve_remote_pin_generates_auto_pin(self):
        pin, changed = resolve_remote_pin("auto", randbelow=lambda _limit: 234567)

        self.assertEqual(pin, "334567")
        self.assertTrue(changed)

    def test_resolve_remote_pin_keeps_configured_pin(self):
        pin, changed = resolve_remote_pin("123456", randbelow=lambda _limit: 0)

        self.assertEqual(pin, "123456")
        self.assertFalse(changed)

    def test_remote_status_payload_uses_visible_status_values(self):
        payload = remote_status_payload(
            status="Ready",
            engine="llama connected",
            voice="Voice ready",
            wake="Wake on",
            privacy="Local mode",
        )

        self.assertEqual(payload["engine"], "llama connected")
        self.assertEqual(payload["privacy"], "Local mode")

    def test_tray_status_text_summarizes_runtime_flags(self):
        self.assertEqual(
            tray_status_text(mic_enabled=True, ollama_connected=False, wake_running=True),
            "Mic on | Ollama offline | Wake on",
        )

    def test_start_minimized_status_text_describes_next_launch_behavior(self):
        self.assertEqual(start_minimized_status_text(True), "Damien will start in background tray mode.")
        self.assertEqual(start_minimized_status_text(False), "Damien will show the window on startup.")

    def test_enabling_launch_at_sign_in_enables_background_tray_start(self):
        app = _FakeLifecycleApp(launch=True, start_minimized=False, wake=True)

        with (
            patch("jarvis_assistant.app_lifecycle.messagebox.askyesno", return_value=True),
            patch("jarvis_assistant.app_lifecycle.set_launch_at_sign_in") as set_launch,
            patch("jarvis_assistant.app_lifecycle.update_settings") as update_settings,
        ):
            AppLifecycleController(app).toggle_launch_at_sign_in()

        set_launch.assert_called_once()
        update_settings.assert_called_once_with({"launch_at_sign_in": True, "start_minimized_to_tray": True})
        self.assertTrue(app.start_minimized_to_tray.get())

    def test_enabling_launch_at_sign_in_enables_wake_phrase(self):
        app = _FakeLifecycleApp(launch=True, start_minimized=True, wake=False)

        with (
            patch("jarvis_assistant.app_lifecycle.messagebox.askyesno", return_value=True),
            patch("jarvis_assistant.app_lifecycle.set_launch_at_sign_in") as set_launch,
            patch("jarvis_assistant.app_lifecycle.update_settings") as update_settings,
        ):
            AppLifecycleController(app).toggle_launch_at_sign_in()

        set_launch.assert_called_once()
        update_settings.assert_called_once_with({"launch_at_sign_in": True, "wake_phrase_enabled": True})
        self.assertTrue(app.wake_enabled.get())

    def test_enabling_launch_at_sign_in_enables_active_spoken_notices(self):
        app = _FakeLifecycleApp(
            launch=True,
            start_minimized=True,
            wake=True,
            proactive=False,
            proactive_voice=False,
        )

        with (
            patch("jarvis_assistant.app_lifecycle.messagebox.askyesno", return_value=True),
            patch("jarvis_assistant.app_lifecycle.set_launch_at_sign_in") as set_launch,
            patch("jarvis_assistant.app_lifecycle.update_settings") as update_settings,
        ):
            AppLifecycleController(app).toggle_launch_at_sign_in()

        set_launch.assert_called_once()
        update_settings.assert_called_once_with(
            {"launch_at_sign_in": True, "proactive_enabled": True, "proactive_voice_enabled": True}
        )
        self.assertTrue(app.proactive_enabled.get())
        self.assertTrue(app.proactive_voice_enabled.get())

    def test_enabling_launch_at_sign_in_starts_active_checks_during_current_session(self):
        app = _FakeLifecycleApp(launch=True, start_minimized=True, wake=True, proactive=False)

        with (
            patch("jarvis_assistant.app_lifecycle.messagebox.askyesno", return_value=True),
            patch("jarvis_assistant.app_lifecycle.set_launch_at_sign_in"),
            patch("jarvis_assistant.app_lifecycle.update_settings"),
        ):
            AppLifecycleController(app).toggle_launch_at_sign_in()

        self.assertTrue(app.settings.proactive_enabled)
        self.assertTrue(app.proactive_loop_started)

    def test_enabling_launch_at_sign_in_reports_background_voice_readiness(self):
        app = _FakeLifecycleApp(launch=True, start_minimized=False, wake=False)

        with (
            patch("jarvis_assistant.app_lifecycle.messagebox.askyesno", return_value=True),
            patch("jarvis_assistant.app_lifecycle.set_launch_at_sign_in"),
            patch("jarvis_assistant.app_lifecycle.update_settings"),
        ):
            AppLifecycleController(app).toggle_launch_at_sign_in()

        self.assertEqual(
            app.status.get(),
            "Damien will launch at sign-in in background tray mode with wake phrase, active checks, and spoken notices enabled.",
        )

    def test_declining_launch_at_sign_in_confirmation_reports_cancelled_status(self):
        app = _FakeLifecycleApp(launch=True, start_minimized=True, wake=True)

        with (
            patch("jarvis_assistant.app_lifecycle.messagebox.askyesno", return_value=False),
            patch("jarvis_assistant.app_lifecycle.set_launch_at_sign_in") as set_launch,
            patch("jarvis_assistant.app_lifecycle.update_settings") as update_settings,
        ):
            AppLifecycleController(app).toggle_launch_at_sign_in()

        set_launch.assert_not_called()
        update_settings.assert_not_called()
        self.assertFalse(app.launch_at_sign_in.get())
        self.assertEqual(app.status.get(), "Launch at sign-in was left off.")

    def test_quit_stops_proactive_loop(self):
        app = _FakeLifecycleApp(launch=False, start_minimized=True, wake=True)
        app.proactive_loop = _FakeStoppable(lambda: setattr(app, "proactive_loop_stopped", True))

        AppLifecycleController(app).quit()

        self.assertTrue(app.proactive_loop_stopped)
        self.assertIsNone(app.proactive_loop)


class _FakeBool:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value

    def set(self, value: bool) -> None:
        self.value = value


class _FakeLifecycleApp:
    def __init__(
        self,
        launch: bool,
        start_minimized: bool,
        wake: bool,
        proactive: bool = True,
        proactive_voice: bool = True,
    ) -> None:
        self.launch_at_sign_in = _FakeBool(launch)
        self.start_minimized_to_tray = _FakeBool(start_minimized)
        self.wake_enabled = _FakeBool(wake)
        self.proactive_enabled = _FakeBool(proactive)
        self.proactive_voice_enabled = _FakeBool(proactive_voice)
        self.settings = SimpleNamespace(proactive_enabled=proactive, proactive_voice_enabled=proactive_voice)
        self.status = _FakeBool("")
        self.quitting = False
        self.wake_detector = None
        self.tray = None
        self.remote = None
        self.discord_bridge = None
        self.proactive_loop = None
        self.proactive_loop_started = False
        self.proactive_loop_stopped = False
        self.destroyed = False

    def _start_proactive_loop(self) -> None:
        if self.settings.proactive_enabled:
            self.proactive_loop_started = True

    def destroy(self) -> None:
        self.destroyed = True


class _FakeStoppable:
    def __init__(self, on_stop=None) -> None:
        self.on_stop = on_stop

    def stop(self) -> None:
        if self.on_stop is not None:
            self.on_stop()


if __name__ == "__main__":
    unittest.main()
