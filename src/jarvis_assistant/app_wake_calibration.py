from __future__ import annotations

from typing import Any

from .app_helpers import describe_recording, recording_volume_text
from .config import load_settings, update_settings
from .speech import WhisperTranscriber
from .wake import WakePhraseDetector


def calibration_header_lines(microphone_device_name: str) -> list[str]:
    return [
        "Wake calibration:",
        f"Microphone: {microphone_device_name or 'System default microphone'}",
    ]


def updated_wake_variants(existing: list[str], *, matched: bool, normalized: str) -> list[str]:
    variants = list(existing)
    if matched and normalized and normalized not in variants:
        variants.append(normalized)
    return variants


class DamienWakeCalibrationRunner:
    def __init__(self, app: Any) -> None:
        self.app = app

    def run(self) -> None:
        app = self.app
        was_running = bool(app.wake_detector and app.wake_detector.is_running())
        try:
            from .audio import record_fixed_wav_with_level

            app._pause_wake_detector("wake calibration")
            transcriber = WhisperTranscriber(
                app.settings.wake_whisper_model,
                app.settings.wake_whisper_device,
                app.settings.wake_whisper_compute_type,
                beam_size=app.settings.wake_whisper_beam_size,
            )
            app.events.put(("active_stt", f"STT: {transcriber.active_device}/{transcriber.active_compute_type}"))
            matcher = WakePhraseDetector(
                wake_phrase=app.settings.wake_phrase,
                wake_phrase_variants=app.settings.wake_phrase_variants,
                wake_sensitivity=app.settings.wake_sensitivity,
                on_detected=lambda: None,
                on_status=lambda _text: None,
                check_seconds=app.settings.wake_check_seconds,
                model_name=app.settings.wake_whisper_model,
                device=app.settings.wake_whisper_device,
                compute_type=app.settings.wake_whisper_compute_type,
                microphone_device_index=app.settings.microphone_device_index,
                beam_size=app.settings.wake_whisper_beam_size,
            )
            lines = calibration_header_lines(app.settings.microphone_device_name)
            accepted = list(app.settings.wake_phrase_variants)
            for sample_number in range(1, 4):
                app.events.put(("wake_status", f"Calibration sample {sample_number}/3: listening..."))
                recording = record_fixed_wav_with_level(
                    app.settings.wake_check_seconds,
                    device_index=app.settings.microphone_device_index,
                )
                app._log_voice(f"wake_calibration_recording_{sample_number}: {describe_recording(recording)}")
                app.events.put(("microphone_volume", recording_volume_text(recording)))
                if recording.near_silence:
                    line = f"Sample {sample_number}: This microphone is not picking up sound."
                    lines.append(line)
                    app._log_voice(f"wake_calibration_decision_{sample_number}: near_silence")
                    continue
                text = transcriber.transcribe(recording.path)
                normalized = WakePhraseDetector._normalize(text)
                matched, matched_phrase = matcher.matches(text)
                decision = "accepted" if matched else "not matched"
                lines.append(f"Sample {sample_number}: heard {text!r} -> {decision}")
                app._log_voice(
                    f"wake_calibration_transcription_{sample_number}: text={text!r}; normalized={normalized!r}; "
                    f"matched={matched}; matched_phrase={matched_phrase!r}; sensitivity={app.settings.wake_sensitivity}"
                )
                accepted = updated_wake_variants(accepted, matched=matched, normalized=normalized)
            update_settings({"wake_phrase_variants": accepted})
            app.settings = load_settings()
            saved = ", ".join(app.settings.wake_phrase_variants)
            lines.append(f"Saved variants: {saved}")
            app.events.put(("wake_status", "Calibration complete."))
            app.events.put(("wake_calibration", "\n".join(lines)))
        except Exception as exc:
            app.events.put(("speech_error", str(exc)))
            app.events.put(("wake_status", f"Error: {exc}"))
        finally:
            if was_running or app.wake_enabled.get():
                app._resume_wake_detector("wake calibration finished")
