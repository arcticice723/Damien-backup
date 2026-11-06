from __future__ import annotations

from typing import Any


def mic_privacy_status(enabled: bool) -> str:
    if enabled:
        return "Microphone enabled. No recording occurs until push-to-talk in this stage."
    return "Privacy control active: microphone capture is stopped."


class MicPrivacyController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def toggle_mic(self) -> None:
        app = self.app
        if app.mic_enabled.get():
            app.listen_indicator.configure(text="Mic ready", bg="#1f4f7a")
            app.status.set(mic_privacy_status(True))
            app.voice_summary.set("Microphone ready")
            app.privacy_summary.set("Local mic processing enabled")
            if app.wake_enabled.get():
                app._start_wake_detector()
        else:
            app._stop_speaking()
            if app.wake_detector:
                app.wake_detector.stop()
                app._log_voice("wake_phrase_state: stopped due to microphone mute")
            app.listen_indicator.configure(text="Mic muted", bg="#7a2630")
            app.status.set(mic_privacy_status(False))
            app.voice_summary.set("Microphone muted")
            app.wake_summary.set("Wake phrase paused")
            app.privacy_summary.set("Microphone capture stopped")
