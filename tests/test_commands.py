import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess

from jarvis_assistant.commands import ApprovedApp, CommandDispatcher, _desktop_apps


class CommandDispatcherTests(unittest.TestCase):
    def test_opens_only_approved_app(self):
        dispatcher = CommandDispatcher({"notepad": ApprovedApp("Notepad", "notepad.exe")})

        with patch("jarvis_assistant.commands.subprocess.Popen") as popen:
            result = dispatcher.try_handle("open notepad")

        self.assertEqual(result, "Opening Notepad.")
        popen.assert_called_once_with(["notepad.exe"], shell=False)

    def test_rejects_unapproved_app(self):
        dispatcher = CommandDispatcher({"notepad": ApprovedApp("Notepad", "notepad.exe")})

        with patch("jarvis_assistant.commands.subprocess.Popen") as popen:
            result = dispatcher.try_handle("open powershell")

        self.assertIn("I can only open approved apps", result)
        popen.assert_not_called()

    def test_ignores_non_command_text(self):
        dispatcher = CommandDispatcher({})

        self.assertIsNone(dispatcher.try_handle("what is the weather?"))

    def test_opens_windows_shortcut_with_native_launcher(self):
        dispatcher = CommandDispatcher({"apex legends": ApprovedApp("Apex Legends", r"C:\Users\kaish\Desktop\Apex Legends.url")})

        with patch("jarvis_assistant.commands.os.startfile") as startfile, patch("jarvis_assistant.commands.subprocess.Popen") as popen, patch(
            "jarvis_assistant.commands.schedule_lobby_entry"
        ) as lobby:
            result = dispatcher.try_handle("open Apex Legends")

        self.assertEqual(result, "Opening Apex Legends. I will monitor the screen until the lobby is confirmed.")
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Apex Legends.url")
        popen.assert_not_called()
        lobby.assert_called_once_with("apex legends")

    def test_opens_marvel_rivals_and_schedules_lobby_entry(self):
        dispatcher = CommandDispatcher({"marvel rivals": ApprovedApp("Marvel Rivals", r"C:\Users\kaish\Desktop\Marvel Rivals.url")})

        with patch("jarvis_assistant.commands.os.startfile") as startfile, patch(
            "jarvis_assistant.commands.schedule_lobby_entry"
        ) as lobby:
            result = dispatcher.try_handle("launch Marvel Rivals")

        self.assertEqual(result, "Opening Marvel Rivals. I will monitor the screen until the lobby is confirmed.")
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Marvel Rivals.url")
        lobby.assert_called_once_with("marvel rivals")

    def test_opens_multiple_approved_apps_from_one_command(self):
        dispatcher = CommandDispatcher(
            {
                "notepad": ApprovedApp("Notepad", "notepad.exe"),
                "chrome": ApprovedApp("Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                "discord": ApprovedApp("Discord", r"C:\Users\kaish\Desktop\Discord.lnk"),
            }
        )

        with patch("jarvis_assistant.commands.os.startfile") as startfile, patch("jarvis_assistant.commands.subprocess.Popen") as popen:
            result = dispatcher.try_handle("open chrome, discord and notepad")

        self.assertEqual(result, "Opening Google Chrome, Discord, and Notepad.")
        popen.assert_any_call([r"C:\Program Files\Google\Chrome\Application\chrome.exe"], shell=False)
        popen.assert_any_call(["notepad.exe"], shell=False)
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Discord.lnk")

    def test_closes_approved_app_by_process_name(self):
        dispatcher = CommandDispatcher({"notepad": ApprovedApp("Notepad", "notepad.exe", process_names=("notepad.exe",))})

        with patch("jarvis_assistant.commands.subprocess.run", return_value=CompletedProcess([], 0)) as run:
            result = dispatcher.try_handle("close notepad")

        self.assertEqual(result, "Closing Notepad.")
        run.assert_called_once()
        args = run.call_args.args[0]
        self.assertEqual(args[:4], ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"])
        self.assertIn("notepad", args[-1])

    def test_closes_multiple_approved_apps_from_one_command(self):
        dispatcher = CommandDispatcher(
            {
                "notepad": ApprovedApp("Notepad", "notepad.exe", process_names=("notepad.exe",)),
                "chrome": ApprovedApp("Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe", process_names=("chrome.exe",)),
            }
        )

        with patch("jarvis_assistant.commands.subprocess.run", return_value=CompletedProcess([], 0)) as run:
            result = dispatcher.try_handle("close chrome and notepad")

        self.assertEqual(result, "Closing Google Chrome and Notepad.")
        self.assertEqual(run.call_count, 2)

    def test_close_reports_when_app_is_not_running(self):
        dispatcher = CommandDispatcher({"notepad": ApprovedApp("Notepad", "notepad.exe", process_names=("notepad.exe",))})

        with patch("jarvis_assistant.commands.subprocess.run", return_value=CompletedProcess([], 128)):
            result = dispatcher.try_handle("close notepad")

        self.assertEqual(result, "Notepad does not appear to be running.")

    def test_close_reports_unknown_process_name(self):
        dispatcher = CommandDispatcher({"web game": ApprovedApp("Web Game", r"C:\Users\kaish\Desktop\Web Game.url")})

        with patch("jarvis_assistant.commands.subprocess.run") as run:
            result = dispatcher.try_handle("close web game")

        self.assertEqual(result, "I can open Web Game, but I do not know its Windows process name yet.")
        run.assert_not_called()

    def test_multiple_app_open_reports_confirmation_and_unknowns(self):
        dispatcher = CommandDispatcher(
            {
                "notepad": ApprovedApp("Notepad", "notepad.exe"),
                "powershell": ApprovedApp("PowerShell", "powershell.exe", requires_confirmation=True),
            }
        )

        with patch("jarvis_assistant.commands.subprocess.Popen") as popen:
            result = dispatcher.try_handle("open notepad and powershell and mystery app")

        self.assertEqual(
            result,
            "Opening Notepad. Confirmation required before opening PowerShell. Denied: I could not find approved apps for mystery.",
        )
        popen.assert_called_once_with(["notepad.exe"], shell=False)

    def test_multiple_app_split_preserves_multi_word_app_names(self):
        dispatcher = CommandDispatcher(
            {
                "visual studio code": ApprovedApp("Visual Studio Code", r"C:\Users\kaish\Desktop\Visual Studio Code.lnk"),
                "task manager": ApprovedApp("Task Manager", "taskmgr.exe"),
            }
        )

        with patch("jarvis_assistant.commands.os.startfile") as startfile, patch("jarvis_assistant.commands.subprocess.Popen") as popen:
            result = dispatcher.try_handle("open visual studio code and task manager")

        self.assertEqual(result, "Opening Visual Studio Code and Task Manager.")
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Visual Studio Code.lnk")
        popen.assert_called_once_with(["taskmgr.exe"], shell=False)

    def test_multiple_app_split_accepts_then_and_also(self):
        dispatcher = CommandDispatcher(
            {
                "chrome": ApprovedApp("Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                "discord": ApprovedApp("Discord", r"C:\Users\kaish\Desktop\Discord.lnk"),
                "notepad": ApprovedApp("Notepad", "notepad.exe"),
            }
        )

        with patch("jarvis_assistant.commands.os.startfile") as startfile, patch("jarvis_assistant.commands.subprocess.Popen") as popen:
            result = dispatcher.try_handle("open chrome then discord also notepad")

        self.assertEqual(result, "Opening Google Chrome, Discord, and Notepad.")
        popen.assert_any_call([r"C:\Program Files\Google\Chrome\Application\chrome.exe"], shell=False)
        popen.assert_any_call(["notepad.exe"], shell=False)
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Discord.lnk")

    def test_close_multiple_app_split_accepts_commas_then_and_also(self):
        dispatcher = CommandDispatcher(
            {
                "chrome": ApprovedApp("Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe", process_names=("chrome.exe",)),
                "discord": ApprovedApp("Discord", r"C:\Users\kaish\Desktop\Discord.lnk", process_names=("Discord.exe",)),
                "notepad": ApprovedApp("Notepad", "notepad.exe", process_names=("notepad.exe",)),
            }
        )

        with patch("jarvis_assistant.commands.subprocess.run", return_value=CompletedProcess([], 0)) as run:
            result = dispatcher.try_handle("close chrome, discord then also notepad")

        self.assertEqual(result, "Closing Google Chrome, Discord, and Notepad.")
        self.assertEqual(run.call_count, 3)

    def test_fuzzy_matches_speech_recognition_app_name(self):
        dispatcher = CommandDispatcher({"apex legends": ApprovedApp("Apex Legends", r"C:\Users\kaish\Desktop\Apex Legends.url")})

        with patch("jarvis_assistant.commands.os.startfile") as startfile, patch("jarvis_assistant.commands.schedule_lobby_entry"):
            result = dispatcher.try_handle("Open APEG's Legends.")

        self.assertEqual(result, "Opening Apex Legends. I will monitor the screen until the lobby is confirmed.")
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Apex Legends.url")

    def test_normalizes_common_app_aliases(self):
        dispatcher = CommandDispatcher(
            {
                "itunes": ApprovedApp("iTunes", r"C:\Program Files\iTunes\iTunes.exe"),
                "crunchyroll": ApprovedApp("Crunchyroll", r"C:\Users\kaish\Desktop\Crunchyroll - Watch Popular Anime.lnk"),
            }
        )

        with patch("jarvis_assistant.commands.subprocess.Popen") as popen:
            self.assertEqual(dispatcher.try_handle("open the i tunes app"), "Opening iTunes.")
        popen.assert_called_once_with([r"C:\Program Files\iTunes\iTunes.exe"], shell=False)

        with patch("jarvis_assistant.commands.os.startfile") as startfile:
            self.assertEqual(dispatcher.try_handle("launch crunchy roll"), "Opening Crunchyroll.")
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Crunchyroll - Watch Popular Anime.lnk")

    def test_from_file_creates_default_allowlist_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config" / "approved_apps.json"

            dispatcher = CommandDispatcher.from_file(path)

            self.assertTrue(path.exists())
            self.assertIn("notepad", dispatcher.apps)

    def test_from_file_adds_important_apps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config" / "approved_apps.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"apps": {}}', encoding="utf-8")

            dispatcher = CommandDispatcher.from_file(path)

        self.assertIn("settings", dispatcher.apps)
        self.assertIn("task manager", dispatcher.apps)

    def test_desktop_apps_discovers_launchable_items_and_aliases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            desktop = Path(temp_dir)
            (desktop / "Apex Legends.url").write_text("[InternetShortcut]\nURL=steam://rungameid/1172470\n", encoding="utf-8")
            (desktop / "Minecraft Launcher.lnk").write_bytes(b"shortcut")
            (desktop / "Azgaar's Fantasy Map Generator.lnk").write_bytes(b"shortcut")
            (desktop / "https   pwa.zoom.us wc.lnk").write_bytes(b"shortcut")
            (desktop / "Visual Studio Code.lnk").write_bytes(b"shortcut")
            (desktop / "BeamNG.drive.url").write_text("[InternetShortcut]\nURL=steam://rungameid/284160\n", encoding="utf-8")
            (desktop / "Crunchyroll - Watch Popular Anime.lnk").write_bytes(b"shortcut")
            (desktop / "Damien.lnk").write_bytes(b"shortcut")
            (desktop / "notes.txt").write_text("ignore me", encoding="utf-8")

            apps = _desktop_apps(desktop)

        self.assertIn("apex legends", apps)
        self.assertIn("minecraft", apps)
        self.assertIn("map generator", apps)
        self.assertIn("zoom", apps)
        self.assertIn("visual studio code", apps)
        self.assertIn("beamng", apps)
        self.assertIn("crunchy anime", apps)
        self.assertNotIn("damien", apps)
        self.assertNotIn("notes", apps)

    def test_resolves_similar_desktop_app_references(self):
        dispatcher = CommandDispatcher(
            {
                "azgaars fantasy map generator": ApprovedApp("Azgaar's Fantasy Map Generator", r"C:\Users\kaish\Desktop\Azgaar's Fantasy Map Generator.lnk"),
                "zoom": ApprovedApp("Zoom", r"C:\Users\kaish\Desktop\https   pwa.zoom.us wc.lnk"),
                "visual studio code": ApprovedApp("Visual Studio Code", r"C:\Users\kaish\Desktop\Visual Studio Code.lnk"),
                "beamng drive": ApprovedApp("BeamNG.drive", r"C:\Users\kaish\Desktop\BeamNG.drive.url"),
                "crunchyroll watch popular anime": ApprovedApp("Crunchyroll", r"C:\Users\kaish\Desktop\Crunchyroll - Watch Popular Anime.lnk"),
            }
        )

        with patch("jarvis_assistant.commands.os.startfile") as startfile:
            self.assertEqual(dispatcher.try_handle("open map generator"), "Opening Azgaar's Fantasy Map Generator.")
            self.assertEqual(dispatcher.try_handle("open zoom"), "Opening Zoom.")
            self.assertEqual(dispatcher.try_handle("open vs code"), "Opening Visual Studio Code.")
            self.assertEqual(dispatcher.try_handle("open bng"), "Opening BeamNG.drive.")
            self.assertEqual(dispatcher.try_handle("open crunchy anime"), "Opening Crunchyroll.")

        self.assertEqual(startfile.call_count, 5)

    def test_opens_windows_uri_with_native_launcher(self):
        dispatcher = CommandDispatcher({"settings": ApprovedApp("Windows Settings", "ms-settings:")})

        with patch("jarvis_assistant.commands.os.startfile") as startfile:
            result = dispatcher.try_handle("open settings")

        self.assertEqual(result, "Opening Windows Settings.")
        startfile.assert_called_once_with("ms-settings:")


if __name__ == "__main__":
    unittest.main()
