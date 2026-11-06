import unittest

from dataclasses import dataclass

from jarvis_assistant.app_helpers import (
    describe_recording,
    microphone_name_tokens,
    recording_volume_text,
    sensitivity_label,
    sensitivity_value,
    short_status_text,
    tts_engine_label,
    tts_engine_value,
)


@dataclass(frozen=True)
class Recording:
    path: str
    duration_seconds: float
    rms: float
    peak: float
    volume_percent: int
    device_index: int = 1
    device_name: str = "Microphone"
    sample_rate: int = 16000


class AppHelperTests(unittest.TestCase):
    def test_microphone_tokens_keep_useful_words(self):
        self.assertEqual(microphone_name_tokens("HyperX QuadCast Microphone"), {"hyperx", "quadcast", "microphone"})

    def test_short_status_text_collapses_and_truncates(self):
        self.assertEqual(short_status_text("Heard:   open   Discord", 18), "Heard: open Dis...")

    def test_tts_engine_labels_round_trip(self):
        self.assertEqual(tts_engine_label("piper"), "Piper Neural")
        self.assertEqual(tts_engine_value("Windows SAPI"), "pyttsx3")

    def test_sensitivity_labels_round_trip(self):
        self.assertEqual(sensitivity_label(0.84), "High")
        self.assertEqual(sensitivity_value("Low"), 0.50)

    def test_recording_text_is_concise(self):
        recording = Recording("clip.wav", 1.25, 0.1, 0.5, 42)

        self.assertIn("device_index=1", describe_recording(recording))
        self.assertEqual(recording_volume_text(recording), "Microphone volume: 42% (RMS 0.10000, peak 0.50000) on Microphone")


if __name__ == "__main__":
    unittest.main()
