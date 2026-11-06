import unittest

from jarvis_assistant.app_voice_diagnostics import diagnostics_step_line


class AppVoiceDiagnosticsTests(unittest.TestCase):
    def test_diagnostics_step_line_formats_pass_without_fix_text(self):
        self.assertEqual(
            diagnostics_step_line(1, "Python/venv", True, "C:/app/.venv/python.exe"),
            "1. Python/venv: PASS - C:/app/.venv/python.exe",
        )

    def test_diagnostics_step_line_includes_fix_only_for_failures(self):
        self.assertEqual(
            diagnostics_step_line(2, "microphone", False, "No input devices found.", "Check Windows input settings."),
            "2. microphone: FAIL - No input devices found.\n   Fix: Check Windows input settings.",
        )


if __name__ == "__main__":
    unittest.main()
