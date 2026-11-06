import unittest

from jarvis_assistant.app_mic_privacy_control import mic_privacy_status


class AppMicPrivacyControlTests(unittest.TestCase):
    def test_mic_privacy_status_matches_enabled_and_muted_states(self):
        self.assertEqual(
            mic_privacy_status(True),
            "Microphone enabled. No recording occurs until push-to-talk in this stage.",
        )
        self.assertEqual(
            mic_privacy_status(False),
            "Privacy control active: microphone capture is stopped.",
        )


if __name__ == "__main__":
    unittest.main()
