import unittest

from jarvis_assistant.app_speech_interaction import wake_feedback_action


class AppSpeechInteractionTests(unittest.TestCase):
    def test_wake_feedback_action_matches_acknowledgement_settings(self):
        self.assertEqual(wake_feedback_action("silent", sound_enabled=True), "none")
        self.assertEqual(wake_feedback_action("voice", sound_enabled=False), "voice")
        self.assertEqual(wake_feedback_action("tone", sound_enabled=True), "tone")
        self.assertEqual(wake_feedback_action("tone", sound_enabled=False), "none")


if __name__ == "__main__":
    unittest.main()
