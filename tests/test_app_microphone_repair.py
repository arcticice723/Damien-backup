import unittest

from jarvis_assistant.app_microphone_repair import repaired_microphone_settings
from jarvis_assistant.audio import InputDevice


class AppMicrophoneRepairTests(unittest.TestCase):
    def test_repaired_microphone_settings_matches_saved_name_when_index_is_stale(self):
        devices = [
            InputDevice(1, "Laptop Microphone Array", "Windows", 2, 48000),
            InputDevice(4, "HyperX QuadCast Microphone", "Windows", 1, 48000),
        ]

        self.assertEqual(
            repaired_microphone_settings(
                saved_index=9,
                saved_name="HyperX QuadCast Microphone",
                devices=devices,
            ),
            {"microphone_device_index": 4, "microphone_device_name": "HyperX QuadCast Microphone"},
        )

    def test_repaired_microphone_settings_keeps_valid_saved_index(self):
        devices = [InputDevice(4, "HyperX QuadCast Microphone", "Windows", 1, 48000)]

        self.assertIsNone(
            repaired_microphone_settings(
                saved_index=4,
                saved_name="HyperX QuadCast Microphone",
                devices=devices,
            )
        )


if __name__ == "__main__":
    unittest.main()
