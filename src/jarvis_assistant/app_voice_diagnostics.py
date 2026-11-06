from __future__ import annotations

from typing import Any

from .ai import ChatMessage
from .app_helpers import describe_recording, recording_volume_text, tts_engine_label
from .speech import TextToSpeech, WhisperTranscriber
from .speech_diagnostics import run_speech_diagnostics


def diagnostics_step_line(number: int, name: str, ok: bool, detail: str, fix: str = "") -> str:
    status = "PASS" if ok else "FAIL"
    line = f"{number}. {name}: {status} - {detail}"
    if not ok and fix:
        line += f"\n   Fix: {fix}"
    return line


class DamienVoiceDiagnosticsRunner:
    def __init__(self, app: Any) -> None:
        self.app = app
        self.lines: list[str] = []

    def step(self, number: int, name: str, ok: bool, detail: str, fix: str = "") -> None:
        line = diagnostics_step_line(number, name, ok, detail, fix)
        self.lines.append(line)
        self.app._log_voice(f"voice_diagnostics_step_{number}: {line}")

    def run(self) -> None:
        app = self.app
        diagnostics = run_speech_diagnostics(
            load_whisper=False,
            init_tts=False,
            microphone_device_index=app.settings.microphone_device_index,
            output_device_name=app.settings.output_device_name,
        )
        self.step(
            1,
            "Python/venv",
            diagnostics.running_from_venv,
            diagnostics.python_executable,
            r"Run .\scripts\setup.ps1, then launch with .\scripts\run.ps1.",
        )
        self.step(
            2,
            "microphone devices",
            diagnostics.sounddevice_available and bool(diagnostics.microphone_devices),
            "; ".join(diagnostics.microphone_devices[:5]) if diagnostics.microphone_devices else "No input devices found.",
            "Install dependencies with .\\scripts\\setup.ps1 and check Windows microphone privacy/input settings.",
        )
        try:
            from .audio import record_fixed_wav_with_level

            app._log_voice(
                "diagnostics_recording_started; "
                f"device_index={app.settings.microphone_device_index}; "
                f"name={app.settings.microphone_device_name or 'System default microphone'!r}"
            )
            recording = record_fixed_wav_with_level(1.25, device_index=app.settings.microphone_device_index)
            wav_path = recording.path
            app._log_voice(f"diagnostics_recording_stopped: {wav_path}; {describe_recording(recording)}")
            app.events.put(("microphone_volume", recording_volume_text(recording)))
            self.step(
                3,
                "microphone recording",
                not recording.near_silence,
                f"Captured {wav_path}. {recording_volume_text(recording)}",
                "This microphone is not picking up sound. Choose another microphone in Settings.",
            )
        except Exception as exc:
            self.step(3, "microphone recording", False, str(exc), "Run .\\scripts\\setup.ps1 and verify the selected Windows input device.")
            wav_path = None

        try:
            transcriber = WhisperTranscriber(
                app.settings.whisper_model,
                app.settings.whisper_device,
                app.settings.whisper_compute_type,
                beam_size=app.settings.whisper_beam_size,
            )
            app.events.put(("active_stt", f"STT: {transcriber.active_device}/{transcriber.active_compute_type}"))
            self.step(4, "whisper/faster-whisper load", True, transcriber.status_message)
        except Exception as exc:
            transcriber = None
            self.step(4, "whisper/faster-whisper load", False, str(exc), "Run .\\scripts\\setup.ps1. Keep speech settings on cpu/int8.")

        if transcriber and wav_path:
            try:
                text = transcriber.transcribe(wav_path)
                app._log_voice(f"diagnostics_transcription_text: {text!r}")
                self.step(
                    5,
                    "speech transcription test",
                    bool(text.strip()),
                    f"Heard: {text!r}" if text.strip() else "No speech recognized in the short test recording.",
                    "Speak clearly during the diagnostic recording; check microphone volume/input device.",
                )
            except Exception as exc:
                self.step(5, "speech transcription test", False, str(exc), "Keep speech settings on cpu/int8 and rerun setup.")
        else:
            self.step(5, "speech transcription test", False, "Skipped because recording or Whisper load failed.")

        ollama_status = app.ai.check_connection()
        self.step(6, "Ollama connection", ollama_status.reachable, f"{ollama_status.url}: {ollama_status.detail}", "Start Ollama and press Retry.")

        try:
            app._log_voice(f"ollama_request_started: diagnostics model={app.ai.model}")
            response = "".join(
                event.content
                for event in app.ai.stream([ChatMessage("user", "Reply with exactly: voice diagnostics ok")], tools=None)
                if event.kind == "text"
            ).strip()
            app._log_voice(f"ollama_request_finished: diagnostics response={response!r}")
            self.step(7, "model response", bool(response), response or "No model text returned.", "Check logs/damien.log and model selection.")
        except Exception as exc:
            self.step(7, "model response", False, str(exc), "Confirm Ollama is running and the configured model exists.")

        try:
            app._log_voice("tts_started: diagnostics")
            tts = TextToSpeech(
                app.settings.output_device_name,
                app.settings.tts_voice_name,
                app.settings.tts_rate,
                app.settings.tts_volume,
                app.settings.tts_engine,
                app.settings.piper_voice_name,
            )
            tts.speak("Damien voice diagnostics complete.")
            app._log_voice("tts_finished: diagnostics")
            self.step(
                8,
                "TTS voice test",
                True,
                f"{tts_engine_label(app.settings.tts_engine)} spoke using {app.settings.output_device_name}.",
            )
        except Exception as exc:
            self.step(8, "TTS voice test", False, str(exc), "Run .\\scripts\\setup.ps1 and check Windows output device/volume.")

        wake_state = "enabled" if app.wake_enabled.get() else "disabled"
        wake_running = bool(app.wake_detector and app.wake_detector.is_running())
        self.step(
            9,
            "wake phrase status",
            True,
            f"Wake phrase is {wake_state}; detector running={wake_running}; push-to-talk fallback remains available.",
        )

        app.events.put(("voice_diagnostics", "\n".join(self.lines)))
