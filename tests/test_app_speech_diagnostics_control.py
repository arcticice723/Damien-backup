import unittest

from jarvis_assistant.app_speech_diagnostics_control import muted_microphone_test_message


class AppSpeechDiagnosticsControlTests(unittest.TestCase):
    def test_muted_microphone_test_message_matches_existing_status(self):
        self.assertEqual(muted_microphone_test_message(), "Microphone is muted by privacy control.")


if __name__ == "__main__":
    unittest.main()
