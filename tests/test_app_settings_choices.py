import unittest
from dataclasses import dataclass

from jarvis_assistant.app_settings_choices import (
    appearance_reset_values,
    appearance_settings_update,
    appearance_option_values,
    microphone_options,
    output_device_choice,
    selected_microphone,
    settings_section_titles,
    voice_choice_update,
    voice_option_values,
)
from jarvis_assistant.audio import InputDevice
from jarvis_assistant.speech import TextToSpeech


@dataclass(frozen=True)
class Settings:
    microphone_device_index: int | None = None
    output_device_name: str = TextToSpeech.DEFAULT_OUTPUT
    piper_voice_name: str = TextToSpeech.DEFAULT_PIPER_VOICE
    tts_voice_name: str = TextToSpeech.DEFAULT_VOICE
    tts_engine: str = TextToSpeech.ENGINE_SAPI
    tts_rate: int = TextToSpeech.DEFAULT_RATE


def device(index: int, name: str) -> InputDevice:
    return InputDevice(index=index, name=name, hostapi="WASAPI", max_input_channels=1, default_samplerate=48000)


class AppSettingsChoiceTests(unittest.TestCase):
    def test_microphone_options_include_default_and_select_saved_device(self):
        devices = [device(4, "Headset Mic"), device(9, "Webcam Mic")]

        options = microphone_options(devices, selected_index=9)

        self.assertEqual(options.labels[0], "System default microphone")
        self.assertEqual(options.label_to_index["System default microphone"], None)
        self.assertEqual(options.label_to_index[devices[1].label], 9)
        self.assertEqual(options.selected_label, devices[1].label)

    def test_selected_microphone_returns_default_when_label_is_unknown(self):
        devices = [device(4, "Headset Mic")]

        self.assertEqual(selected_microphone("missing", {"System default microphone": None}, devices), (None, "System default microphone"))

    def test_output_device_choice_uses_saved_device_only_when_available(self):
        self.assertEqual(
            output_device_choice(["Speakers", "Headphones"], "Headphones"),
            ([TextToSpeech.DEFAULT_OUTPUT, "Speakers", "Headphones"], "Headphones"),
        )
        self.assertEqual(output_device_choice(["Speakers"], "Gone")[1], TextToSpeech.DEFAULT_OUTPUT)

    def test_voice_choice_update_selects_first_available_missing_saved_values(self):
        update = voice_choice_update(
            voices=["Zira", "Guy"],
            piper_voices=["en_US-lessac-high"],
            settings=Settings(tts_voice_name="Missing", piper_voice_name="Missing"),
        )

        self.assertEqual(update.voice_values, [TextToSpeech.DEFAULT_VOICE, "Zira", "Guy"])
        self.assertEqual(update.voice_choice, "Guy")
        self.assertEqual(update.piper_voice_choice, "en_US-lessac-high")
        self.assertEqual(update.settings_updates, {"piper_voice_name": "en_US-lessac-high", "tts_voice_name": "Guy"})

    def test_appearance_settings_update_normalizes_empty_values_and_opacity_percent(self):
        update = appearance_settings_update(
            ui_style="",
            accent_color="",
            custom_accent_color="  #ffcc66  ",
            mascot_size="",
            mascot_opacity_percent="82",
            compact_mode=True,
            reduce_glow=True,
        )

        self.assertEqual(update["ui_style"], "hybrid")
        self.assertEqual(update["accent_color"], "cyan")
        self.assertEqual(update["custom_accent_color"], "#ffcc66")
        self.assertEqual(update["mascot_size"], "normal")
        self.assertEqual(update["mascot_opacity"], 0.82)
        self.assertTrue(update["compact_mode"])
        self.assertTrue(update["reduce_glow"])

    def test_appearance_reset_values_match_damien_defaults(self):
        self.assertEqual(
            appearance_reset_values(),
            {
                "ui_style": "hybrid",
                "accent_color": "cyan",
                "custom_accent_color": "",
                "mascot_size": "normal",
                "mascot_opacity_percent": "94",
                "compact_mode": False,
                "reduce_glow": False,
            },
        )

    def test_settings_section_titles_keep_settings_tab_order(self):
        self.assertEqual(
            settings_section_titles(),
            ["Local AI", "Voice", "Automation", "Diagnostics", "Appearance / QoL", "Audit"],
        )

    def test_voice_and_appearance_option_values_match_ui_controls(self):
        voice = voice_option_values()
        appearance = appearance_option_values()

        self.assertEqual(voice["tts_engines"], ["Piper Neural", "Windows SAPI"])
        self.assertEqual(voice["wake_sensitivity"], ["Low", "Normal", "High"])
        self.assertIn("jarvis", appearance["ui_styles"])
        self.assertEqual(appearance["mascot_opacity"], ["75", "85", "94", "100"])


if __name__ == "__main__":
    unittest.main()
