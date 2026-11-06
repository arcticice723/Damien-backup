import tempfile
import unittest
from pathlib import Path

from jarvis_assistant.conversation import ConversationHistory, SYSTEM_PROMPT


class ConversationHistoryTests(unittest.TestCase):
    def test_persists_and_reloads_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "conversation.jsonl"
            history = ConversationHistory(path)
            history.add_user("hello")
            history.add_assistant("hi")

            loaded = ConversationHistory(path)
            provider_messages = loaded.for_provider()

        self.assertEqual(provider_messages[-2].role, "user")
        self.assertEqual(provider_messages[-2].content, "hello")
        self.assertEqual(provider_messages[-1].role, "assistant")
        self.assertEqual(provider_messages[-1].content, "hi")

    def test_system_prompt_prefers_spoken_clarity(self):
        self.assertIn("speaking to the user in the room", SYSTEM_PROMPT)
        self.assertIn("short spoken sentences", SYSTEM_PROMPT)
        self.assertIn("Do not use Markdown emphasis", SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
