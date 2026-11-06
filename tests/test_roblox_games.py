import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.roblox_games import RobloxGameLauncher


class RobloxGameLauncherTests(unittest.TestCase):
    def test_opens_configured_roblox_experience_by_alias(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_config(root, "arsenal", "Arsenal", "286090429", aliases=["fps"])

            with patch("jarvis_assistant.roblox_games.webbrowser.open") as open_url:
                result = RobloxGameLauncher(root).open_game("fps")

        self.assertEqual(result, "Opening Roblox game: Arsenal.")
        open_url.assert_called_once_with("https://www.roblox.com/games/286090429")

    def test_opens_configured_roblox_experience_url_directly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_config(root, "dress", "Dress To Impress", "https://www.roblox.com/games/15101393044/Dress-To-Impress")

            with patch("jarvis_assistant.roblox_games.webbrowser.open") as open_url:
                result = RobloxGameLauncher(root).open_game("dress")

        self.assertEqual(result, "Opening Roblox game: Dress To Impress.")
        open_url.assert_called_once_with("https://www.roblox.com/games/15101393044/Dress-To-Impress")

    def test_unknown_roblox_game_opens_roblox_search(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with patch("jarvis_assistant.roblox_games.webbrowser.open") as open_url:
                result = RobloxGameLauncher(root).open_game("tower defense")

        self.assertEqual(result, "I do not have tower defense saved yet, so I opened Roblox search for it.")
        open_url.assert_called_once_with("https://www.roblox.com/discover/?Keyword=tower%20defense")


def _write_config(root: Path, key: str, display_name: str, target: str, aliases: list[str] | None = None) -> None:
    config = root / "config" / "roblox_games.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "games": {
                    key: {
                        "display_name": display_name,
                        "target": target,
                        "aliases": aliases or [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
