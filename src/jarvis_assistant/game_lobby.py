from __future__ import annotations

import threading
import time
import re
from dataclasses import dataclass
from pathlib import Path

from .improvement import ImprovementQueue
from .runtime import APP_ROOT
from .task_status import VisibleStatusVerifier, visible_window_contains, visible_window_exists, with_screen_evidence


@dataclass(frozen=True)
class LobbyStep:
    label: str
    wait_seconds: float = 2.0
    fallback_enter: bool = True


GAME_LOBBY_PROFILES: dict[str, tuple[LobbyStep, ...]] = {
    "apex legends": (
        LobbyStep("Continue", wait_seconds=18.0),
    ),
    "marvel rivals": (
        LobbyStep("Launch", wait_seconds=8.0),
        LobbyStep("Continue", wait_seconds=20.0),
    ),
}

SAFE_BUTTON_LABELS = {
    "continue": "Continue",
    "launch": "Launch",
    "play": "Play",
    "start": "Start",
    "ok": "OK",
    "yes": "Yes",
}

_last_lobby_game: str | None = None


class SafeUiController:
    def __init__(self, click_button=None) -> None:
        self.click_button = click_button or _click_button_by_name

    def click_known_button(self, label: str) -> str:
        canonical = SAFE_BUTTON_LABELS.get(label.strip().lower())
        if canonical is None:
            approved = ", ".join(sorted(SAFE_BUTTON_LABELS.values()))
            return f"Denied: I can only click approved low-risk buttons for now: {approved}."
        if self.click_button(canonical):
            return f"Clicked {canonical}."
        return f"I could not find a visible {canonical} button."


def has_lobby_profile(app_name: str) -> bool:
    return app_name in GAME_LOBBY_PROFILES


def current_lobby_game() -> str | None:
    return _last_lobby_game


def schedule_lobby_entry(app_name: str, root: Path = APP_ROOT) -> None:
    steps = GAME_LOBBY_PROFILES.get(app_name)
    if not steps:
        return
    global _last_lobby_game
    _last_lobby_game = app_name
    thread = threading.Thread(target=_run_lobby_steps, args=(app_name, steps, root), daemon=True)
    thread.start()


def run_lobby_entry_now(app_name: str | None = None, root: Path = APP_ROOT) -> str:
    target = app_name or _last_lobby_game
    if target is None or target not in GAME_LOBBY_PROFILES:
        return "I do not have a recent lobby-capable game to continue yet."
    _run_lobby_steps(target, GAME_LOBBY_PROFILES[target], root)
    return f"Taking you to the {_game_display_name(target)} lobby."


def _run_lobby_steps(app_name: str, steps: tuple[LobbyStep, ...], root: Path = APP_ROOT) -> None:
    title_pattern, phrases = _lobby_status_query(app_name)
    for index, step in enumerate(steps):
        time.sleep(step.wait_seconds)
        window_visible, _window_detail = visible_window_exists(title_pattern)
        if not window_visible:
            other_game = _visible_other_lobby_game(app_name)
            if other_game:
                ImprovementQueue(root).log(
                    request=f"Take {_game_display_name(app_name)} to lobby",
                    reason=with_screen_evidence(
                        root,
                        (
                            f"{_game_display_name(app_name)} window was not visible, so Damien did not press "
                            f"{step.label} or Enter. {_game_display_name(other_game)} appears to be visible instead."
                        ),
                    ),
                    suggestion=f"Improve game lobby screen detection and app selection for {_game_display_name(app_name)}.",
                )
                continue

        action_taken = False
        if _click_button_by_name(step.label, title_pattern):
            action_taken = True
        elif step.fallback_enter:
            if window_visible and _press_enter():
                action_taken = True

        if action_taken:
            if index < len(steps) - 1:
                continue
            status = VisibleStatusVerifier(root, max_checks=10, interval_seconds=1.0).verify(title_pattern, phrases)
            if status.done:
                continue
            window_visible, _window_detail = visible_window_exists(title_pattern)
            if window_visible:
                continue
            ImprovementQueue(root).log(
                request=f"Take {_game_display_name(app_name)} to lobby",
                reason=(
                    f"Clicked or pressed through {step.label}, but Damien did not confirm lobby status. "
                    f"Last check: {status.detail}"
                ),
                suggestion=f"Improve game lobby status detection for {_game_display_name(app_name)}.",
            )
            continue

        ImprovementQueue(root).log(
            request=f"Take {_game_display_name(app_name)} to lobby",
            reason=with_screen_evidence(
                root,
                f"Could not find the {step.label} button during lobby automation.",
            ),
            suggestion=f"Improve game lobby screen detection and button automation for {_game_display_name(app_name)}.",
        )


def _click_button_by_name(label: str, title_pattern: str | None = None) -> bool:
    try:
        from pywinauto import Desktop  # type: ignore[import-not-found]
    except Exception:
        return False
    try:
        desktop = Desktop(backend="uia")
        if title_pattern:
            windows = desktop.windows(title_re=title_pattern, visible_only=True)
        else:
            windows = desktop.windows(visible_only=True)
        candidates = _button_title_candidates(label)
        for window in windows:
            for title in candidates:
                try:
                    button = window.child_window(title=title, control_type="Button")
                    if button.exists(timeout=0.4):
                        try:
                            window.set_focus()
                        except Exception:
                            pass
                        button.click_input()
                        return True
                except Exception:
                    continue
    except Exception:
        return False
    return False


def _press_enter() -> bool:
    try:
        import win32api  # type: ignore[import-not-found]
        import win32con  # type: ignore[import-not-found]

        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


def _button_title_candidates(label: str) -> tuple[str, ...]:
    return (
        label,
        label.upper(),
        label.title(),
        f"{label} Button",
        f"{label.title()} Button",
    )


def _verify_lobby_ready(app_name: str) -> tuple[bool, str]:
    title_pattern, phrases = _lobby_status_query(app_name)
    return visible_window_contains(title_pattern, phrases)


def _visible_other_lobby_game(app_name: str) -> str | None:
    for other_name in GAME_LOBBY_PROFILES:
        if other_name == app_name:
            continue
        other_pattern, _phrases = _lobby_status_query(other_name)
        visible, _detail = visible_window_exists(other_pattern)
        if visible:
            return other_name
    return None


def _lobby_status_query(app_name: str) -> tuple[str, tuple[str, ...]]:
    title_patterns = {
        "apex legends": r".*(Apex|r5apex).*",
        "marvel rivals": r".*(Marvel|Rivals).*",
    }
    phrases = {
        "apex legends": ("ready", "lobby", "play apex", "friends in apex"),
        "marvel rivals": ("play", "heroes", "season", "lobby"),
    }
    return (
        title_patterns.get(app_name, rf".*{re.escape(app_name)}.*"),
        phrases.get(app_name, ("lobby", "play", "ready")),
    )


def _game_display_name(app_name: str) -> str:
    names = {
        "apex legends": "Apex Legends",
        "marvel rivals": "Marvel Rivals",
    }
    return names.get(app_name, app_name.title())
