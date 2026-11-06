import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.discord_control import DiscordCallController


class DiscordCallControllerTests(unittest.TestCase):
    def test_saved_group_chat_route_is_used_for_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = root / "config" / "discord_calls.json"
            config.parent.mkdir()
            config.write_text(
                json.dumps(
                    {
                        "targets": {
                            "squad": {
                                "display_name": "The Squad",
                                "type": "group",
                                "route": "discord://-/channels/@me/12345",
                                "aliases": ["group chat"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            controller = DiscordCallController(root)

            with patch("jarvis_assistant.discord_control.os.startfile") as startfile, patch.object(
                controller, "_click_call_button", return_value=True
            ), patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(True, "Voice connected"),
            ) as verify:
                result = controller.call("the group chat")

        self.assertEqual(result, "Starting Discord call with The Squad.")
        startfile.assert_called_once_with("discord://-/channels/@me/12345")
        verify.assert_called_with(r".*Discord.*", ("voice connected", "disconnect", "screen", "soundboard", "leave call"))

    def test_call_logs_upgrade_when_click_does_not_reach_connected_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            controller = DiscordCallController(root)

            with patch("jarvis_assistant.discord_control._discord_executable", return_value=None), patch(
                "jarvis_assistant.discord_control.os.startfile"
            ), patch.object(controller, "_search_discord"), patch.object(
                controller, "_click_call_button", return_value=True
            ), patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(False, "No connected call controls"),
            ), patch(
                "jarvis_assistant.task_status.ScreenReader"
            ) as screen_reader:
                screen_reader.return_value.capture_screen.return_value = type(
                    "Capture",
                    (),
                    {"path": root / "screenshots" / "discord.png", "width": 100, "height": 50},
                )()
                result = controller.call("Alex")

            self.assertIn("could not confirm the call connected", result)
            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("Screen evidence:", records[-1]["reason"])
            self.assertIn("discord.png", records[-1]["reason"])

    def test_search_fallback_opens_discord_when_target_is_not_saved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            controller = DiscordCallController(root)

            with patch("jarvis_assistant.discord_control._discord_executable", return_value=None), patch(
                "jarvis_assistant.discord_control.os.startfile"
            ) as startfile, patch.object(controller, "_search_discord") as search, patch.object(
                controller, "_click_call_button", return_value=False
            ), patch("jarvis_assistant.task_status.ScreenReader") as screen_reader:
                screen_reader.return_value.capture_screen.return_value = type(
                    "Capture",
                    (),
                    {"path": root / "screenshots" / "discord-no-button.png", "width": 100, "height": 50},
                )()
                result = controller.call("Alex")

            self.assertIn("I opened Alex in Discord", result)
            self.assertIn("queued a Discord calling upgrade", result)
            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("Screen evidence:", records[-1]["reason"])
            self.assertIn("discord-no-button.png", records[-1]["reason"])
            startfile.assert_called_once_with("discord:")
            search.assert_called_once_with("Alex")

    def test_answer_incoming_call_clicks_discord_answer_button(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            controller = DiscordCallController(Path(temp_dir))

            with patch("jarvis_assistant.discord_control._discord_executable", return_value=None), patch(
                "jarvis_assistant.discord_control.os.startfile"
            ) as startfile, patch.object(controller, "_click_discord_button", return_value=True) as click:
                result = controller.answer_call()

        self.assertEqual(result, "Answered the incoming Discord call.")
        startfile.assert_called_once_with("discord:")
        click.assert_called_once()

    def test_answer_incoming_call_logs_upgrade_when_button_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            controller = DiscordCallController(root)

            with patch("jarvis_assistant.discord_control._discord_executable", return_value=None), patch(
                "jarvis_assistant.discord_control.os.startfile"
            ), patch.object(controller, "_click_discord_button", return_value=False), patch(
                "jarvis_assistant.task_status.ScreenReader"
            ) as screen_reader:
                screen_reader.return_value.capture_screen.return_value = type(
                    "Capture",
                    (),
                    {"path": root / "screenshots" / "discord-answer.png", "width": 100, "height": 50},
                )()
                result = controller.answer_call()

            self.assertIn("could not find the incoming call button", result)
            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("Screen evidence:", records[-1]["reason"])
            self.assertIn("discord-answer.png", records[-1]["reason"])


if __name__ == "__main__":
    unittest.main()
