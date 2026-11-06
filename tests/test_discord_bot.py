import io
import json
import unittest
from unittest.mock import patch

from jarvis_assistant.discord_bot import chunk_discord_reply, remote_damien_command


class DiscordBotTests(unittest.TestCase):
    def test_remote_damien_command_posts_to_local_remote_api(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return io.BytesIO(json.dumps({"response": "Hello from Damien."}).encode("utf-8"))

        response = remote_damien_command("http://127.0.0.1:8765", "123456", "status", opener=opener)

        self.assertEqual(response, "Hello from Damien.")
        self.assertEqual(captured["url"], "http://127.0.0.1:8765/api/command")
        self.assertEqual(captured["body"], {"pin": "123456", "text": "status"})
        self.assertEqual(captured["timeout"], 95)

    def test_remote_damien_command_reports_remote_errors(self):
        def opener(_request, _timeout):
            return io.BytesIO(json.dumps({"error": "Invalid PIN."}).encode("utf-8"))

        response = remote_damien_command("http://127.0.0.1:8765", "wrong", "status", opener=opener)

        self.assertEqual(response, "Invalid PIN.")

    def test_chunk_discord_reply_respects_message_limit(self):
        chunks = chunk_discord_reply("a" * 4100, limit=1900)

        self.assertEqual(len(chunks), 3)
        self.assertTrue(all(len(chunk) <= 1900 for chunk in chunks))
        self.assertEqual("".join(chunks), "a" * 4100)

    def test_discord_module_does_not_require_discord_package_at_import_time(self):
        with patch.dict("sys.modules", {"discord": None}):
            import jarvis_assistant.discord_bot as discord_bot

        self.assertTrue(hasattr(discord_bot, "DiscordBotBridge"))


if __name__ == "__main__":
    unittest.main()
