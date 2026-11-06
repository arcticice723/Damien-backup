import unittest

from jarvis_assistant.app_startup_sequence import startup_step_names


class AppStartupSequenceTests(unittest.TestCase):
    def test_startup_step_names_keep_boot_order(self):
        self.assertEqual(
            startup_step_names(),
            [
                "style",
                "build_ui",
                "window_events",
                "mascot",
                "tray",
                "remote_control",
                "discord_bridge",
                "proactive_loop",
                "startup_visibility",
                "startup_state",
                "gpu_status",
                "ollama_status",
                "wake_phrase",
                "event_polling",
            ],
        )


if __name__ == "__main__":
    unittest.main()
