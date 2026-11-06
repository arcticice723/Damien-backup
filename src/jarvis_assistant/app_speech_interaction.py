from __future__ import annotations

import threading
from tkinter import messagebox
from typing import Any

from .app_voice_capture import DamienVoiceCaptureRunner
from .speech import TextToSpeech


def wake_feedback_action(mode: str, sound_enabled: bool) -> str:
    if mode == "silent":
        return "none"
    if mode == "voice":
        return "voice"
    return "tone" if sound_enabled else "none"


class SpeechInteractionController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def start_recording(self) -> None:
        app = self.app
        if not app.mic_enabled.get():
            app.status.set("Microphone is muted by privacy control.")
            app._log_voice("push_to_talk_blocked: microphone muted")
            return
        try:
            app._pause_wake_detector("push-to-talk recording")
            app._log_voice(
                "recording_started: push-to-talk; "
                f"device_index={app.settings.microphone_device_index}; "
                f"name={app.settings.microphone_device_name or 'System default microphone'!r}; "
                f"sample_rate={app.recorder.sample_rate}"
            )
            app.recorder.start()
            app.status.set("Listening, sir. Release to send.")
            app.listen_indicator.configure(text="Listening", bg="#1f7a4d")
            app.voice_summary.set("Listening on selected microphone")
        except Exception as exc:
            app._log_voice(f"recording_start_failed: {exc}")
            messagebox.showerror("Microphone error", str(exc))

    def stop_recording(self) -> None:
        app = self.app
        if not app.mic_enabled.get():
            return
        app.status.set("Transcribing...")
        app.listen_indicator.configure(text="Transcribing", bg="#8a6d1d")
        app.voice_summary.set("Transcribing local audio")
        app._log_voice("recording_stopped: push-to-talk")
        threading.Thread(target=app._transcribe_recording, daemon=True).start()

    def transcribe_recording(self) -> None:
        DamienVoiceCaptureRunner(self.app).transcribe_push_to_talk()

    def start_streaming_speech(self) -> None:
        self.app.speech.start_streaming()

    def queue_streaming_speech(self, text: str) -> None:
        self.app.speech.queue_streaming_text(text)

    def finish_streaming_speech(self) -> None:
        self.app.speech.finish_streaming()

    def speak(self, text: str) -> None:
        self.app.speech.speak(text)

    def queue_spoken_cue(self, text: str) -> None:
        self.app.speech.speak_short_cue(text)

    def speak_short_cue(self, text: str) -> None:
        self.app.speech.speak_short_cue(text)

    def play_wake_feedback(self, cue_text: str, tone_callback) -> None:
        app = self.app
        action = wake_feedback_action(app.settings.wake_acknowledgement_mode, app.settings.wake_acknowledgement_sound_enabled)
        if action == "voice":
            app._queue_spoken_cue(cue_text)
        elif action == "tone":
            threading.Thread(target=tone_callback, daemon=True).start()

    def stop_speaking(self) -> None:
        self.app.speech.stop()

    def new_tts(self) -> TextToSpeech:
        app = self.app
        if app.tts is None:
            app.tts = TextToSpeech(
                app.settings.output_device_name,
                app.settings.tts_voice_name,
                app.settings.tts_rate,
                app.settings.tts_volume,
                app.settings.tts_engine,
                app.settings.piper_voice_name,
            )
        return app.tts
