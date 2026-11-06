import unittest

from jarvis_assistant.app_bridge_control import discord_bot_token


class AppBridgeControlTests(unittest.TestCase):
    def test_discord_bot_token_prefers_environment_then_settings(self):
        self.assertEqual(discord_bot_token(" env-token ", "settings-token"), "env-token")
        self.assertEqual(discord_bot_token(" ", " settings-token "), "settings-token")
        self.assertEqual(discord_bot_token("", " "), "")


if __name__ == "__main__":
    unittest.main()
