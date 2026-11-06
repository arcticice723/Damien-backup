from __future__ import annotations

import threading
from typing import Any

from .app_speech_checks import DamienSpeechCheckRunner
from .app_speech_status import speech_error_updates, speech_status_view
from .app_voice_diagnostics import DamienVoiceDiagnosticsRunner
from .app_wake_calibration import DamienWakeCalibrationRunner
from .speech_diagnostics import run_speech_diagnostics


def muted_microphone_test_message() -> str:
    return "Microphone is muted by privacy control."


class SpeechDiagnosticsController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def refresh_speech_status_async(self) -> None:
        threading.Thread(target=self.app._refresh_speech_status_worker, daemon=True).start()

    def refresh_speech_status_worker(self) -> None:
        app = self.app
        app.events.put((
            "speech_status",
            run_speech_diagnostics(
                load_whisper=False,
                init_tts=False,
                microphone_device_index=app.settings.microphone_device_index,
                output_device_name=app.settings.output_device_name,
            ),
        ))

    def apply_speech_status(self, diagnostics: object) -> None:
        app = self.app
        view = speech_status_view(diagnostics, app.settings)
        app.mic_status.set(view.mic_status)
        app.wake_dependency_status.set(view.wake_dependency_status)
        app.tts_status.set(view.tts_status)
        app.active_stt_device.set(view.active_stt_device)
        app.voice_summary.set(view.voice_summary)
        if view.wake_summary is not None:
            app.wake_summary.set(view.wake_summary)

    def apply_speech_error(self, message: str) -> None:
        app = self.app
        updates = speech_error_updates(message)
        if "mic_status" in updates:
            app.mic_status.set(updates["mic_status"])
        if "voice_summary" in updates:
            app.voice_summary.set(updates["voice_summary"])
        if "wake_dependency_status" in updates:
            app.wake_dependency_status.set(updates["wake_dependency_status"])
        if "wake_status" in updates:
            app.wake_status.set(updates["wake_status"])
        if "wake_summary" in updates:
            app.wake_summary.set(updates["wake_summary"])

    def test_microphone(self) -> None:
        app = self.app
        if not app.mic_enabled.get():
            app.status.set(muted_microphone_test_message())
            return
        app.status.set("Testing microphone for one second...")
        threading.Thread(target=app._test_microphone_worker, daemon=True).start()

    def test_microphone_worker(self) -> None:
        DamienSpeechCheckRunner(self.app).run_microphone_test()

    def test_voice(self) -> None:
        threading.Thread(target=self.app._test_voice_worker, daemon=True).start()

    def test_voice_worker(self) -> None:
        DamienSpeechCheckRunner(self.app).run_voice_test()

    def run_voice_diagnostics(self) -> None:
        app = self.app
        app.status.set("Running voice diagnostics...")
        threading.Thread(target=app._voice_diagnostics_worker, daemon=True).start()

    def voice_diagnostics_worker(self) -> None:
        DamienVoiceDiagnosticsRunner(self.app).run()

    def show_voice_diagnostics(self, text: str) -> None:
        app = self.app
        app._append_line("Voice Diagnostics", text)
        app.status.set("Voice diagnostics finished. See conversation and logs/damien.log.")

    def test_wake_phrase(self) -> None:
        app = self.app
        app.status.set('Wake calibration: say "Hey Damien" for each sample.')
        app.wake_status.set("Calibration recording 3 samples...")
        threading.Thread(target=app._test_wake_phrase_worker, daemon=True).start()

    def test_wake_phrase_worker(self) -> None:
        DamienWakeCalibrationRunner(self.app).run()
