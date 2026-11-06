import sys
import unittest
from unittest.mock import patch

from jarvis_assistant.audio import resolve_input_device_settings


class FakeSoundDevice:
    def __init__(self):
        self.devices = [
            {"name": "Monitor", "hostapi": 0, "max_input_channels": 0, "default_samplerate": 48000},
            {"name": "Stereo Mix", "hostapi": 0, "max_input_channels": 2, "default_samplerate": 48000},
            {"name": "Headset Microphone", "hostapi": 0, "max_input_channels": 1, "default_samplerate": 48000},
        ]
        self.hostapis = [{"name": "Windows WDM-KS"}]

    def query_devices(self, device=None, kind=None):
        if kind == "input":
            raise RuntimeError("no system input default")
        if device is None:
            return self.devices
        return self.devices[device]

    def query_hostapis(self):
        return self.hostapis

    def check_input_settings(self, device=None, channels=1, samplerate=16000, dtype="int16"):
        del channels, dtype
        if device == 1 and samplerate == 48000:
            return
        if device == 2 and samplerate == 48000:
            return
        raise RuntimeError("unsupported input settings")


class AudioDeviceSelectionTests(unittest.TestCase):
    def test_output_only_saved_device_falls_back_to_preferred_microphone(self):
        fake_sounddevice = FakeSoundDevice()

        with patch.dict(sys.modules, {"sounddevice": fake_sounddevice}):
            device_index, sample_rate = resolve_input_device_settings(0, 16000)

        self.assertEqual(device_index, 2)
        self.assertEqual(sample_rate, 48000)

    def test_valid_saved_device_keeps_device_but_uses_supported_rate(self):
        fake_sounddevice = FakeSoundDevice()

        with patch.dict(sys.modules, {"sounddevice": fake_sounddevice}):
            device_index, sample_rate = resolve_input_device_settings(1, 16000)

        self.assertEqual(device_index, 1)
        self.assertEqual(sample_rate, 48000)


if __name__ == "__main__":
    unittest.main()
