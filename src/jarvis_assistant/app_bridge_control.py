from __future__ import annotations

import os
from typing import Any

from .discord_bot import DiscordBotBridge
from .config import load_settings, update_settings
from .remote import RemoteControlServer
from .tray import TrayController


def discord_bot_token(env_token: str, settings_token: str) -> str:
    return env_token.strip() or settings_token.strip()


class AppBridgeController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def start_tray(self) -> None:
        app = self.app
        app.tray = TrayController(
            restore=app._restore_from_tray,
            quit_app=app._quit_from_tray,
            toggle_mic=app._toggle_mic_from_tray,
            status_text=app._tray_status_text,
        )
        app.tray.start()
        if app.tray.available:
            app.status.set("Ready. Closing the window keeps Damien running in the tray.")
            app.privacy_summary.set("Background tray mode available")
        elif app.tray.error:
            app._log_connection(app.tray.error)

    def start_remote_control(self) -> None:
        app = self.app
        if not app.settings.remote_control_enabled:
            app._set_remote_status("Remote: disabled")
            return
        pin = app._remote_pin()
        try:
            app.remote = RemoteControlServer(
                app.settings.remote_control_host,
                app.settings.remote_control_port,
                pin,
                command_callback=lambda request_id, text: app.events.put(("remote_user_text", (request_id, text))),
                status_callback=app._remote_status_payload,
            )
            app.remote.start()
            tailnet_url = app.remote.tailscale_url
            tailscale_serve_url = app.remote.tailscale_serve_url
            status = f"Home Wi-Fi: {app.remote.local_url}"
            if tailscale_serve_url:
                status += f" | Away (Tailscale HTTPS): {tailscale_serve_url}"
            elif tailnet_url:
                status += f" | Away (Tailscale tunnel): {tailnet_url}"
                status += " | run Tailscale Serve once for HTTPS"
            elif app.remote.tailscale_installed:
                status += " | Away access: sign in to Tailscale on this PC and your phone"
            else:
                status += " | Away access: install and sign in to Tailscale on this PC and your phone"
            status += " | password protected"
            app._set_remote_status(status)
            app._log_connection(f"Remote control started at {status} (password hidden)")
        except Exception as exc:
            app._set_remote_status(f"Remote unavailable: {exc}")
            app._log_connection(f"Remote control failed: {exc}")

    def save_remote_password(self) -> None:
        app = self.app
        password = app.remote_password_choice.get().strip()
        if len(password) < 12:
            app.remote_pin_display.set("Use at least 12 characters for the phone password.")
            return
        if app.remote is not None:
            app.remote.stop()
            app.remote = None
        update_settings({"remote_control_pin": password})
        app.settings = load_settings()
        app.remote_password_choice.set("")
        app.remote_pin_display.set("Fixed phone password saved. Reconnect your phone with the new password.")
        app._start_remote_control()

    def start_discord_bridge(self) -> None:
        app = self.app
        if not app.settings.discord_bot_enabled:
            app._log_connection("Discord bot: disabled")
            return
        token = discord_bot_token(os.environ.get("DAMIEN_DISCORD_BOT_TOKEN", ""), app.settings.discord_bot_token)
        if not token:
            message = "Discord bot needs a bot token in DAMIEN_DISCORD_BOT_TOKEN or config/settings.json."
            app._log_connection(message)
            app.privacy_summary.set("Discord bot needs token")
            return
        if not app.remote:
            app._log_connection("Discord bot unavailable: local remote control is not running.")
            return
        base_url = f"http://127.0.0.1:{app.remote.port}"
        app.discord_bridge = DiscordBotBridge(
            token,
            base_url,
            app.settings.remote_control_pin,
            allowed_channel_ids=app.settings.discord_bot_allowed_channel_ids,
            status_callback=app._log_connection,
        )
        app.discord_bridge.start()
        app._log_connection("Discord bot: starting")
