import unittest

from jarvis_assistant.app_chat_ui import chat_status_cards


class AppChatUiTests(unittest.TestCase):
    def test_chat_status_cards_keep_sidebar_order_and_color_keys(self):
        self.assertEqual(
            chat_status_cards(),
            [
                ("LOCAL ENGINE", "local_engine_summary", "accent"),
                ("WAKE", "wake_summary", "blue"),
                ("VOICE", "voice_summary", "warning"),
                ("PRIVACY", "privacy_summary", "accent_dark"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
