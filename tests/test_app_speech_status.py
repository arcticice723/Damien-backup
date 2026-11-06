import unittest
from dataclasses import dataclass

from jarvis_assistant.app_speech_status import speech_error_updates, speech_status_view


@dataclass(frozen=True)
class Diagnostics:
    sounddevice_available: bool = True
    microphone_devices: tuple[str, ...] = ("Mic 1",)
    faster_whisper_available: bool = True
    piper_available: bool = False
    pyttsx3_available: bool = True
    selected_microphone_device_name: str = "USB Microphone"
    selected_output_device_name: str = "Headphones"


@dataclass(frozen=True)
class Settings:
    tts_engine: str = "pyttsx3"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"


class AppSpeechStatusTests(unittest.TestCase):
    def test_speech_status_view_summarizes_available_voice_stack(self):
        view = speech_status_view(Diagnostics(), Settings())

        self.assertEqual(view.mic_status, "Microphone: available - USB Microphone")
        self.assertEqual(view.wake_dependency_status, "Wake phrase: available")
        self.assertEqual(view.tts_status, "Voice: Windows SAPI available - Headphones")
        self.assertEqual(view.active_stt_device, "STT: cpu/int8")
        self.assertEqual(view.voice_summary, "Windows SAPI ready - Headphones")
        self.assertIsNone(view.wake_summary)

    def test_speech_status_view_reports_missing_dependencies_with_defaults(self):
        view = speech_status_view(
            Diagnostics(
                sounddevice_available=False,
                microphone_devices=(),
                faster_whisper_available=False,
                piper_available=False,
                pyttsx3_available=False,
                selected_microphone_device_name="",
                selected_output_device_name="",
            ),
            Settings(tts_engine="piper", whisper_device="cuda", whisper_compute_type="float16"),
        )

        self.assertEqual(view.mic_status, "Microphone: unavailable")
        self.assertEqual(view.wake_dependency_status, "Wake phrase: unavailable")
        self.assertEqual(view.tts_status, "Voice: unavailable")
        self.assertEqual(view.active_stt_device, "STT: cuda/float16")
        self.assertEqual(view.voice_summary, "Voice unavailable")
        self.assertEqual(view.wake_summary, "Wake phrase unavailable")

    def test_speech_error_updates_targets_microphone_and_wake_phrase_failures(self):
        sounddevice = speech_error_updates("No module named sounddevice")
        whisper = speech_error_updates("cublas failed while loading faster-whisper")

        self.assertEqual(sounddevice["mic_status"], "Microphone: unavailable - install sounddevice into .venv")
        self.assertEqual(sounddevice["voice_summary"], "Microphone unavailable")
        self.assertEqual(whisper["wake_dependency_status"], "Wake phrase: unavailable - speech recognition failed")
        self.assertEqual(whisper["wake_summary"], "Wake phrase unavailable")
        self.assertIn("cublas failed", whisper["wake_status"])


if __name__ == "__main__":
    unittest.main()
