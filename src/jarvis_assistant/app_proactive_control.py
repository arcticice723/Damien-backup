from __future__ import annotations

from dataclasses import is_dataclass, replace
import threading
from typing import Any

from .config import update_settings
from .app_state import active_companion_summary_text
from .proactive_loop import ProactiveLoop


def proactive_settings_update(enabled: bool) -> dict[str, bool]:
    return {"proactive_enabled": enabled}


def proactive_voice_settings_update(enabled: bool) -> dict[str, bool]:
    return {"proactive_voice_enabled": enabled}


def should_speak_proactive_notice(proactive_voice_enabled: bool, tts_engine: str) -> bool:
    return proactive_voice_enabled and tts_engine != "off"


def live_proactive_voice_enabled(app: Any) -> bool:
    value = getattr(app, "proactive_voice_enabled", None)
    if value is not None:
        return bool(value.get())
    return bool(app.settings.proactive_voice_enabled)


def update_loaded_setting(app: Any, name: str, value: object) -> None:
    if is_dataclass(app.settings):
        app.settings = replace(app.settings, **{name: value})
    else:
        setattr(app.settings, name, value)


def update_proactive_summary(app: Any) -> None:
    if hasattr(app, "proactive_summary"):
        app.proactive_summary.set(
            active_companion_summary_text(app.settings.proactive_enabled, app.settings.proactive_voice_enabled)
        )


class ProactiveController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def start_loop(self, *, enabled: bool | None = None) -> None:
        app = self.app
        if enabled is None:
            enabled = app.settings.proactive_enabled
        if not enabled:
            return
        if getattr(app, "proactive_loop", None) is not None:
            return
        app.proactive_loop = ProactiveLoop(
            check=app.orchestrator.check_proactive,
            emit=lambda kind, payload: app.events.put((kind, payload)),
            interval_seconds=app.settings.reminder_check_seconds,
            should_stop=lambda: app.quitting,
            on_error=lambda exc: app._log_connection(f"proactive check failed: {exc}"),
        )
        app.proactive_loop.start()

    def toggle_proactive_checks(self) -> None:
        app = self.app
        enabled = app.proactive_enabled.get()
        update_settings(proactive_settings_update(enabled))
        update_loaded_setting(app, "proactive_enabled", enabled)
        update_proactive_summary(app)
        if enabled:
            self.start_loop(enabled=True)
            app.status.set("Active companion checks are on.")
        else:
            loop = getattr(app, "proactive_loop", None)
            if loop is not None:
                loop.stop()
                app.proactive_loop = None
            app.status.set("Active companion checks are off.")

    def toggle_proactive_voice(self) -> None:
        app = self.app
        enabled = app.proactive_voice_enabled.get()
        update_settings(proactive_voice_settings_update(enabled))
        update_loaded_setting(app, "proactive_voice_enabled", enabled)
        update_proactive_summary(app)
        if should_speak_proactive_notice(enabled, app.settings.tts_engine):
            app.status.set("Damien will speak proactive notices aloud.")
        elif enabled:
            app.status.set("Voice output is off, so proactive notices will stay silent.")
        else:
            app.status.set("Damien will show proactive notices silently.")

    def show_notice(self, text: str) -> None:
        app = self.app
        app._append_line("Damien", text)
        app.history.add_assistant(text)
        if should_speak_proactive_notice(live_proactive_voice_enabled(app), app.settings.tts_engine):
            app.status.set("Proactive notice spoken.")
            threading.Thread(target=app._speak, args=(text,), daemon=True).start()
        else:
            app.status.set("Proactive notice.")
