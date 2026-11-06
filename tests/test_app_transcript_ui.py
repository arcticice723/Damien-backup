import unittest

from jarvis_assistant.app_transcript_ui import transcript_speaker_prefix


class TranscriptUiTests(unittest.TestCase):
    def test_speaker_prefix_matches_transcript_format(self):
        self.assertEqual(transcript_speaker_prefix("Damien"), "Damien:\n")


if __name__ == "__main__":
    unittest.main()
