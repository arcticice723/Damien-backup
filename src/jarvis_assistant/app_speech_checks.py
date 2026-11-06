from __future__ import annotations

from typing import Any

from .app_helpers import describe_recording, recording_volume_text
from .speech import TextToSpeech
from .speech_diagnostics import run_speech_diagnostics


def microphone_result_events(result: object) -> list[tuple[str, object]]:
    events: list[tuple[str, object]] = [("microphone_volume", recording_volume_text(result))]
    if getattr(result, "near_silence"):
        events.append(("speech_error", "This microphone is not picking up sound. Choose another microphone in Settings."))
    else:
        events.append(("wake_status", f"Microphone test captured sound. Volume {getattr(result, 'volume_percent')}%."))
    return events


class DamienSpeechCheckRunner:
    def __init__(self, app: Any) -> None:
        self.app = app

    def run_microphone_test(self) -> None:
        app = self.app
        try:
            from .audio import record_fixed_wav_with_level

            app._log_voice(
                "test_microphone_started; "
                f"device_index={app.settings.microphone_device_index}; "
                f"name={app.settings.microphone_device_name or 'System default microphone'!r}"
            )
            result = record_fixed_wav_with_level(1.0, device_index=app.settings.microphone_device_index)
            app._log_voice(f"test_microphone_finished; {describe_recording(result)}")
            for event in microphone_result_events(result):
                app.events.put(event)
            app.events.put(("speech_status", self._speech_status()))
        except Exception as exc:
            app.events.put(("speech_error", str(exc)))

    def run_voice_test(self) -> None:
        app = self.app
        try:
            tts = TextToSpeech(
                app.settings.output_device_name,
                app.settings.tts_voice_name,
                app.settings.tts_rate,
                app.settings.tts_volume,
                app.settings.tts_engine,
                app.settings.piper_voice_name,
            )
            app._log_voice("tts_started: test voice")
            tts.speak("Good evening. Damien voice systems are online.")
            app._log_voice("tts_finished: test voice")
            app.events.put(("speech_status", self._speech_status()))
        except Exception as exc:
            app.events.put(("speech_error", str(exc)))

    def _speech_status(self) -> object:
        return run_speech_diagnostics(
            load_whisper=False,
            init_tts=False,
            microphone_device_index=self.app.settings.microphone_device_index,
            output_device_name=self.app.settings.output_device_name,
        )
