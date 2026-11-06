from __future__ import annotations

import json
import subprocess
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path

from .browser_control import BrowserAutomationError, ChromeController
from .discord_control import DiscordCallController
from .game_lobby import SafeUiController, run_lobby_entry_now
from .improvement import ImprovementQueue
from .project_opening import ProjectOpener
from .roblox_games import RobloxGameLauncher
from .runtime import APP_ROOT
from .screen_access import ScreenReader


class ConvenienceTools:
    def __init__(self, root: Path = APP_ROOT) -> None:
        self.root = root
        self.notes_path = root / "notes" / "damien_notes.jsonl"

    def open_web(self, query_or_url: str) -> str:
        target = query_or_url.strip()
        if not target:
            return "I need a site or search phrase to open."
        if not target.startswith(("http://", "https://")):
            if "." in target and " " not in target:
                target = "https://" + target
            else:
                target = "https://duckduckgo.com/?q=" + urllib.parse.quote(target)
        webbrowser.open(target)
        return f"Opened: {target}"

    def open_crunchyroll_title(self, title: str) -> str:
        value = title.strip(" .")
        if not value:
            return "I need a show title to open in Crunchyroll."
        settings = self._settings_payload()
        if settings and settings.get("crunchyroll_browser_automation_enabled", True):
            profile_name = str(settings.get("crunchyroll_profile_name", "")).strip()
            port = int(settings.get("crunchyroll_browser_port", 9223))
            controller = ChromeController(self.root / "browser_profiles" / "crunchyroll", port=port)
            try:
                return controller.open_crunchyroll_title(value, profile_name=profile_name)
            except BrowserAutomationError as exc:
                url = "https://www.crunchyroll.com/search?q=" + urllib.parse.quote(value)
                webbrowser.open(url)
                return f"Crunchyroll browser control was unavailable ({exc}), so I opened search for {value}."
        url = "https://www.crunchyroll.com/search?q=" + urllib.parse.quote(value)
        webbrowser.open(url)
        return f"Opened Crunchyroll for {value}. If you are signed in, use the result or Continue Watching entry."

    def set_crunchyroll_profile(self, profile_name: str) -> str:
        value = profile_name.strip(" .")
        if not value:
            return "I need the Crunchyroll profile name to save."
        self._update_settings({"crunchyroll_profile_name": value})
        return f"Crunchyroll profile set to {value}."

    def play_itunes_playlist(self, playlist_name: str, shuffle: bool = False) -> str:
        value = playlist_name.strip(" .")
        if not value:
            return "I need a playlist name."
        try:
            import win32com.client  # type: ignore[import-not-found]
        except Exception:
            self.open_web("itunes")
            return "iTunes automation is unavailable here, so I opened iTunes instead."
        try:
            app = win32com.client.Dispatch("iTunes.Application")
            playlist = _find_itunes_playlist(app, value)
            if playlist is None:
                return f"I could not find an iTunes playlist named {value}."
            actual_name = str(getattr(playlist, "Name", value))
            try:
                app.Stop()
            except Exception:
                pass
            _select_itunes_playlist(app, playlist)
            if shuffle and hasattr(playlist, "Shuffle"):
                playlist.Shuffle = True
            playlist.PlayFirstTrack()
            mode = "Shuffling" if shuffle else "Playing"
            return f"{mode} iTunes playlist: {actual_name}."
        except Exception as exc:
            return f"iTunes playlist control failed: {exc}"

    def media_control(self, action: str) -> str:
        keys = {
            "pause": 0xB3,
            "play": 0xB3,
            "resume": 0xB3,
            "next": 0xB0,
            "previous": 0xB1,
            "back": 0xB1,
        }
        key = keys.get(action.lower())
        if key is None:
            return f"I do not know the media command {action}."
        try:
            import win32api  # type: ignore[import-not-found]
            import win32con  # type: ignore[import-not-found]

            win32api.keybd_event(key, 0, 0, 0)
            win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
            return f"Media {action}."
        except Exception as exc:
            return f"Media control failed: {exc}"

    def discord_call(self, target: str) -> str:
        return DiscordCallController(self.root).call(target)

    def discord_answer_call(self) -> str:
        return DiscordCallController(self.root).answer_call()

    def open_editor_project(self, editor: str, project_name: str) -> str:
        return ProjectOpener(self.root).open_project(editor, project_name)

    def open_roblox_game(self, game_name: str) -> str:
        return RobloxGameLauncher(self.root).open_game(game_name)

    def read_screen(self) -> str:
        return ScreenReader(self.root).understand_screen("read my screen")

    def click_ui_button(self, label: str) -> str:
        return ScreenReader(self.root).click_visible_button(label)

    def safe_ui_click(self, label: str) -> str:
        return SafeUiController().click_known_button(label)

    def take_me_to_lobby(self, app_name: str | None = None) -> str:
        return run_lobby_entry_now(app_name, root=self.root)

    def list_improvements(self) -> str:
        return ImprovementQueue(self.root).summary()

    def prepare_latest_improvement_task(self) -> str:
        try:
            path = ImprovementQueue(self.root).prepare_latest_task()
        except RuntimeError as exc:
            return str(exc)
        return f"Codex upgrade task ready: {path}"

    def retry_latest_failed_command(self) -> str:
        return ImprovementQueue(self.root).retry_latest_message()

    def copy_to_clipboard(self, text: str) -> str:
        value = text.strip()
        if not value:
            return "I need text to copy."
        process = subprocess.Popen(["clip.exe"], stdin=subprocess.PIPE, text=True)
        process.communicate(value)
        return "Copied to clipboard."

    def add_note(self, text: str) -> str:
        value = text.strip()
        if not value:
            return "I need note text to save."
        self.notes_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"created_at": datetime.now().isoformat(timespec="seconds"), "content": value}
        with self.notes_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload) + "\n")
        return f"Saved note: {value}"

    def list_notes(self, limit: int = 10) -> str:
        if not self.notes_path.exists():
            return "No local notes yet."
        notes = []
        for line in self.notes_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                notes.append(json.loads(line))
        if not notes:
            return "No local notes yet."
        lines = [f"- {note.get('created_at', '')}: {note.get('content', '')}" for note in notes[-limit:]]
        return "Recent local notes:\n" + "\n".join(lines)

    def local_time(self) -> str:
        return "Local time: " + datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

    def open_project_area(self, area: str) -> str:
        areas = {
            "documents": self.root / "approved_documents",
            "approved documents": self.root / "approved_documents",
            "notes": self.root / "notes",
            "logs": self.root / "logs",
            "settings": self.root / "config",
            "config": self.root / "config",
        }
        key = area.strip().lower()
        path = areas.get(key)
        if path is None:
            approved = ", ".join(sorted(areas))
            return f"Denied: I can open approved project areas only. Approved areas: {approved}."
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer.exe", str(path)], shell=False)
        return f"Opened {key}: {path}"

    def _settings_payload(self) -> dict[str, object]:
        path = self.root / "config" / "settings.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _update_settings(self, values: dict[str, object]) -> None:
        path = self.root / "config" / "settings.json"
        payload = self._settings_payload()
        payload.update(values)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _find_itunes_playlist(app: object, playlist_name: str) -> object | None:
    requested = playlist_name.casefold()
    sources = getattr(app, "Sources", None)
    if sources is None:
        library = getattr(app, "LibrarySource", None)
        playlists = getattr(library, "Playlists", None) if library is not None else None
        return _playlist_by_name(playlists, requested)
    for source_index in range(1, int(sources.Count) + 1):
        source = sources.Item(source_index)
        playlist = _playlist_by_name(getattr(source, "Playlists", None), requested)
        if playlist is not None:
            return playlist
    return None


def _select_itunes_playlist(app: object, playlist: object) -> None:
    try:
        browser_window = getattr(app, "BrowserWindow", None)
        if browser_window is not None:
            browser_window.SelectedPlaylist = playlist
    except Exception:
        pass
    try:
        playlist.Reveal()
    except Exception:
        pass


def _playlist_by_name(playlists: object | None, requested: str) -> object | None:
    if playlists is None:
        return None
    for index in range(1, int(playlists.Count) + 1):
        playlist = playlists.Item(index)
        if str(getattr(playlist, "Name", "")).casefold() == requested:
            return playlist
    return None
