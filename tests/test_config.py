import json
import tempfile
import unittest
from pathlib import Path

from jarvis_assistant.config import PROJECT_ROOT, load_settings, update_settings


class ConfigTests(unittest.TestCase):
    def test_update_settings_preserves_existing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(json.dumps({"model": "llama3:latest", "wake_phrase_enabled": False}), encoding="utf-8")

            update_settings({"wake_phrase_enabled": True}, path)

            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["model"], "llama3:latest")
        self.assertTrue(payload["wake_phrase_enabled"])

    def test_load_settings_reads_microphone_device(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps({"microphone_device_index": 12, "microphone_device_name": "Headset"}),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertEqual(settings.microphone_device_index, 12)
        self.assertEqual(settings.microphone_device_name, "Headset")

    def test_load_settings_creates_default_file_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config" / "settings.json"

            settings = load_settings(path)

            self.assertTrue(path.exists())
            self.assertEqual(settings.model, "llama3:latest")
            self.assertEqual(settings.microphone_device_name, "System default microphone")
            self.assertEqual(settings.output_device_name, "System default output")
            self.assertEqual(settings.tts_engine, "piper")
            self.assertEqual(settings.tts_voice_name, "auto")
            self.assertEqual(settings.piper_voice_name, "en_US-ryan-high")
            self.assertEqual(settings.tts_rate, 155)
            self.assertEqual(settings.tts_volume, 1.0)
            self.assertEqual(settings.theme_mode, "dark")
            self.assertEqual(settings.ui_style, "hybrid")
            self.assertEqual(settings.accent_color, "cyan")
            self.assertEqual(settings.custom_accent_color, "")
            self.assertEqual(settings.mascot_size, "normal")
            self.assertEqual(settings.mascot_opacity, 0.94)
            self.assertFalse(settings.compact_mode)
            self.assertFalse(settings.reduce_glow)
            self.assertTrue(settings.remote_control_enabled)
            self.assertEqual(settings.remote_control_host, "0.0.0.0")
            self.assertEqual(settings.remote_control_port, 8765)
            self.assertEqual(settings.remote_control_pin, "auto")
            self.assertFalse(settings.discord_bot_enabled)
            self.assertEqual(settings.discord_bot_token, "")
            self.assertEqual(settings.discord_bot_allowed_channel_ids, [])
            self.assertTrue(settings.start_minimized_to_tray)
            self.assertTrue(settings.mascot_widget_enabled)
            self.assertIsNone(settings.mascot_widget_x)
            self.assertIsNone(settings.mascot_widget_y)
            self.assertTrue(settings.screen_access_enabled)
            self.assertEqual(settings.screen_capture_dir, PROJECT_ROOT / "screenshots")
            self.assertEqual(settings.whisper_model, "small")
            self.assertEqual(settings.whisper_device, "cpu")
            self.assertEqual(settings.whisper_beam_size, 5)
            self.assertEqual(settings.wake_whisper_beam_size, 1)
            self.assertIn("hey damian", settings.wake_phrase_variants)
            self.assertEqual(settings.wake_sensitivity, 0.72)
            self.assertTrue(settings.wake_phrase_enabled)
            self.assertFalse(settings.wake_acknowledgement_sound_enabled)
            self.assertEqual(settings.wake_acknowledgement_mode, "voice")
            self.assertEqual(settings.wake_listening_cue, "yes?")
            self.assertEqual(settings.wake_thinking_cue, "hmmm...")
            self.assertEqual(settings.crunchyroll_profile_name, "")
            self.assertTrue(settings.crunchyroll_browser_automation_enabled)
            self.assertEqual(settings.crunchyroll_browser_port, 9223)
            self.assertTrue(settings.proactive_enabled)
            self.assertTrue(settings.proactive_voice_enabled)
            self.assertEqual(settings.reminder_check_seconds, 30)
            self.assertFalse(settings.remote_brain_enabled)
            self.assertEqual(settings.remote_brain_base_url, "")

    def test_load_settings_reads_wake_variants_and_sensitivity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps({"wake_phrase_variants": ["hey computer"], "wake_sensitivity": 0.88}),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertIn("hey computer", settings.wake_phrase_variants)
        self.assertIn("hey daemon", settings.wake_phrase_variants)
        self.assertEqual(settings.wake_sensitivity, 0.88)

    def test_load_settings_reads_appearance_qol_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "ui_style": "jarvis",
                        "accent_color": "custom",
                        "custom_accent_color": "#ffcc66",
                        "mascot_size": "large",
                        "mascot_opacity": 0.82,
                        "compact_mode": True,
                        "reduce_glow": True,
                    }
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertEqual(settings.ui_style, "jarvis")
        self.assertEqual(settings.accent_color, "custom")
        self.assertEqual(settings.custom_accent_color, "#ffcc66")
        self.assertEqual(settings.mascot_size, "large")
        self.assertEqual(settings.mascot_opacity, 0.82)
        self.assertTrue(settings.compact_mode)
        self.assertTrue(settings.reduce_glow)

    def test_load_settings_reads_screen_access_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps({"screen_access_enabled": False, "screen_capture_dir": "captures"}),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertFalse(settings.screen_access_enabled)
        self.assertEqual(settings.screen_capture_dir, PROJECT_ROOT / "captures")

    def test_load_settings_reads_wake_cue_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "wake_acknowledgement_sound_enabled": True,
                        "wake_acknowledgement_mode": "silent",
                        "wake_listening_cue": "mhm?",
                        "wake_thinking_cue": "hmmm.",
                    }
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertTrue(settings.wake_acknowledgement_sound_enabled)
        self.assertEqual(settings.wake_acknowledgement_mode, "silent")
        self.assertEqual(settings.wake_listening_cue, "mhm?")
        self.assertEqual(settings.wake_thinking_cue, "hmmm.")

    def test_load_settings_reads_discord_bot_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "discord_bot_enabled": True,
                        "discord_bot_token": "abc",
                        "discord_bot_allowed_channel_ids": ["123", 456],
                    }
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertTrue(settings.discord_bot_enabled)
        self.assertEqual(settings.discord_bot_token, "abc")
        self.assertEqual(settings.discord_bot_allowed_channel_ids, [123, 456])

    def test_load_settings_reads_remote_brain_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "remote_brain_enabled": True,
                        "remote_brain_base_url": "http://192.168.1.50:11434/",
                    }
                ),
                encoding="utf-8",
            )

            settings = load_settings(path)

        self.assertTrue(settings.remote_brain_enabled)
        self.assertEqual(settings.remote_brain_base_url, "http://192.168.1.50:11434")


if __name__ == "__main__":
    unittest.main()
