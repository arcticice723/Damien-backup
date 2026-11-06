from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis_assistant.config import load_settings
from jarvis_assistant.speech_diagnostics import run_speech_diagnostics


def main() -> int:
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    settings = load_settings()
    diagnostics = run_speech_diagnostics(
        load_whisper=True,
        init_tts=True,
        microphone_device_index=settings.microphone_device_index,
    )
    print(f"sounddevice import: {'OK' if diagnostics.sounddevice_available else 'FAILED'}")
    print("Microphone devices:")
    if diagnostics.microphone_devices:
        for device in diagnostics.microphone_devices:
            print(f"  {device}")
    else:
        print("  <none found>")
    print(
        "Selected microphone: "
        f"{diagnostics.selected_microphone_device_index} "
        f"{diagnostics.selected_microphone_device_name or 'unavailable'}"
    )
    print(f"faster-whisper import: {'OK' if diagnostics.faster_whisper_available else 'FAILED'}")
    print(f"tiny CPU/int8 model load: {'OK' if diagnostics.whisper_cpu_tiny_available else 'FAILED'}")
    print(f"Whisper detail: {diagnostics.whisper_detail}")
    print(f"pyttsx3 import: {'OK' if diagnostics.pyttsx3_available else 'FAILED'}")
    print(f"TTS init: {'OK' if diagnostics.tts_available else 'FAILED'}")
    print(f"TTS detail: {diagnostics.tts_detail}")
    return 0 if diagnostics.sounddevice_available and diagnostics.faster_whisper_available and diagnostics.pyttsx3_available else 1


if __name__ == "__main__":
    raise SystemExit(main())
