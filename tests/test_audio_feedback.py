import unittest

from jarvis_assistant.audio_feedback import command_captured_cue, wake_acknowledgement_cue


class AudioFeedbackTests(unittest.TestCase):
    def test_wake_acknowledgement_uses_spoken_cue_text(self):
        self.assertEqual(wake_acknowledgement_cue("yes?"), "yes?")
        self.assertEqual(wake_acknowledgement_cue("mhm?"), "mhm?")
        self.assertEqual(wake_acknowledgement_cue(""), "yes?")

    def test_command_captured_uses_soft_thinking_cue_text(self):
        self.assertEqual(command_captured_cue("hmmm..."), "hmmm...")
        self.assertEqual(command_captured_cue(""), "hmmm...")


if __name__ == "__main__":
    unittest.main()
