import tempfile
import unittest
import json
from subprocess import CompletedProcess
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.commands import ApprovedApp, CommandDispatcher
from jarvis_assistant.convenience import ConvenienceTools
from jarvis_assistant.memory import LongTermMemory
from jarvis_assistant.retrieval import ApprovedDocumentRetriever
from jarvis_assistant.tools import RiskLevel, ToolRegistry


class ToolRegistryTests(unittest.TestCase):
    def _registry(self, root: Path, memory_enabled: bool = True) -> ToolRegistry:
        commands = CommandDispatcher(
            {
                "notepad": ApprovedApp("Notepad", "notepad.exe", process_names=("notepad.exe",)),
                "apex legends": ApprovedApp("Apex Legends", r"C:\Users\kaish\Desktop\Apex Legends.url"),
            }
        )
        memory = LongTermMemory(root / "memory.jsonl", enabled=memory_enabled)
        retriever = ApprovedDocumentRetriever(root / "docs")
        return ToolRegistry(commands, retriever, memory, convenience=ConvenienceTools(root))

    def test_denies_dangerous_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            planned = self._registry(Path(temp_dir)).plan("delete all my files")

            self.assertEqual(planned.risk, RiskLevel.DENY)

    def test_opens_approved_app_as_low_risk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))
            planned = registry.plan("open notepad")

            with patch("jarvis_assistant.commands.subprocess.Popen") as popen:
                result = registry.execute(planned)

            self.assertEqual(result.risk, RiskLevel.LOW)
            self.assertIn("Opening Notepad", result.content)
            popen.assert_called_once()

    def test_closes_approved_app_as_low_risk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))
            planned = registry.plan("close notepad")

            with patch("jarvis_assistant.commands.subprocess.run", return_value=CompletedProcess([], 0)) as run:
                result = registry.execute(planned)

            self.assertEqual(result.risk, RiskLevel.LOW)
            self.assertIn("Closing Notepad", result.content)
            run.assert_called_once()

    def test_memory_disabled_does_not_claim_saved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir), memory_enabled=False)
            result = registry.execute(registry.plan("remember that I prefer short answers"))

            self.assertFalse(result.executed)
            self.assertIn("Memory is disabled", result.content)

    def test_searches_approved_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "note.md").write_text("The arc reactor prototype is ready.", encoding="utf-8")
            registry = self._registry(root)

            result = registry.execute(registry.plan("search documents for arc reactor"))

            self.assertIn("note.md", result.content)

    def test_takes_and_lists_local_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            save_result = registry.execute(registry.plan("take a note call the dentist"))
            list_result = registry.execute(registry.plan("show my notes"))

            self.assertIn("Saved note", save_result.content)
            self.assertIn("call the dentist", list_result.content)

    def test_opens_web_target_as_low_risk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch("jarvis_assistant.convenience.webbrowser.open") as open_web:
                result = registry.execute(registry.plan("open example.com"))

            self.assertEqual(result.risk, RiskLevel.LOW)
            self.assertIn("https://example.com", result.content)
            open_web.assert_called_once()

    def test_opens_crunchyroll_title_for_play_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch("jarvis_assistant.convenience.webbrowser.open") as open_web:
                result = registry.execute(registry.plan("play One Piece"))

            self.assertEqual(result.name, "crunchyroll_title")
            self.assertIn("Opened Crunchyroll for One Piece", result.content)
            open_web.assert_called_once_with("https://www.crunchyroll.com/search?q=One%20Piece")

    def test_opens_crunchyroll_title_with_configured_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir()
            (root / "config" / "settings.json").write_text(
                json.dumps({"crunchyroll_browser_automation_enabled": True, "crunchyroll_profile_name": "Damien"}),
                encoding="utf-8",
            )
            registry = self._registry(root)

            with patch("jarvis_assistant.convenience.ChromeController") as controller:
                controller.return_value.open_crunchyroll_title.return_value = "Opened Crunchyroll for One Piece using profile Damien."
                result = registry.execute(registry.plan("play One Piece"))

            self.assertEqual(result.name, "crunchyroll_title")
            self.assertIn("profile Damien", result.content)
            controller.return_value.open_crunchyroll_title.assert_called_once_with("One Piece", profile_name="Damien")

    def test_saves_crunchyroll_profile_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            result = registry.execute(registry.plan("set crunchyroll profile to Damien"))

            self.assertEqual(result.name, "set_crunchyroll_profile")
            self.assertIn("Crunchyroll profile set to Damien", result.content)

    def test_capabilities_command_reports_real_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            result = registry.execute(registry.plan("what can you do"))

            self.assertEqual(result.name, "capabilities")
            self.assertIn("Crunchyroll", result.content)
            self.assertIn("open and close approved Desktop apps", result.content)

    def test_media_control_command_uses_windows_media_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "media_control") as media:
                media.return_value = "Media pause."
                result = registry.execute(registry.plan("pause music"))

            self.assertEqual(result.name, "media_control")
            media.assert_called_once_with("pause")

    def test_media_control_accepts_short_and_natural_commands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "media_control") as media:
                media.return_value = "Media pause."
                result = registry.execute(registry.plan("pause"))

            self.assertEqual(result.name, "media_control")
            media.assert_called_once_with("pause")

            with patch.object(registry.convenience, "media_control") as media:
                media.return_value = "Media next."
                result = registry.execute(registry.plan("skip song"))

            self.assertEqual(result.name, "media_control")
            media.assert_called_once_with("next")

            with patch.object(registry.convenience, "media_control") as media:
                media.return_value = "Media resume."
                result = registry.execute(registry.plan("unpause my video"))

            self.assertEqual(result.name, "media_control")
            media.assert_called_once_with("resume")

    def test_discord_call_routes_to_discord_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "discord_call") as discord_call:
                discord_call.return_value = "Starting Discord call with Alex."
                result = registry.execute(registry.plan("call Alex on Discord"))

            self.assertEqual(result.name, "discord_call")
            discord_call.assert_called_once_with("Alex")

            with patch.object(registry.convenience, "discord_call") as discord_call:
                discord_call.return_value = "Starting Discord call with m."
                result = registry.execute(registry.plan("call m"))

            self.assertEqual(result.name, "discord_call")
            discord_call.assert_called_once_with("m")

    def test_discord_answer_call_routes_to_discord_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "discord_answer_call") as answer_call:
                answer_call.return_value = "Answered the incoming Discord call."
                result = registry.execute(registry.plan("answer Discord call"))

            self.assertEqual(result.name, "discord_answer_call")
            answer_call.assert_called_once_with()

    def test_editor_project_commands_route_to_project_opener(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "open_editor_project") as open_project:
                open_project.return_value = "Opening Unreal project RunBuildTest."
                result = registry.execute(registry.plan("open RunBuildTest in Unreal Engine"))

            self.assertEqual(result.name, "open_editor_project")
            open_project.assert_called_once_with("Unreal Engine", "RunBuildTest")

            with patch.object(registry.convenience, "open_editor_project") as open_project:
                open_project.return_value = "Opening Roblox Studio project devils battlefield."
                result = registry.execute(registry.plan("open Roblox Studio project devils battlefield"))

            self.assertEqual(result.name, "open_editor_project")
            open_project.assert_called_once_with("Roblox Studio", "devils battlefield")

    def test_roblox_game_commands_route_to_roblox_launcher(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "open_roblox_game") as open_game:
                open_game.return_value = "Opening Roblox game: Arsenal."
                result = registry.execute(registry.plan("open Arsenal on Roblox"))

            self.assertEqual(result.name, "open_roblox_game")
            open_game.assert_called_once_with("Arsenal")

            with patch.object(registry.convenience, "open_roblox_game") as open_game:
                open_game.return_value = "I do not have Devil Hunters saved yet, so I opened Roblox search for it."
                result = registry.execute(registry.plan("Open Devil Hunters on Roblox."))

            self.assertEqual(result.name, "open_roblox_game")
            open_game.assert_called_once_with("Devil Hunters")

            with patch.object(registry.convenience, "open_roblox_game") as open_game:
                open_game.return_value = "Opening Roblox game: Dress To Impress."
                result = registry.execute(registry.plan("launch Roblox game Dress To Impress"))

            self.assertEqual(result.name, "open_roblox_game")
            open_game.assert_called_once_with("Dress To Impress")

    def test_screen_commands_route_to_screen_reader(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "read_screen") as read_screen:
                read_screen.return_value = "I captured your screen."
                result = registry.execute(registry.plan("what's on my screen"))

            self.assertEqual(result.name, "read_screen")
            read_screen.assert_called_once_with()

    def test_safe_ui_commands_route_to_controller(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "safe_ui_click") as click:
                click.return_value = "Clicked Continue."
                result = registry.execute(registry.plan("click continue"))

            self.assertEqual(result.name, "safe_ui_click")
            click.assert_called_once_with("continue")

    def test_lobby_followup_routes_to_current_lobby_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "take_me_to_lobby") as lobby:
                lobby.return_value = "Taking you to the Apex Legends lobby."
                result = registry.execute(registry.plan("take me to lobby"))

            self.assertEqual(result.name, "take_me_to_lobby")
            lobby.assert_called_once_with()

    def test_named_lobby_request_routes_to_that_game_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "take_me_to_lobby") as lobby:
                lobby.return_value = "Taking you to the Apex Legends lobby."
                result = registry.execute(registry.plan("Take Apex Legends to lobby"))

            self.assertEqual(result.name, "take_me_to_lobby")
            lobby.assert_called_once_with("apex legends")

    def test_improvement_commands_route_to_queue_helpers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "list_improvements") as list_improvements:
                list_improvements.return_value = "Queued Damien upgrades."
                result = registry.execute(registry.plan("show improvement queue"))

            self.assertEqual(result.name, "list_improvements")
            list_improvements.assert_called_once_with()

            with patch.object(registry.convenience, "prepare_latest_improvement_task") as prepare:
                prepare.return_value = "Codex upgrade task ready."
                result = registry.execute(registry.plan("ask Codex to upgrade that"))

            self.assertEqual(result.name, "prepare_latest_improvement_task")
            prepare.assert_called_once_with()

            with patch.object(registry.convenience, "retry_latest_failed_command") as retry:
                retry.return_value = "The last failed command still needs an upgrade."
                result = registry.execute(registry.plan("retry last failed command"))

            self.assertEqual(result.name, "retry_latest_failed_command")
            retry.assert_called_once_with()

    def test_itunes_playlist_commands_route_to_music_control(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "play_itunes_playlist") as play_playlist:
                play_playlist.return_value = "Shuffling iTunes playlist: workout."
                result = registry.execute(registry.plan("shuffle my workout playlist"))

            self.assertEqual(result.name, "itunes_playlist")
            self.assertIn("Shuffling", result.content)
            play_playlist.assert_called_once_with("workout", shuffle=True)

            with patch.object(registry.convenience, "play_itunes_playlist") as play_playlist:
                play_playlist.return_value = "Playing iTunes playlist: chill."
                result = registry.execute(registry.plan("play chill playlist"))

            self.assertEqual(result.name, "itunes_playlist")
            play_playlist.assert_called_once_with("chill", shuffle=False)

    def test_itunes_playlist_commands_accept_natural_word_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch.object(registry.convenience, "play_itunes_playlist") as play_playlist:
                play_playlist.return_value = "Shuffling iTunes playlist: gym."
                result = registry.execute(registry.plan("shuffle playlist gym"))

            self.assertEqual(result.name, "itunes_playlist")
            play_playlist.assert_called_once_with("gym", shuffle=True)

            with patch.object(registry.convenience, "play_itunes_playlist") as play_playlist:
                play_playlist.return_value = "Shuffling iTunes playlist: late night."
                result = registry.execute(registry.plan("shuffle late night"))

            self.assertEqual(result.name, "itunes_playlist")
            play_playlist.assert_called_once_with("late night", shuffle=True)

    def test_vague_playlist_command_does_not_fall_back_to_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            result = registry.execute(registry.plan("shuffle another playlist"))

            self.assertEqual(result.name, "missing_playlist_name")
            self.assertIn("Which iTunes playlist", result.content)

    def test_vague_crunchyroll_command_does_not_search_bogus_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            result = registry.execute(registry.plan("continue watching"))

            self.assertEqual(result.name, "missing_crunchyroll_title")
            self.assertIn("Which Crunchyroll title", result.content)

    def test_copies_user_text_to_clipboard(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch("jarvis_assistant.convenience.subprocess.Popen") as popen:
                popen.return_value.communicate.return_value = ("", "")
                result = registry.execute(registry.plan("copy hello there to clipboard"))

            self.assertIn("Copied", result.content)
            popen.assert_called_once()

    def test_opens_only_approved_project_area(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            with patch("jarvis_assistant.convenience.subprocess.Popen") as popen:
                result = registry.execute(registry.plan("open notes folder"))

            self.assertIn("Opened notes", result.content)
            popen.assert_called_once()

    def test_mascot_phrases_do_not_launch_vpet(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            result = registry.execute(registry.plan("open Damien mascot"))
            self.assertEqual(result.name, "mascot_ui_info")
            self.assertIn("not a separate VPet launcher", result.content)

            result = registry.execute(registry.plan("bring up the butler"))
            self.assertEqual(result.name, "mascot_ui_info")

    def test_command_routing_scenario_matrix(self):
        scenarios = {
            "open notepad": "open_approved_app",
            "launch notepad": "open_approved_app",
            "start notepad": "open_approved_app",
            "close notepad": "close_approved_app",
            "quit notepad": "close_approved_app",
            "stop notepad": "close_approved_app",
            "what apps can you open": "list_approved_apps",
            "list approved apps": "list_approved_apps",
            "approved apps": "list_approved_apps",
            "pause": "media_control",
            "pause music": "media_control",
            "resume": "media_control",
            "unpause my video": "media_control",
            "play some music": "media_control",
            "play a song": "media_control",
            "next": "media_control",
            "next track": "media_control",
            "skip song": "media_control",
            "play next song": "media_control",
            "previous song": "media_control",
            "play previous track": "media_control",
            "call Alex on Discord": "discord_call",
            "discord call the group chat": "discord_call",
            "call m": "discord_call",
            "answer Discord call": "discord_answer_call",
            "accept call on Discord": "discord_answer_call",
            "open RunBuildTest in Unreal Engine": "open_editor_project",
            "open Roblox Studio project devils battlefield": "open_editor_project",
            "open Arsenal on Roblox": "open_roblox_game",
            "launch Roblox game Dress To Impress": "open_roblox_game",
            "read my screen": "read_screen",
            "what's on my screen": "read_screen",
            "take a screenshot": "read_screen",
            "click continue": "safe_ui_click",
            "press launch": "safe_ui_click",
            "take me to lobby": "take_me_to_lobby",
            "take to the lobby": "take_me_to_lobby",
            "take Apex Legends to lobby": "take_me_to_lobby",
            "show improvement queue": "list_improvements",
            "what did you fail to do": "list_improvements",
            "ask Codex to upgrade that": "prepare_latest_improvement_task",
            "retry last failed command": "retry_latest_failed_command",
            "open Damien mascot": "mascot_ui_info",
            "bring up the butler": "mascot_ui_info",
            "shuffle workout": "itunes_playlist",
            "shuffle workout playlist": "itunes_playlist",
            "shuffle playlist workout": "itunes_playlist",
            "play playlist chill": "itunes_playlist",
            "play chill playlist": "itunes_playlist",
            "shuffle another playlist": "missing_playlist_name",
            "continue watching": "missing_crunchyroll_title",
            "resume crunchyroll": "missing_crunchyroll_title",
            "watch One Piece": "crunchyroll_title",
            "continue One Piece": "crunchyroll_title",
            "play One Piece on crunchyroll": "crunchyroll_title",
            "set crunchyroll profile to Damien": "set_crunchyroll_profile",
            "copy hello to clipboard": "copy_to_clipboard",
            "put hello on the clipboard": "copy_to_clipboard",
            "take note call dentist": "add_note",
            "make a note that buy milk": "add_note",
            "show my notes": "list_notes",
            "what time is it": "local_time",
            "open notes folder": "open_project_area",
            "open settings folder": "open_project_area",
            "search documents for arc reactor": "search_approved_files",
            "look up online Python news": "web_search",
            "system status": "system_status",
            "gaming mode": "quick_mode",
            "delete all files": "blocked_high_risk_action",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = self._registry(Path(temp_dir))

            for command, expected in scenarios.items():
                with self.subTest(command=command):
                    planned = registry.plan(command)
                    self.assertIsNotNone(planned)
                    self.assertEqual(planned.name, expected)


if __name__ == "__main__":
    unittest.main()
