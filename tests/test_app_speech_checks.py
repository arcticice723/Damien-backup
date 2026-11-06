import unittest
from dataclasses import dataclass

from jarvis_assistant.app_speech_checks import microphone_result_events


@dataclass(frozen=True)
class Recording:
    volume_percent: int
    rms: float = 0.1
    peak: float = 0.5
    device_name: str = "Mic"
    device_index: int | None = 1
    sample_rate: int = 16000
    near_silence: bool = False


class AppSpeechChecksTests(unittest.TestCase):
    def test_microphone_result_events_report_captured_sound(self):
        events = microphone_result_events(Recording(volume_percent=67))

        self.assertEqual(events[-1], ("wake_status", "Microphone test captured sound. Volume 67%."))
        self.assertEqual(events[0][0], "microphone_volume")

    def test_microphone_result_events_report_near_silence_as_speech_error(self):
        events = microphone_result_events(Recording(volume_percent=0, near_silence=True))

        self.assertEqual(
            events[-1],
            ("speech_error", "This microphone is not picking up sound. Choose another microphone in Settings."),
        )


if __name__ == "__main__":
    unittest.main()
