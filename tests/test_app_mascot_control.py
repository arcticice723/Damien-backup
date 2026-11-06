import unittest

from jarvis_assistant.app_mascot_control import assistant_motion_state


class AppMascotControlTests(unittest.TestCase):
    def test_assistant_motion_state_prioritizes_thinking_listening_and_mute(self):
        self.assertEqual(assistant_motion_state(streaming_active=True, wake_running=True, mic_enabled=True), "thinking")
        self.assertEqual(assistant_motion_state(streaming_active=False, wake_running=True, mic_enabled=True), "listening")
        self.assertEqual(assistant_motion_state(streaming_active=False, wake_running=False, mic_enabled=True), "idle")
        self.assertEqual(assistant_motion_state(streaming_active=False, wake_running=False, mic_enabled=False), "muted")


if __name__ == "__main__":
    unittest.main()
