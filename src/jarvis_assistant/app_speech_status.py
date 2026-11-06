from __future__ import annotations

from dataclasses import dataclass

from .app_helpers import tts_engine_label
from .speech import TextToSpeech


@dataclass(frozen=True)
class SpeechStatusView:
    mic_status: str
    wake_dependency_status: str
    tts_status: str
    active_stt_device: str
    voice_summary: str
    wake_summary: str | None = None


def speech_status_view(diagnostics: object, settings: object) -> SpeechStatusView:
    mic_ok = bool(getattr(diagnostics, "sounddevice_available", False)) and bool(
        getattr(diagnostics, "microphone_devices", [])
    )
    whisper_ok = bool(getattr(diagnostics, "faster_whisper_available", False))
    tts_ok = bool(getattr(diagnostics, "piper_available", False)) or bool(getattr(diagnostics, "pyttsx3_available", False))
    selected_name = getattr(diagnostics, "selected_microphone_device_name", "") or "System default microphone"
    selected_output = getattr(diagnostics, "selected_output_device_name", "") or TextToSpeech.DEFAULT_OUTPUT
    engine_label = tts_engine_label(getattr(settings, "tts_engine"))
    return SpeechStatusView(
        mic_status=f"Microphone: available - {selected_name}" if mic_ok else "Microphone: unavailable",
        wake_dependency_status="Wake phrase: available" if whisper_ok else "Wake phrase: unavailable",
        tts_status=f"Voice: {engine_label} available - {selected_output}" if tts_ok else "Voice: unavailable",
        active_stt_device=f"STT: {getattr(settings, 'whisper_device')}/{getattr(settings, 'whisper_compute_type')}",
        voice_summary=f"{engine_label} ready - {selected_output}" if tts_ok else "Voice unavailable",
        wake_summary=None if whisper_ok else "Wake phrase unavailable",
    )


def speech_error_updates(message: str) -> dict[str, str]:
    updates: dict[str, str] = {}
    lowered = message.lower()
    if "sounddevice" in lowered:
        updates["mic_status"] = "Microphone: unavailable - install sounddevice into .venv"
        updates["voice_summary"] = "Microphone unavailable"
    if "faster-whisper" in lowered or "whisper" in lowered or "cublas" in lowered:
        updates["wake_dependency_status"] = "Wake phrase: unavailable - speech recognition failed"
        updates["wake_status"] = f"Error: {message}"
        updates["wake_summary"] = "Wake phrase unavailable"
    return updates
