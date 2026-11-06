from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .screen_access import ScreenReader


TaskVerifier = Callable[[], tuple[bool, str]]


@dataclass(frozen=True)
class TaskStatus:
    done: bool
    attempts: int
    detail: str


@dataclass(frozen=True)
class TaskStatusMonitor:
    max_checks: int = 8
    interval_seconds: float = 1.0

    def wait_until(self, verifier: TaskVerifier) -> TaskStatus:
        attempts = 0
        last_detail = ""
        for attempt in range(1, max(1, self.max_checks) + 1):
            attempts = attempt
            done, detail = verifier()
            last_detail = detail
            if done:
                return TaskStatus(True, attempts, last_detail)
            if attempt < self.max_checks:
                time.sleep(max(0.0, self.interval_seconds))
        return TaskStatus(False, attempts, last_detail)


@dataclass(frozen=True)
class VisibleStatusVerifier:
    root: Path
    max_checks: int = 8
    interval_seconds: float = 1.0

    def verify(self, title_pattern: str, phrases: tuple[str, ...]) -> TaskStatus:
        status = TaskStatusMonitor(self.max_checks, self.interval_seconds).wait_until(
            lambda: visible_window_contains(title_pattern, phrases)
        )
        if status.done:
            return status
        return TaskStatus(status.done, status.attempts, with_screen_evidence(self.root, status.detail))


def with_screen_evidence(root: Path, detail: str) -> str:
    reader = ScreenReader(root)
    if not reader.screen_access_enabled():
        return f"{detail} Screen evidence unavailable: screen access is disabled in Damien settings."
    try:
        capture = reader.capture_screen()
    except Exception as exc:
        return f"{detail} Screen evidence unavailable: {exc}"
    return f"{detail} Screen evidence: {capture.path} ({capture.width}x{capture.height})."


def visible_window_contains(title_pattern: str, phrases: tuple[str, ...]) -> tuple[bool, str]:
    try:
        from pywinauto import Desktop  # type: ignore[import-not-found]
    except Exception as exc:
        return False, f"UI status check unavailable: {exc}"
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows(title_re=title_pattern, visible_only=True)
    except Exception as exc:
        return False, f"No matching visible app window: {exc}"

    wanted = tuple(phrase.casefold() for phrase in phrases)
    for window in windows:
        try:
            texts = [str(text) for text in window.descendants() if str(text)]
        except Exception:
            texts = []
        try:
            window_text = str(window.window_text())
            if window_text:
                texts.append(window_text)
        except Exception:
            pass
        haystack = " ".join(texts).casefold()
        for phrase in wanted:
            if phrase and phrase in haystack:
                return True, f"Confirmed visible status text: {phrase}"
    return False, "Visible app window did not show the expected status yet."


def visible_window_exists(title_pattern: str) -> tuple[bool, str]:
    try:
        from pywinauto import Desktop  # type: ignore[import-not-found]
    except Exception as exc:
        return False, f"UI window check unavailable: {exc}"
    try:
        windows = Desktop(backend="uia").windows(title_re=title_pattern, visible_only=True)
    except Exception as exc:
        return False, f"No matching visible app window: {exc}"
    if windows:
        return True, "Matching game window is visible."
    return False, "No matching visible game window."
