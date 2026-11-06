from __future__ import annotations

import secrets
from collections.abc import Callable
from tkinter import messagebox
from typing import Any

from .config import load_settings, update_settings
from .app_proactive_control import update_loaded_setting, update_proactive_summary
from .runtime import APP_ROOT
from .startup import is_launch_at_sign_in_enabled, set_launch_at_sign_in


def resolve_remote_pin(value: str, randbelow: Callable[[int], int]) -> tuple[str, bool]:
    pin = value.strip()
    if pin.lower() == "auto" or not pin:
        return f"{randbelow(900000) + 100000}", True
    return pin, False


def remote_status_payload(status: str, engine: str, voice: str, wake: str, privacy: str) -> dict[str, str]:
    return {
        "status": status,
        "engine": engine,
        "voice": voice,
        "wake": wake,
        "privacy": privacy,
    }


def tray_status_text(mic_enabled: bool, ollama_connected: bool, wake_running: bool) -> str:
    mic = "Mic on" if mic_enabled else "Mic muted"
    ollama = "Ollama connected" if ollama_connected else "Ollama offline"
    wake = "Wake on" if wake_running else "Wake off"
    return f"{mic} | {ollama} | {wake}"


def start_minimized_status_text(enabled: bool) -> str:
    if enabled:
        return "Damien will start in background tray mode."
    return "Damien will show the window on startup."


class AppLifecycleController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def remote_pin(self) -> str:
        app = self.app
        pin, changed = resolve_remote_pin(app.settings.remote_control_pin, secrets.randbelow)
        if changed:
            update_settings({"remote_control_pin": pin})
            app.settings = load_settings()
        self.set_remote_pin_display(pin)
        return pin

    def set_remote_pin_display(self, pin: str) -> None:
        app = self.app
        if hasattr(app, "remote_pin_display"):
            app.remote_pin_display.set("Phone password is saved. Enter a new one below to change it.")

    def set_remote_status(self, text: str) -> None:
        app = self.app
        if hasattr(app, "remote_status"):
            app.remote_status.set(text)
        app.privacy_summary.set(text)

    def remote_status_payload(self) -> dict[str, str]:
        app = self.app
        return remote_status_payload(
            status=app.status.get(),
            engine=app.local_engine_summary.get(),
            voice=app.voice_summary.get(),
            wake=app.wake_summary.get(),
            privacy=app.privacy_summary.get(),
        )

    def apply_startup_visibility(self) -> None:
        app = self.app
        if app.settings.start_minimized_to_tray and app.tray and app.tray.available:
            app.after(0, app._start_in_tray)

    def start_in_tray(self) -> None:
        app = self.app
        app.withdraw()
        app.status.set("Damien is running in background tray mode.")
        app.privacy_summary.set("Screenless background mode")
        app._log_voice("background_mode: started in tray; wake and voice services remain active")

    def toggle_start_minimized_to_tray(self) -> None:
        app = self.app
        enabled = app.start_minimized_to_tray.get()
        update_settings({"start_minimized_to_tray": enabled})
        app.settings = load_settings()
        app.status.set(start_minimized_status_text(enabled))

    def on_close(self) -> None:
        app = self.app
        if app.quitting:
            app.destroy()
            return
        if app.tray and app.tray.available:
            app.withdraw()
            app.status.set("Damien is running in the system tray.")
        else:
            app._quit_from_tray()

    def on_unmap(self) -> None:
        app = self.app
        if app.quitting:
            return
        if app.state() == "iconic" and app.tray and app.tray.available:
            app.after(0, app.withdraw)
            app.status.set("Damien is minimized to the system tray.")

    def restore_from_tray(self) -> None:
        self.app.after(0, self.app._restore_window)

    def restore_window(self) -> None:
        app = self.app
        app.deiconify()
        app.state("normal")
        app.lift()
        app.focus_force()
        app.privacy_summary.set("Control surface restored")
        app._log_voice("background_mode: window restored")

    def quit_from_tray(self) -> None:
        self.app.after(0, self.app._quit)

    def quit(self) -> None:
        app = self.app
        app.quitting = True
        transcriber = getattr(app, "transcriber", None)
        if transcriber is not None:
            transcriber.close()
            app.transcriber = None
        if app.wake_detector:
            app.wake_detector.stop()
        if app.tray:
            app.tray.stop()
        if app.remote:
            app.remote.stop()
        if app.discord_bridge:
            app.discord_bridge.stop()
        if app.proactive_loop:
            app.proactive_loop.stop()
            app.proactive_loop = None
        app.destroy()

    def toggle_mic_from_tray(self) -> None:
        self.app.after(0, self.app._toggle_mic_value)

    def toggle_mic_value(self) -> None:
        app = self.app
        app.mic_enabled.set(not app.mic_enabled.get())
        app._toggle_mic()

    def tray_status_text(self) -> str:
        app = self.app
        return tray_status_text(
            mic_enabled=app.mic_enabled.get(),
            ollama_connected=app.ollama_connected.get(),
            wake_running=bool(app.wake_enabled.get() and app.wake_detector and app.wake_detector.is_running()),
        )

    def sync_startup_state(self) -> None:
        self.app.launch_at_sign_in.set(is_launch_at_sign_in_enabled())

    def toggle_launch_at_sign_in(self) -> None:
        app = self.app
        enabled = app.launch_at_sign_in.get()
        if enabled:
            if not messagebox.askyesno(
                "Launch at sign-in",
                "Enable launch at Windows sign-in? This writes to your current user's Windows startup registry key.",
            ):
                app.launch_at_sign_in.set(False)
                app.status.set("Launch at sign-in was left off.")
                return
        try:
            set_launch_at_sign_in(enabled, APP_ROOT)
            values = {"launch_at_sign_in": enabled}
            if enabled and not app.start_minimized_to_tray.get():
                app.start_minimized_to_tray.set(True)
                values["start_minimized_to_tray"] = True
            if enabled and not app.wake_enabled.get():
                app.wake_enabled.set(True)
                values["wake_phrase_enabled"] = True
            proactive_enabled = getattr(app, "proactive_enabled", None)
            if enabled and proactive_enabled is not None and not proactive_enabled.get():
                proactive_enabled.set(True)
                values["proactive_enabled"] = True
                if hasattr(app, "settings"):
                    update_loaded_setting(app, "proactive_enabled", True)
            proactive_voice_enabled = getattr(app, "proactive_voice_enabled", None)
            if enabled and proactive_voice_enabled is not None and not proactive_voice_enabled.get():
                proactive_voice_enabled.set(True)
                values["proactive_voice_enabled"] = True
                if hasattr(app, "settings"):
                    update_loaded_setting(app, "proactive_voice_enabled", True)
            update_settings(values)
            if enabled and values.get("proactive_enabled") and hasattr(app, "_start_proactive_loop"):
                app._start_proactive_loop()
            if enabled and ("proactive_enabled" in values or "proactive_voice_enabled" in values):
                update_proactive_summary(app)
            if enabled:
                app.status.set(
                    "Damien will launch at sign-in in background tray mode with wake phrase, "
                    "active checks, and spoken notices enabled."
                )
            else:
                app.status.set("Damien will not launch at sign-in.")
        except Exception as exc:
            app.launch_at_sign_in.set(is_launch_at_sign_in_enabled())
            messagebox.showerror("Launch at sign-in", str(exc))
