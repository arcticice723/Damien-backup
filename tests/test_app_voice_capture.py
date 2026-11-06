import unittest

from jarvis_assistant.app_voice_capture import capture_text_events, near_silence_error


class AppVoiceCaptureTests(unittest.TestCase):
    def test_capture_text_events_routes_push_to_talk_text_to_user_text(self):
        self.assertEqual(capture_text_events("open notes", wake_command=False), [("user_text", "open notes")])

    def test_capture_text_events_routes_empty_wake_command_as_nothing(self):
        self.assertEqual(
            capture_text_events("", wake_command=True),
            [("wake_command_heard", "nothing"), ("user_text", "")],
        )

    def test_near_silence_error_matches_existing_voice_guidance(self):
        self.assertEqual(
            near_silence_error(),
            "This microphone is not picking up sound. Choose another microphone in Settings.",
        )


if __name__ == "__main__":
    unittest.main()
