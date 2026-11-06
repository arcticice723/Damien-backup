import unittest

from jarvis_assistant.app_state import active_companion_summary_text, mascot_opacity_percent_text, wake_summary_text


class AppStateTests(unittest.TestCase):
    def test_mascot_opacity_percent_text_rounds_settings_value(self):
        self.assertEqual(mascot_opacity_percent_text(0.944), "94")
        self.assertEqual(mascot_opacity_percent_text(1.0), "100")

    def test_wake_summary_text_matches_initial_wake_state(self):
        self.assertEqual(wake_summary_text(True), "Wake phrase initializing")
        self.assertEqual(wake_summary_text(False), "Wake phrase off")

    def test_active_companion_summary_text_matches_initial_proactive_state(self):
        self.assertEqual(active_companion_summary_text(True, True), "Active companion checks on; speak-up notices on")
        self.assertEqual(active_companion_summary_text(True, False), "Active companion checks on; speak-up notices off")
        self.assertEqual(active_companion_summary_text(False, True), "Active companion checks off; speak-up notices on")


if __name__ == "__main__":
    unittest.main()
