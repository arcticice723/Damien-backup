from __future__ import annotations

import time


def wake_acknowledgement_cue(value: str) -> str:
    return (value or "yes?").strip() or "yes?"


def command_captured_cue(value: str) -> str:
    return (value or "hmmm...").strip() or "hmmm..."


def play_wake_acknowledgement() -> bool:
    """Play a short local tone after the wake phrase is detected."""
    try:
        import winsound

        winsound.Beep(880, 75)
        time.sleep(0.035)
        winsound.Beep(1175, 95)
        return True
    except Exception:
        return False


def play_command_captured() -> bool:
    """Play a softer tone when Damien finishes recording the wake command."""
    try:
        import winsound

        winsound.Beep(740, 70)
        return True
    except Exception:
        return False
