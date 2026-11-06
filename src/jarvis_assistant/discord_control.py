from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .improvement import ImprovementQueue
from .task_status import VisibleStatusVerifier, visible_window_contains, with_screen_evidence


_CONNECTED_CALL_PHRASES = (
    "voice connected",
    "disconnect",
    "screen",
    "soundboard",
    "leave call",
)


@dataclass(frozen=True)
class DiscordCallTarget:
    key: str
    display_name: str
    route: str = ""
    aliases: tuple[str, ...] = ()
    target_type: str = "dm"


class DiscordCallController:
    def __init__(self, root: Path, config_path: Path | None = None) -> None:
        self.root = root
        self.config_path = config_path or root / "config" / "discord_calls.json"

    def call(self, requested_target: str) -> str:
        target_text = _clean_discord_target(requested_target)
        if not target_text:
            return "Who should I call on Discord?"

        target = self._resolve_target(target_text)
        display_name = target.display_name if target else target_text
        route = target.route if target else ""

        self._open_discord(route)
        if not route:
            self._search_discord(target_text)

        clicked = self._click_call_button()
        if clicked:
            status = VisibleStatusVerifier(self.root, max_checks=8, interval_seconds=1.0).verify(
                r".*Discord.*",
                _CONNECTED_CALL_PHRASES,
            )
            if not status.done:
                ImprovementQueue(self.root).log(
                    request=f"Call {display_name} on Discord",
                    reason=(
                        "Discord call button was clicked, but Damien could not confirm the call connected. "
                        f"Last check: {status.detail}"
                    ),
                    suggestion="Improve Discord connected-call status detection and retry handling.",
                )
                return (
                    f"I pressed the Discord call button for {display_name}, but I could not confirm the call connected. "
                    "I queued a Discord call status-check upgrade for Codex."
                )
            return f"Starting Discord call with {display_name}."
        ImprovementQueue(self.root).log(
            request=f"Call {display_name} on Discord",
            reason=with_screen_evidence(
                self.root,
                "Discord opened, but Damien could not find or click the voice call button automatically.",
            ),
            suggestion="Improve Discord UI automation for voice calls, group chats, and Discord button labels.",
        )
        return (
            f"I opened {display_name} in Discord, but I could not press the call button automatically. "
            "I queued a Discord calling upgrade for Codex instead of repeating this fallback."
        )

    def answer_call(self) -> str:
        self._open_discord()
        clicked = self._click_discord_button(
            (
                "Answer",
                "Accept",
                "Join Call",
                "Join Voice",
                "Accept Call",
                "Answer Call",
            )
        )
        if clicked:
            return "Answered the incoming Discord call."
        ImprovementQueue(self.root).log(
            request="Answer incoming Discord call",
            reason=with_screen_evidence(
                self.root,
                "Discord opened, but Damien could not find the incoming call button automatically.",
            ),
            suggestion="Add incoming Discord call detection and answer/decline button automation.",
        )
        return "I opened Discord, but I could not find the incoming call button. I queued that Discord receive-call upgrade for Codex."

    def _open_discord(self, route: str = "") -> None:
        if route:
            os.startfile(route)
            time.sleep(2.0)
            return
        discord_exe = _discord_executable()
        if discord_exe:
            subprocess.Popen([str(discord_exe)], shell=False)
        else:
            os.startfile("discord:")
        time.sleep(2.5)

    def _search_discord(self, target_text: str) -> None:
        try:
            import win32api  # type: ignore[import-not-found]
            import win32con  # type: ignore[import-not-found]
            import win32clipboard  # type: ignore[import-not-found]
        except Exception:
            return

        _set_clipboard_text(target_text, win32clipboard)
        for key in (win32con.VK_CONTROL, ord("K")):
            win32api.keybd_event(key, 0, 0, 0)
        for key in (ord("K"), win32con.VK_CONTROL):
            win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.25)
        for key in (win32con.VK_CONTROL, ord("V")):
            win32api.keybd_event(key, 0, 0, 0)
        for key in (ord("V"), win32con.VK_CONTROL):
            win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.45)
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(1.25)

    def _click_call_button(self) -> bool:
        return self._click_discord_button(
            (
                "Start Voice Call",
                "Voice Call",
                "Start Call",
                "Start voice call",
                "Call",
            )
        )

    def _verify_call_connected(self) -> tuple[bool, str]:
        return visible_window_contains(r".*Discord.*", _CONNECTED_CALL_PHRASES)

    def _click_discord_button(self, candidates: tuple[str, ...]) -> bool:
        try:
            from pywinauto import Desktop  # type: ignore[import-not-found]
        except Exception:
            return False
        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows(title_re=r".*Discord.*", visible_only=True)
            for window in windows:
                try:
                    window.set_focus()
                except Exception:
                    pass
                for title in candidates:
                    try:
                        button = window.child_window(title=title, control_type="Button")
                        if button.exists(timeout=0.8):
                            button.click_input()
                            return True
                    except Exception:
                        continue
        except Exception:
            return False
        return False

    def _targets(self) -> list[DiscordCallTarget]:
        payload = self._config_payload()
        targets = []
        raw_targets = payload.get("targets", {})
        if not isinstance(raw_targets, dict):
            return []
        for key, value in raw_targets.items():
            if not isinstance(value, dict):
                continue
            aliases = value.get("aliases", [])
            if not isinstance(aliases, list):
                aliases = []
            targets.append(
                DiscordCallTarget(
                    key=str(key),
                    display_name=str(value.get("display_name") or key),
                    route=str(value.get("route") or ""),
                    aliases=tuple(str(alias) for alias in aliases),
                    target_type=str(value.get("type") or "dm"),
                )
            )
        return targets

    def _resolve_target(self, requested_target: str) -> DiscordCallTarget | None:
        requested = _normalize_discord_name(requested_target)
        scored: list[tuple[float, DiscordCallTarget]] = []
        for target in self._targets():
            names = (target.key, target.display_name, *target.aliases)
            score = max((_name_score(requested, _normalize_discord_name(name)) for name in names), default=0.0)
            scored.append((score, target))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1] if scored[0][0] >= 0.74 else None

    def _config_payload(self) -> dict[str, object]:
        if not self.config_path.exists():
            self._write_default_config()
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {"targets": {}}

    def _write_default_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "targets": {
                        "example friend": {
                            "display_name": "Example Friend",
                            "type": "dm",
                            "route": "discord://-/channels/@me/USER_OR_DM_CHANNEL_ID",
                            "aliases": ["friend"],
                        },
                        "example group": {
                            "display_name": "Example Group",
                            "type": "group",
                            "route": "discord://-/channels/@me/GROUP_DM_CHANNEL_ID",
                            "aliases": ["the group chat"],
                        },
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _discord_executable() -> Path | None:
    local = Path.home() / "AppData" / "Local" / "Discord"
    if not local.exists():
        return None
    candidates = sorted(local.glob("app-*/Discord.exe"), reverse=True)
    return candidates[0] if candidates else None


def _clean_discord_target(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:the\s+)?discord\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:on|in)\s+discord$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def _normalize_discord_name(value: str) -> str:
    cleaned = value.casefold().replace("&", " and ")
    cleaned = re.sub(r"\b(?:the|a|an|discord|call|voice|dm|person|people|for me)\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _name_score(requested: str, candidate: str) -> float:
    if not requested or not candidate:
        return 0.0
    if requested == candidate:
        return 1.0
    requested_tokens = set(requested.split())
    candidate_tokens = set(candidate.split())
    overlap = len(requested_tokens & candidate_tokens) / max(len(requested_tokens), 1)
    sequence = SequenceMatcher(None, requested, candidate).ratio()
    if requested_tokens and requested_tokens <= candidate_tokens:
        return max(sequence, 0.95)
    return max(sequence, overlap)


def _set_clipboard_text(text: str, win32clipboard: object) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text)
    finally:
        win32clipboard.CloseClipboard()
