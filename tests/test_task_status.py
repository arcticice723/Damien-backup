import unittest
import tempfile
import sys
import types
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.task_status import TaskStatusMonitor, VisibleStatusVerifier, visible_window_exists


class TaskStatusMonitorTests(unittest.TestCase):
    def test_retries_until_verifier_reports_done(self):
        checks = iter([(False, "loading"), (False, "still loading"), (True, "ready")])
        monitor = TaskStatusMonitor(max_checks=4, interval_seconds=0.1)

        with patch("jarvis_assistant.task_status.time.sleep") as sleep:
            result = monitor.wait_until(lambda: next(checks))

        self.assertTrue(result.done)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.detail, "ready")
        self.assertEqual(sleep.call_count, 2)

    def test_returns_last_status_when_verifier_never_reports_done(self):
        monitor = TaskStatusMonitor(max_checks=3, interval_seconds=0.1)

        with patch("jarvis_assistant.task_status.time.sleep"):
            result = monitor.wait_until(lambda: (False, "not there yet"))

        self.assertFalse(result.done)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(result.detail, "not there yet")

    def test_visible_status_verifier_does_not_capture_screen_when_status_is_confirmed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            verifier = VisibleStatusVerifier(root, max_checks=2, interval_seconds=0.1)

            with patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(True, "Confirmed visible status text: voice connected"),
            ), patch("jarvis_assistant.task_status.ScreenReader") as screen_reader:
                result = verifier.verify(r".*Discord.*", ("voice connected",))

        self.assertTrue(result.done)
        self.assertIn("Confirmed visible status", result.detail)
        screen_reader.assert_not_called()

    def test_visible_status_verifier_captures_screen_evidence_when_status_is_not_confirmed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            capture = type("Capture", (), {"path": root / "screenshots" / "status.png", "width": 80, "height": 45})()
            verifier = VisibleStatusVerifier(root, max_checks=2, interval_seconds=0.1)

            with patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(False, "Visible app window did not show the expected status yet."),
            ), patch("jarvis_assistant.task_status.time.sleep"), patch(
                "jarvis_assistant.task_status.ScreenReader"
            ) as screen_reader:
                screen_reader.return_value.capture_screen.return_value = capture
                result = verifier.verify(r".*Discord.*", ("voice connected",))

        self.assertFalse(result.done)
        self.assertEqual(result.attempts, 2)
        self.assertIn("Visible app window did not show", result.detail)
        self.assertIn("Screen evidence:", result.detail)
        self.assertIn("status.png", result.detail)

    def test_visible_status_verifier_respects_disabled_screen_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir()
            (root / "config" / "settings.json").write_text('{"screen_access_enabled": false}', encoding="utf-8")
            verifier = VisibleStatusVerifier(root, max_checks=1, interval_seconds=0.1)

            with patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(False, "No matching visible app window."),
            ), patch("jarvis_assistant.screen_access.ScreenReader.capture_screen") as capture_screen:
                result = verifier.verify(r".*Discord.*", ("voice connected",))

        self.assertFalse(result.done)
        self.assertIn("screen access is disabled", result.detail.lower())
        capture_screen.assert_not_called()

    def test_visible_window_exists_reports_matching_visible_window(self):
        class FakeDesktop:
            def __init__(self, backend: str) -> None:
                self.backend = backend

            def windows(self, title_re: str, visible_only: bool):
                return [object()]

        fake_pywinauto = types.SimpleNamespace(Desktop=FakeDesktop)

        with patch.dict(sys.modules, {"pywinauto": fake_pywinauto}):
            found, detail = visible_window_exists(r".*Apex.*")

        self.assertTrue(found)
        self.assertIn("visible", detail.lower())

    def test_visible_window_exists_reports_no_matching_window(self):
        class FakeDesktop:
            def __init__(self, backend: str) -> None:
                self.backend = backend

            def windows(self, title_re: str, visible_only: bool):
                return []

        fake_pywinauto = types.SimpleNamespace(Desktop=FakeDesktop)

        with patch.dict(sys.modules, {"pywinauto": fake_pywinauto}):
            found, detail = visible_window_exists(r".*Apex.*")

        self.assertFalse(found)
        self.assertIn("no matching", detail.lower())


if __name__ == "__main__":
    unittest.main()
