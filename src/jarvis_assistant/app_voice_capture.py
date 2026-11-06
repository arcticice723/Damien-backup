from __future__ import annotations

from typing import Any

from .app_helpers import describe_recording, recording_volume_text
from .audio_feedback import command_captured_cue, play_command_captured
from .speech import WhisperTranscriber


def near_silence_error() -> str:
    return "This microphone is not picking up sound. Choose another microphone in Settings."


def capture_text_events(text: str, *, wake_command: bool) -> list[tuple[str, object]]:
    if wake_command:
        return [("wake_command_heard", text or "nothing"), ("user_text", text)]
    return [("user_text", text)]


class DamienVoiceCaptureRunner:
    def __init__(self, app: Any) -> None:
        self.app = app

    def transcribe_push_to_talk(self) -> None:
        app = self.app
        try:
            result = app.recorder.stop()
            app._log_voice(f"recording_stopped: push-to-talk; {describe_recording(result)}")
            app.events.put(("microphone_volume", recording_volume_text(result)))
            if result.near_silence:
                app._log_voice(f"near_silence_detected: push-to-talk; {describe_recording(result)}")
                app.events.put(("speech_error", near_silence_error()))
                return
            transcriber = self._transcriber()
            text = transcriber.transcribe(result.path)
            app._log_voice(f"transcription_text: {text!r}")
            for event in capture_text_events(text, wake_command=False):
                app.events.put(event)
        except Exception as exc:
            app._log_voice(f"transcription_failed: {exc}")
            app.events.put(("speech_error", str(exc)))
        finally:
            app._resume_wake_detector("push-to-talk transcription finished")

    def record_wake_command(self) -> None:
        app = self.app
        try:
            from .audio import record_fixed_wav_with_level

            result = record_fixed_wav_with_level(
                app.settings.wake_command_seconds,
                device_index=app.settings.microphone_device_index,
            )
            app._log_voice(f"wake_command_recording: {describe_recording(result)}")
            app.events.put(("microphone_volume", recording_volume_text(result)))
            if result.near_silence:
                app.events.put(("speech_error", near_silence_error()))
                return
            transcriber = self._transcriber()
            text = transcriber.transcribe(result.path)
            app._log_voice(f"transcription_text: {text!r}")
            app._play_wake_feedback(command_captured_cue(app.settings.wake_thinking_cue), play_command_captured)
            for event in capture_text_events(text, wake_command=True):
                app.events.put(event)
        except Exception as exc:
            app.events.put(("speech_error", str(exc)))
        finally:
            app.wake_command_gate.finish()
            app._resume_wake_detector("wake command finished")

    def _transcriber(self) -> WhisperTranscriber:
        app = self.app
        if app.transcriber is None:
            app.transcriber = WhisperTranscriber(
                app.settings.whisper_model,
                app.settings.whisper_device,
                app.settings.whisper_compute_type,
                beam_size=app.settings.whisper_beam_size,
                vocabulary=app.settings.speech_vocabulary,
                corrections=app.settings.speech_corrections,
            )
            app.active_stt_device.set(f"STT: {app.transcriber.active_device}/{app.transcriber.active_compute_type}")
            if getattr(app.transcriber, "status_message", ""):
                app.status.set(app.transcriber.status_message)
        return app.transcriber
