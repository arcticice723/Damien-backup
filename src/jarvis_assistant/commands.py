from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .game_lobby import has_lobby_profile, schedule_lobby_entry


DESKTOP_LAUNCH_EXTENSIONS = {".lnk", ".url", ".exe", ".bat", ".cmd"}
DESKTOP_EXCLUDE_NAMES = {"desktop", "damien"}


@dataclass(frozen=True)
class ApprovedApp:
    display_name: str
    command: str
    requires_confirmation: bool = False
    process_names: tuple[str, ...] = ()


class CommandDispatcher:
    OPEN_APP_PATTERN = re.compile(r"^\s*(?:open|launch|start)\s+(?P<name>.+?)\s*$", re.IGNORECASE)
    CLOSE_APP_PATTERN = re.compile(r"^\s*(?:close|quit|exit|stop)\s+(?P<name>.+?)\s*$", re.IGNORECASE)

    def __init__(self, apps: dict[str, ApprovedApp]) -> None:
        self.apps = apps

    @classmethod
    def from_file(cls, path: Path) -> "CommandDispatcher":
        if not path.exists():
            _write_default_approved_apps(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        apps = _important_apps()
        apps.update(
            {
                key.lower(): ApprovedApp(
                    display_name=value["display_name"],
                    command=value["command"],
                    requires_confirmation=bool(value.get("requires_confirmation", False)),
                    process_names=tuple(value.get("process_names", [])),
                )
                for key, value in payload.get("apps", {}).items()
            }
        )
        apps.update(_desktop_apps())
        return cls(apps)

    def tool_specs(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "open_approved_app",
                    "description": "Open a Windows application only if it is present in Damien's approved app allowlist.",
                    "parameters": {
                        "type": "object",
                        "required": ["app_name"],
                        "properties": {
                            "app_name": {
                                "type": "string",
                                "description": "Approved app name such as notepad, calculator, or paint.",
                            }
                        },
                    },
                },
            }
        ]

    def try_handle_text(self, text: str) -> str | None:
        match = self.OPEN_APP_PATTERN.match(text)
        if match:
            return self.open_approved_apps(match.group("name").strip().lower())
        match = self.CLOSE_APP_PATTERN.match(text)
        if match:
            return self.close_approved_apps(match.group("name").strip().lower())
        return None

    def try_handle(self, text: str) -> str | None:
        return self.try_handle_text(text)

    def run_tool_call(self, tool_call: dict) -> str:
        function = tool_call.get("function", {})
        if function.get("name") != "open_approved_app":
            return "Denied: that tool is not approved."
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        return self.open_approved_apps(str(arguments.get("app_name", "")).lower().strip())

    def open_approved_app(self, requested_name: str) -> str:
        resolved_name, app = self._resolve_app(requested_name)
        if app is None:
            approved = ", ".join(sorted(self.apps))
            return f"Denied: I can only open approved apps. Approved apps are: {approved}."
        if app.requires_confirmation:
            return f"Confirmation required before opening {app.display_name}."
        if app.command.lower().endswith((".lnk", ".url")) or _is_windows_uri(app.command):
            os.startfile(app.command)
        else:
            subprocess.Popen([app.command], shell=False)
        if resolved_name and has_lobby_profile(resolved_name):
            schedule_lobby_entry(resolved_name)
            return f"Opening {app.display_name}. I will monitor the screen until the lobby is confirmed."
        return f"Opening {app.display_name}."

    def open_approved_apps(self, requested_names: str) -> str:
        names = self._split_requested_apps(requested_names)
        if len(names) <= 1:
            return self.open_approved_app(requested_names)

        opened: list[str] = []
        confirmations: list[str] = []
        denied: list[str] = []
        monitoring_lobby = False
        for name in names:
            resolved_name, app = self._resolve_app(name)
            if app is None:
                denied.append(name)
                continue
            if app.requires_confirmation:
                confirmations.append(app.display_name)
                continue
            if app.command.lower().endswith((".lnk", ".url")) or _is_windows_uri(app.command):
                os.startfile(app.command)
            else:
                subprocess.Popen([app.command], shell=False)
            if resolved_name and has_lobby_profile(resolved_name):
                schedule_lobby_entry(resolved_name)
                monitoring_lobby = True
            opened.append(app.display_name)

        parts: list[str] = []
        if opened:
            parts.append(f"Opening {_join_display_names(opened)}.")
            if monitoring_lobby:
                parts.append("I will monitor the screen until the lobby is confirmed.")
        if confirmations:
            parts.append(f"Confirmation required before opening {_join_display_names(confirmations)}.")
        if denied:
            parts.append(f"Denied: I could not find approved apps for {_join_display_names(denied)}.")
        if not parts:
            approved = ", ".join(sorted(self.apps))
            return f"Denied: I can only open approved apps. Approved apps are: {approved}."
        return " ".join(parts)

    def close_approved_app(self, requested_name: str) -> str:
        resolved_name, app = self._resolve_app(requested_name)
        if app is None:
            approved = ", ".join(sorted(self.apps))
            return f"Denied: I can only close approved apps. Approved apps are: {approved}."
        process_names = _process_names_for_app(resolved_name or requested_name, app)
        if not process_names:
            return f"I can open {app.display_name}, but I do not know its Windows process name yet."
        closed = _close_processes(process_names)
        if closed:
            return f"Closing {app.display_name}."
        return f"{app.display_name} does not appear to be running."

    def close_approved_apps(self, requested_names: str) -> str:
        names = self._split_requested_apps(requested_names)
        if len(names) <= 1:
            return self.close_approved_app(requested_names)

        closed: list[str] = []
        not_running: list[str] = []
        unknown_process: list[str] = []
        denied: list[str] = []
        for name in names:
            resolved_name, app = self._resolve_app(name)
            if app is None:
                denied.append(name)
                continue
            process_names = _process_names_for_app(resolved_name or name, app)
            if not process_names:
                unknown_process.append(app.display_name)
                continue
            if _close_processes(process_names):
                closed.append(app.display_name)
            else:
                not_running.append(app.display_name)

        parts: list[str] = []
        if closed:
            parts.append(f"Closing {_join_display_names(closed)}.")
        if not_running:
            parts.append(f"{_join_display_names(not_running)} did not appear to be running.")
        if unknown_process:
            parts.append(f"I do not know the process name for {_join_display_names(unknown_process)} yet.")
        if denied:
            parts.append(f"Denied: I could not find approved apps for {_join_display_names(denied)}.")
        if not parts:
            approved = ", ".join(sorted(self.apps))
            return f"Denied: I can only close approved apps. Approved apps are: {approved}."
        return " ".join(parts)

    def _split_requested_apps(self, requested_names: str) -> list[str]:
        requested = requested_names.strip()
        if not requested:
            return []
        protected: dict[str, str] = {}
        for index, app_name in enumerate(sorted(self.apps, key=len, reverse=True)):
            normalized = _normalize_app_name(app_name)
            if not normalized or " " not in normalized:
                continue
            token = f"__APP{index}__"
            pattern = re.compile(rf"\b{re.escape(normalized)}\b", re.IGNORECASE)
            if pattern.search(requested):
                protected[token] = normalized
                requested = pattern.sub(token, requested)
        raw_parts = re.split(r"\s*(?:,|;|&|\+|\band\b|\bthen\b|\balso\b)\s*", requested, flags=re.IGNORECASE)
        parts: list[str] = []
        for part in raw_parts:
            value = part.strip()
            if not value:
                continue
            for token, original in protected.items():
                value = value.replace(token, original)
            value = _normalize_app_name(value)
            if value:
                parts.append(value)
        return parts

    def _resolve_app(self, requested_name: str) -> tuple[str | None, ApprovedApp | None]:
        requested = _normalize_app_name(requested_name)
        if requested in self.apps:
            return requested, self.apps[requested]

        normalized_apps = {_normalize_app_name(name): (name, app) for name, app in self.apps.items()}
        if requested in normalized_apps:
            return normalized_apps[requested]

        compact_requested = requested.replace(" ", "")
        for normalized_name, entry in normalized_apps.items():
            compact_name = normalized_name.replace(" ", "")
            if compact_requested == compact_name:
                return entry

        prefix_matches = [
            entry for normalized_name, entry in normalized_apps.items()
            if normalized_name.startswith(requested) or requested.startswith(normalized_name)
        ]
        if len(prefix_matches) == 1:
            return prefix_matches[0]

        scored = sorted(
            (
                (_candidate_score(requested, normalized_name), normalized_name, entry)
                for normalized_name, entry in normalized_apps.items()
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        if scored and scored[0][0] >= 0.72:
            runner_up = scored[1][0] if len(scored) > 1 else 0.0
            if scored[0][0] >= 0.88 or scored[0][0] - runner_up >= 0.08:
                return scored[0][2]
        return None, None


def _normalize_app_name(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"\b(?:please|the|app|application|game|for me)\b", " ", value)
    value = re.sub(r"'s\b", "s", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\bi\s+tunes\b", "itunes", value)
    value = re.sub(r"\bcrunchy\s+roll\b", "crunchyroll", value)
    value = re.sub(r"\bapegs\b", "apex", value)
    value = re.sub(r"\bbng\b", "beamng", value)
    value = re.sub(r"\bvs\b", "visual studio", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _candidate_score(requested: str, candidate: str) -> float:
    if not requested or not candidate:
        return 0.0
    if requested == candidate:
        return 1.0
    requested_tokens = set(requested.split())
    candidate_tokens = set(candidate.split())
    compact_requested = requested.replace(" ", "")
    compact_candidate = candidate.replace(" ", "")

    sequence = SequenceMatcher(None, requested, candidate).ratio()
    compact_sequence = SequenceMatcher(None, compact_requested, compact_candidate).ratio()
    overlap = len(requested_tokens & candidate_tokens)
    token_overlap = overlap / max(len(requested_tokens), 1)
    candidate_coverage = overlap / max(len(candidate_tokens), 1)
    score = max(sequence, compact_sequence)

    if requested_tokens and requested_tokens <= candidate_tokens:
        score = max(score, 0.94)
    elif token_overlap >= 0.75:
        score = max(score, 0.86)
    elif token_overlap >= 0.5 and candidate_coverage >= 0.25:
        score = max(score, 0.78)

    if compact_requested and compact_requested in compact_candidate:
        score = max(score, 0.90)
    return min(score, 1.0)


def _join_display_names(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _is_windows_uri(command: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*:$", command, re.IGNORECASE))


def _process_names_for_app(resolved_name: str, app: ApprovedApp) -> tuple[str, ...]:
    if app.process_names:
        return app.process_names
    command_path = Path(app.command)
    if command_path.suffix.lower() == ".exe":
        return (command_path.name,)
    known_processes = {
        "calculator": ("CalculatorApp.exe", "calc.exe"),
        "notepad": ("notepad.exe",),
        "paint": ("mspaint.exe",),
        "explorer": ("explorer.exe",),
        "file explorer": ("explorer.exe",),
        "task manager": ("Taskmgr.exe",),
        "control panel": ("control.exe",),
        "settings": ("SystemSettings.exe",),
        "windows settings": ("SystemSettings.exe",),
        "snipping tool": ("SnippingTool.exe", "ScreenClippingHost.exe"),
        "chrome": ("chrome.exe",),
        "google chrome": ("chrome.exe",),
        "itunes": ("iTunes.exe",),
        "discord": ("Discord.exe",),
        "crunchyroll": ("msedge.exe", "chrome.exe"),
    }
    normalized = _normalize_app_name(resolved_name or app.display_name)
    return known_processes.get(normalized, ())


def _close_processes(process_names: tuple[str, ...]) -> bool:
    names = [Path(process_name).stem for process_name in process_names if process_name.strip()]
    if not names:
        return False
    script = (
        "$names = @("
        + ",".join("'" + name.replace("'", "''") + "'" for name in names)
        + "); "
        "$found = $false; "
        "foreach ($name in $names) { "
        "  $procs = @(Get-Process -Name $name -ErrorAction SilentlyContinue); "
        "  if ($procs.Count -gt 0) { "
        "    $found = $true; "
        "    foreach ($proc in $procs) { "
        "      try { if ($proc.MainWindowHandle -ne 0) { [void]$proc.CloseMainWindow() } } catch {} "
        "    } "
        "  } "
        "} "
        "Start-Sleep -Milliseconds 900; "
        "foreach ($name in $names) { "
        "  $remaining = @(Get-Process -Name $name -ErrorAction SilentlyContinue); "
        "  foreach ($proc in $remaining) { try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop; $found = $true } catch {} } "
        "} "
        "if ($found) { exit 0 } else { exit 2 }"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.returncode == 0


def _important_apps() -> dict[str, ApprovedApp]:
    apps = {
        "calculator": ApprovedApp("Calculator", "calc.exe", process_names=("CalculatorApp.exe", "calc.exe")),
        "notepad": ApprovedApp("Notepad", "notepad.exe", process_names=("notepad.exe",)),
        "paint": ApprovedApp("Paint", "mspaint.exe", process_names=("mspaint.exe",)),
        "explorer": ApprovedApp("File Explorer", "explorer.exe", process_names=("explorer.exe",)),
        "file explorer": ApprovedApp("File Explorer", "explorer.exe", process_names=("explorer.exe",)),
        "task manager": ApprovedApp("Task Manager", "taskmgr.exe", process_names=("Taskmgr.exe",)),
        "control panel": ApprovedApp("Control Panel", "control.exe", process_names=("control.exe",)),
        "settings": ApprovedApp("Windows Settings", "ms-settings:", process_names=("SystemSettings.exe",)),
        "windows settings": ApprovedApp("Windows Settings", "ms-settings:", process_names=("SystemSettings.exe",)),
        "snipping tool": ApprovedApp("Snipping Tool", "snippingtool.exe", process_names=("SnippingTool.exe", "ScreenClippingHost.exe")),
        "terminal": ApprovedApp("Windows Terminal", "wt.exe", requires_confirmation=True, process_names=("WindowsTerminal.exe",)),
        "powershell": ApprovedApp("PowerShell", "powershell.exe", requires_confirmation=True, process_names=("powershell.exe",)),
    }
    _add_existing_path(apps, "chrome", "Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    _add_existing_path(apps, "google chrome", "Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    _add_existing_path(apps, "itunes", "iTunes", r"C:\Program Files\iTunes\iTunes.exe")
    _add_existing_path(apps, "discord", "Discord", str(Path.home() / "Desktop" / "Discord.lnk"))
    return apps


def _add_existing_path(apps: dict[str, ApprovedApp], key: str, display_name: str, command: str) -> None:
    if Path(command).exists():
        process_names = _known_process_names_for_display(key, display_name, command)
        apps[key] = ApprovedApp(display_name, command, process_names=process_names)


def _desktop_apps(desktop: Path | None = None) -> dict[str, ApprovedApp]:
    desktop_path = desktop or Path.home() / "Desktop"
    if not desktop_path.exists():
        return {}
    apps: dict[str, ApprovedApp] = {}
    for item in desktop_path.iterdir():
        if not item.is_file():
            continue
        if item.suffix.lower() not in DESKTOP_LAUNCH_EXTENSIONS:
            continue
        key = _normalize_app_name(item.stem)
        if not key or key in DESKTOP_EXCLUDE_NAMES:
            continue
        display_name = _display_name_from_desktop_item(item)
        app = ApprovedApp(display_name, str(item), process_names=_known_process_names_for_display(key, display_name, str(item)))
        apps[key] = app
        for alias in _desktop_aliases(item.stem):
            alias_key = _normalize_app_name(alias)
            if alias_key and alias_key not in DESKTOP_EXCLUDE_NAMES:
                apps.setdefault(alias_key, app)
    return apps


def _display_name_from_desktop_item(item: Path) -> str:
    name = item.stem.replace(" - Shortcut", "").strip()
    name = re.sub(r"\s+", " ", name)
    return name or item.name


def _desktop_aliases(stem: str) -> list[str]:
    aliases = {stem}
    cleaned = stem.replace(" - Shortcut", "")
    aliases.add(cleaned)
    aliases.add(re.sub(r"\s*-\s*watch popular anime\s*$", "", cleaned, flags=re.IGNORECASE))
    aliases.add(re.sub(r"\bplayer\b", "", cleaned, flags=re.IGNORECASE))
    aliases.add(re.sub(r"\blauncher\b", "", cleaned, flags=re.IGNORECASE))
    aliases.add(re.sub(r"\bfor windows\b", "", cleaned, flags=re.IGNORECASE))
    aliases.add(cleaned.replace("®", ""))
    aliases.add(cleaned.replace(".", " "))
    if re.search(r"\bazgaar", cleaned, re.IGNORECASE):
        aliases.update({"map generator", "fantasy map generator", "fantasy map"})
    if re.search(r"\bbeamng", cleaned, re.IGNORECASE):
        aliases.update({"beamng", "beamng drive", "bng"})
    if re.search(r"\bmarvel\s+rivals\b", cleaned, re.IGNORECASE):
        aliases.update({"marvel rivals", "marvel"})
    if re.search(r"\bcrunchyroll\b", cleaned, re.IGNORECASE):
        aliases.update({"crunchyroll", "crunchy anime", "anime"})
    if re.search(r"\bvisual studio code\b", cleaned, re.IGNORECASE):
        aliases.update({"vs code", "vscode", "code"})
    if "pwa.zoom.us" in cleaned.lower() or re.search(r"\bzoom\b", cleaned, re.IGNORECASE):
        aliases.add("zoom")
    return [alias.strip() for alias in aliases if alias.strip()]


def _known_process_names_for_display(key: str, display_name: str, command: str) -> tuple[str, ...]:
    command_path = Path(command)
    if command_path.suffix.lower() == ".exe":
        return (command_path.name,)
    normalized = _normalize_app_name(f"{key} {display_name}")
    matches: list[str] = []
    known = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "itunes": "iTunes.exe",
        "discord": "Discord.exe",
        "crunchyroll": "msedge.exe",
        "visual studio code": "Code.exe",
        "vscode": "Code.exe",
        "steam": "steam.exe",
        "epic games": "EpicGamesLauncher.exe",
        "minecraft": "MinecraftLauncher.exe",
        "apex": "r5apex.exe",
        "marvel rivals": "MarvelRivals.exe",
        "brawlhalla": "Brawlhalla.exe",
        "beamng": "BeamNG.drive.x64.exe",
        "zoom": "Zoom.exe",
    }
    for token, process_name in known.items():
        if token in normalized and process_name not in matches:
            matches.append(process_name)
    return tuple(matches)


def _write_default_approved_apps(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "apps": {
                    "terminal": {"display_name": "Windows Terminal", "command": "wt.exe", "requires_confirmation": True},
                    "powershell": {"display_name": "PowerShell", "command": "powershell.exe", "requires_confirmation": True},
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
