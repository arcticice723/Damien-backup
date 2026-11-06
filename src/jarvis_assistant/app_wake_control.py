from __future__ import annotations

import threading
from typing import Any

from .app_helpers import describe_recording
from .app_voice_capture import DamienVoiceCaptureRunner
from .audio_feedback import play_wake_acknowledgement, wake_acknowledgement_cue
from .config import update_settings
from .wake import WakePhraseDetector


def wake_phrase_settings_update(enabled: bool) -> dict[str, bool]:
    return {"wake_phrase_enabled": enabled}


class WakeController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def toggle_wake_phrase(self) -> None:
        app = self.app
        if app.wake_enabled.get():
            if not app.mic_enabled.get():
                app.wake_status.set("Disabled")
                app.wake_summary.set("Wake phrase waiting for mic")
                update_settings(wake_phrase_settings_update(True))
                return
            update_settings(wake_phrase_settings_update(True))
            self.start_detector()
        else:
            if app.wake_detector:
                app.wake_detector.stop()
                app._log_voice("wake_phrase_state: disabled")
            update_settings(wake_phrase_settings_update(False))
            app.wake_status.set("Disabled")
            app.wake_summary.set("Wake phrase off")

    def start_detector(self) -> None:
        app = self.app
        if app.wake_detector and app.wake_detector.is_running():
            return
        app.wake_detector = WakePhraseDetector(
            wake_phrase=app.settings.wake_phrase,
            wake_phrase_variants=app.settings.wake_phrase_variants,
            wake_sensitivity=app.settings.wake_sensitivity,
            on_detected=lambda: app.events.put(("wake_detected", "")),
            on_status=lambda text: app.events.put(("wake_status", text)),
            check_seconds=app.settings.wake_check_seconds,
            model_name=app.settings.wake_whisper_model,
            device=app.settings.wake_whisper_device,
            compute_type=app.settings.wake_whisper_compute_type,
            microphone_device_index=app.settings.microphone_device_index,
            beam_size=app.settings.wake_whisper_beam_size,
            on_audio_level=lambda result: app._log_voice(f"wake_phrase_recording: {describe_recording(result)}"),
            on_transcription=lambda text, matched, phrase: app._log_voice(
                f"wake_phrase_transcription: text={text!r}; matched={matched}; phrase={phrase!r}; "
                f"sensitivity={app.settings.wake_sensitivity}"
            ),
        )
        app._log_voice(
            "wake_phrase_state: starting; "
            f"device_index={app.settings.microphone_device_index}; "
            f"name={app.settings.microphone_device_name or 'System default microphone'!r}; "
            f"variants={app.settings.wake_phrase_variants!r}; sensitivity={app.settings.wake_sensitivity}"
        )
        app.wake_status.set("Listening")
        app.wake_summary.set("Listening for wake phrase")
        app.wake_detector.start()

    def handle_wake_detected(self) -> None:
        app = self.app
        if not app.mic_enabled.get():
            return
        if not app.wake_command_gate.try_begin():
            app._log_voice("wake_detected_ignored: command recording already active")
            return
        self.pause_detector("wake command recording")
        app._play_wake_feedback(wake_acknowledgement_cue(app.settings.wake_listening_cue), play_wake_acknowledgement)
        app._log_voice(f"wake_acknowledgement_cue: mode={app.settings.wake_acknowledgement_mode!r}")
        app.status.set('Heard wake phrase. Listening for your request...')
        app.mascot_last_heard.set("Listening...")
        app.wake_status.set("Listening for command")
        app.wake_summary.set("Wake detected")
        app.listen_indicator.configure(text="Wake detected", bg="#1f7a4d")
        threading.Thread(target=app._record_wake_command, daemon=True).start()

    def record_wake_command(self) -> None:
        DamienVoiceCaptureRunner(self.app).record_wake_command()

    def pause_detector(self, reason: str) -> None:
        app = self.app
        if app.wake_detector and app.wake_detector.is_running():
            app._log_voice(f"wake_phrase_state: paused ({reason})")
            app.wake_detector.stop()

    def resume_detector(self, reason: str) -> None:
        app = self.app
        if app.wake_enabled.get() and app.mic_enabled.get():
            if not (app.wake_detector and app.wake_detector.is_running()):
                app._log_voice(f"wake_phrase_state: resuming ({reason})")
                self.start_detector()
