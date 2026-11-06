import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.game_lobby import (
    GAME_LOBBY_PROFILES,
    SafeUiController,
    current_lobby_game,
    has_lobby_profile,
    run_lobby_entry_now,
    schedule_lobby_entry,
)


class GameLobbyTests(unittest.TestCase):
    def test_known_games_have_lobby_profiles(self):
        self.assertTrue(has_lobby_profile("apex legends"))
        self.assertTrue(has_lobby_profile("marvel rivals"))

        self.assertEqual([step.label for step in GAME_LOBBY_PROFILES["apex legends"]], ["Continue"])
        self.assertEqual([step.label for step in GAME_LOBBY_PROFILES["marvel rivals"]], ["Launch", "Continue"])

    def test_schedules_lobby_thread_for_known_game_only(self):
        with patch("jarvis_assistant.game_lobby.threading.Thread") as thread:
            schedule_lobby_entry("apex legends")

        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

        with patch("jarvis_assistant.game_lobby.threading.Thread") as thread:
            schedule_lobby_entry("notepad")

        thread.assert_not_called()

    def test_lobby_followup_runs_last_lobby_game(self):
        with patch("jarvis_assistant.game_lobby.threading.Thread"):
            schedule_lobby_entry("apex legends")

        self.assertEqual(current_lobby_game(), "apex legends")

        with patch("jarvis_assistant.game_lobby._run_lobby_steps") as run_steps:
            result = run_lobby_entry_now()

        self.assertEqual(result, "Taking you to the Apex Legends lobby.")
        run_steps.assert_called_once()

    def test_lobby_failure_logs_upgrade_when_button_is_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("jarvis_assistant.game_lobby.time.sleep"), patch(
                "jarvis_assistant.game_lobby._click_button_by_name",
                return_value=False,
            ), patch("jarvis_assistant.game_lobby._press_enter", return_value=False), patch(
                "jarvis_assistant.task_status.ScreenReader"
            ) as screen_reader:
                screen_reader.return_value.capture_screen.return_value = type(
                    "Capture",
                    (),
                    {"path": root / "screenshots" / "lobby-no-button.png", "width": 120, "height": 70},
                )()
                run_lobby_entry_now("apex legends", root=root)

            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[-1]["request"], "Take Apex Legends to lobby")
            self.assertIn("Screen evidence:", records[-1]["reason"])
            self.assertIn("lobby-no-button.png", records[-1]["reason"])

    def test_lobby_keyboard_fallback_does_not_log_upgrade_when_button_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("jarvis_assistant.game_lobby.time.sleep"), patch("jarvis_assistant.task_status.time.sleep"), patch(
                "jarvis_assistant.game_lobby._click_button_by_name",
                return_value=False,
            ), patch("jarvis_assistant.game_lobby._press_enter", return_value=True) as press_enter, patch(
                "jarvis_assistant.game_lobby.visible_window_exists",
                return_value=(True, "Apex Legends window is visible."),
            ), patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(True, "Lobby ready"),
            ) as verify:
                run_lobby_entry_now("apex legends", root=root)

            press_enter.assert_called_once()
            verify.assert_called()
            self.assertFalse((root / "logs" / "improvement_queue.jsonl").exists())

    def test_lobby_logs_upgrade_when_action_does_not_reach_lobby_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("jarvis_assistant.game_lobby.time.sleep"), patch("jarvis_assistant.task_status.time.sleep"), patch(
                "jarvis_assistant.game_lobby._click_button_by_name",
                return_value=False,
            ), patch("jarvis_assistant.game_lobby._press_enter", return_value=True), patch(
                "jarvis_assistant.game_lobby.visible_window_exists",
                side_effect=[
                    (True, "Apex Legends window is visible."),
                    (False, "No matching visible game window."),
                ],
            ), patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(False, "Still on Continue screen"),
            ), patch("jarvis_assistant.task_status.ScreenReader") as screen_reader:
                screen_reader.return_value.capture_screen.return_value = type(
                    "Capture",
                    (),
                    {"path": root / "screenshots" / "lobby.png", "width": 120, "height": 70},
                )()
                run_lobby_entry_now("apex legends", root=root)

            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("did not confirm lobby status", records[-1]["reason"])
            self.assertIn("Screen evidence:", records[-1]["reason"])
            self.assertIn("lobby.png", records[-1]["reason"])

    def test_lobby_keyboard_fallback_requires_matching_game_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("jarvis_assistant.game_lobby.time.sleep"), patch(
                "jarvis_assistant.game_lobby._click_button_by_name",
                return_value=False,
            ), patch("jarvis_assistant.game_lobby.visible_window_exists", return_value=(False, "No Apex window.")), patch(
                "jarvis_assistant.game_lobby._press_enter",
                return_value=True,
            ) as press_enter, patch("jarvis_assistant.task_status.ScreenReader") as screen_reader:
                screen_reader.return_value.capture_screen.return_value = type(
                    "Capture",
                    (),
                    {"path": root / "screenshots" / "wrong-game.png", "width": 120, "height": 70},
                )()
                run_lobby_entry_now("apex legends", root=root)

            press_enter.assert_not_called()
            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("Could not find the Continue button", records[-1]["reason"])

    def test_lobby_preflight_reports_wrong_visible_game_before_pressing_controls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def visible_window(title_pattern: str) -> tuple[bool, str]:
                if title_pattern == r".*(Apex|r5apex).*":
                    return False, "No matching visible game window."
                if title_pattern == r".*(Marvel|Rivals).*":
                    return True, "Matching game window is visible."
                return False, "No matching visible game window."

            with patch("jarvis_assistant.game_lobby.time.sleep"), patch(
                "jarvis_assistant.game_lobby.visible_window_exists",
                side_effect=visible_window,
            ), patch("jarvis_assistant.game_lobby._click_button_by_name", return_value=True) as click_button, patch(
                "jarvis_assistant.game_lobby._press_enter",
                return_value=True,
            ) as press_enter, patch("jarvis_assistant.task_status.ScreenReader") as screen_reader:
                screen_reader.return_value.capture_screen.return_value = type(
                    "Capture",
                    (),
                    {"path": root / "screenshots" / "wrong-visible-game.png", "width": 120, "height": 70},
                )()
                run_lobby_entry_now("apex legends", root=root)

            click_button.assert_not_called()
            press_enter.assert_not_called()
            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn("Apex Legends window was not visible", records[-1]["reason"])
            self.assertIn("Marvel Rivals appears to be visible", records[-1]["reason"])
            self.assertIn("wrong-visible-game.png", records[-1]["reason"])

    def test_lobby_button_click_is_scoped_to_matching_game_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def click_button(_label: str, title_pattern: str | None = None) -> bool:
                return title_pattern == r".*(Apex|r5apex).*"

            with patch("jarvis_assistant.game_lobby.time.sleep"), patch("jarvis_assistant.task_status.time.sleep"), patch(
                "jarvis_assistant.game_lobby._click_button_by_name",
                side_effect=click_button,
            ), patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(True, "Lobby ready"),
            ):
                run_lobby_entry_now("apex legends", root=root)

            self.assertFalse((root / "logs" / "improvement_queue.jsonl").exists())

    def test_lobby_does_not_log_upgrade_when_game_window_remains_visible_after_final_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("jarvis_assistant.game_lobby.time.sleep"), patch("jarvis_assistant.task_status.time.sleep"), patch(
                "jarvis_assistant.game_lobby._click_button_by_name",
                return_value=True,
            ), patch(
                "jarvis_assistant.task_status.visible_window_contains",
                return_value=(False, "Visible app window did not show the expected status yet."),
            ), patch(
                "jarvis_assistant.game_lobby.visible_window_exists",
                return_value=(True, "Apex Legends window is visible."),
            ):
                run_lobby_entry_now("apex legends", root=root)

            self.assertFalse((root / "logs" / "improvement_queue.jsonl").exists())

    def test_multi_step_lobby_profile_does_not_log_upgrade_before_final_step(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clicked: list[str] = []

            def click_button(label: str, _title_pattern: str | None = None) -> bool:
                clicked.append(label)
                return True

            def visible_status(*_args):
                if clicked == ["Launch"]:
                    return False, "Continue screen is visible after launch."
                return True, "Confirmed visible status text: lobby"

            with patch("jarvis_assistant.game_lobby.time.sleep"), patch("jarvis_assistant.task_status.time.sleep"), patch(
                "jarvis_assistant.game_lobby._click_button_by_name",
                side_effect=click_button,
            ), patch(
                "jarvis_assistant.task_status.visible_window_contains",
                side_effect=visible_status,
            ):
                run_lobby_entry_now("marvel rivals", root=root)

            self.assertEqual(clicked, ["Launch", "Continue"])
            self.assertFalse((root / "logs" / "improvement_queue.jsonl").exists())

    def test_safe_ui_controller_allows_known_button_labels_only(self):
        clicked: list[str] = []
        controller = SafeUiController(click_button=lambda label: clicked.append(label) or True)

        self.assertIn("Clicked Continue", controller.click_known_button("continue"))
        self.assertEqual(clicked, ["Continue"])
        self.assertIn("Denied", controller.click_known_button("delete"))


if __name__ == "__main__":
    unittest.main()
