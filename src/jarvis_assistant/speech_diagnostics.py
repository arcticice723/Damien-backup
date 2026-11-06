from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .audio import device_name, list_input_devices
from .speech import TextToSpeech, WhisperTranscriber, list_piper_voices, list_speech_output_devices


@dataclass(frozen=True)
class SpeechDiagnostics:
    python_executable: str
    sounddevice_available: bool
    microphone_devices: list[str]
    selected_microphone_device_index: int | None
    selected_microphone_device_name: str
    speech_output_devices: list[str]
    selected_output_device_name: str
    faster_whisper_available: bool
    whisper_cpu_tiny_available: bool
    whisper_detail: str
    pyttsx3_available: bool
    piper_available: bool
    piper_voices: list[str]
    tts_available: bool
    tts_detail: str
    running_from_venv: bool


def run_speech_diagnostics(
    load_whisper: bool = False,
    init_tts: bool = False,
    microphone_device_index: int | None = None,
    output_device_name: str = TextToSpeech.DEFAULT_OUTPUT,
) -> SpeechDiagnostics:
    sounddevice_available = _can_import("sounddevice")
    microphone_devices = list_input_devices() if sounddevice_available else []
    faster_whisper_available = _can_import("faster_whisper")
    whisper_cpu_tiny_available = False
    whisper_detail = "Not checked."
    if load_whisper and faster_whisper_available:
        try:
            transcriber = WhisperTranscriber("tiny", "cpu", "int8")
            whisper_cpu_tiny_available = True
            whisper_detail = transcriber.status_message
        except Exception as exc:
            whisper_detail = str(exc)
    elif not faster_whisper_available:
        whisper_detail = "Install faster-whisper into Damien's .venv."

    pyttsx3_available = _can_import("pyttsx3")
    piper_available = _can_import("piper") and bool(list_piper_voices())
    piper_voices = list_piper_voices() if _can_import("piper") else []
    speech_output_devices = list_speech_output_devices() if pyttsx3_available else []
    tts_available = False
    tts_detail = "Not checked."
    if init_tts and (piper_available or pyttsx3_available):
        try:
            TextToSpeech(output_device_name)
            tts_available = True
            engine = "Piper" if piper_available else "pyttsx3"
            tts_detail = f"{engine} initialized. Output: {output_device_name}."
        except Exception as exc:
            tts_detail = str(exc)
    elif not (piper_available or pyttsx3_available):
        tts_detail = "Install piper-tts or pyttsx3 into Damien's .venv."

    return SpeechDiagnostics(
        python_executable=sys.executable,
        sounddevice_available=sounddevice_available,
        microphone_devices=microphone_devices,
        selected_microphone_device_index=microphone_device_index,
        selected_microphone_device_name=device_name(microphone_device_index) if sounddevice_available else "",
        speech_output_devices=speech_output_devices,
        selected_output_device_name=output_device_name,
        faster_whisper_available=faster_whisper_available,
        whisper_cpu_tiny_available=whisper_cpu_tiny_available,
        whisper_detail=whisper_detail,
        pyttsx3_available=pyttsx3_available,
        piper_available=piper_available,
        piper_voices=piper_voices,
        tts_available=tts_available,
        tts_detail=tts_detail,
        running_from_venv=(".venv" in Path(sys.executable).parts),
    )


def _can_import(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False
