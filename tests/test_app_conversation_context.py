import unittest

from jarvis_assistant.app_conversation_context import memory_context_message


class AppConversationContextTests(unittest.TestCase):
    def test_memory_context_message_formats_inspectable_memory(self):
        self.assertEqual(
            memory_context_message([{"content": "Blue cable is for the monitor."}]),
            "Inspectable long-term memory:\nBlue cable is for the monitor.",
        )
        self.assertIsNone(memory_context_message([]))


if __name__ == "__main__":
    unittest.main()
