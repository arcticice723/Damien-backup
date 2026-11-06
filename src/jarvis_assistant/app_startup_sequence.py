from __future__ import annotations

from typing import Any


STARTUP_STEP_NAMES = [
    "style",
    "build_ui",
    "window_events",
    "mascot",
    "tray",
    "remote_control",
    "discord_bridge",
    "proactive_loop",
    "startup_visibility",
    "startup_state",
    "gpu_status",
    "ollama_status",
    "wake_phrase",
    "event_polling",
]


def startup_step_names() -> list[str]:
    return list(STARTUP_STEP_NAMES)


class DamienStartupRunner:
    def __init__(self, app: Any) -> None:
        self.app = app

    def run(self) -> None:
        app = self.app
        app._style()
        app._build_ui()
        app.protocol("WM_DELETE_WINDOW", app._on_close)
        app.bind("<Unmap>", app._on_unmap)
        app._sync_mascot_widget()
        app._start_tray()
        app._start_remote_control()
        app._start_discord_bridge()
        app._start_proactive_loop()
        app._apply_startup_visibility()
        app._sync_startup_state()
        app._refresh_gpu()
        app._check_ollama_async()
        if app.wake_enabled.get():
            app._toggle_wake_phrase()
        app._poll_events()
