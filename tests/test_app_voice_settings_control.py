import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jarvis_assistant.app_voice_settings_control import (
    VoiceSettingsController,
    voice_profile_settings_update,
    voice_volume_settings_update,
)


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class AppVoiceSettingsControlTests(unittest.TestCase):
    def test_voice_profile_settings_update_preserves_volume_and_rate(self):
        self.assertEqual(
            voice_profile_settings_update("Zira", "en_US-lessac-high", "175", 0.42),
            {
                "tts_voice_name": "Zira",
                "piper_voice_name": "en_US-lessac-high",
                "tts_rate": 175,
                "tts_volume": 0.42,
            },
        )

    def test_voice_volume_settings_update_converts_percent_to_tts_volume(self):
        self.assertEqual(voice_volume_settings_update(65), {"tts_volume": 0.65})
        self.assertEqual(voice_volume_settings_update(-20), {"tts_volume": 0.0})
        self.assertEqual(voice_volume_settings_update(140), {"tts_volume": 1.0})

    def test_save_selected_voice_volume_updates_settings_and_refreshes_tts(self):
        app = SimpleNamespace(
            voice_volume_choice=FakeVar(65),
            voice_volume_display=FakeVar("100%"),
            tts_status=FakeVar("Voice: checking..."),
            voice_summary=FakeVar("Voice systems checking"),
            tts=object(),
            _log_voice=lambda _message: None,
        )
        reloaded = SimpleNamespace(tts_volume=0.65)

        with patch("jarvis_assistant.app_voice_settings_control.update_settings") as update_settings:
            with patch("jarvis_assistant.app_voice_settings_control.load_settings", return_value=reloaded):
                VoiceSettingsController(app).save_selected_voice_volume()

        update_settings.assert_called_once_with({"tts_volume": 0.65})
        self.assertIs(app.settings, reloaded)
        self.assertIsNone(app.tts)
        self.assertEqual(app.voice_volume_display.get(), "65%")
        self.assertEqual(app.tts_status.get(), "Voice volume: 65%")
        self.assertEqual(app.voice_summary.get(), "Voice volume: 65%")


if __name__ == "__main__":
    unittest.main()
