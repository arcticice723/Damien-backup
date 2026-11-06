import unittest
from types import SimpleNamespace

from jarvis_assistant.app_settings_ui import (
    audit_status_text,
    automation_panel_items,
    automation_status_defaults,
    appearance_panel_fields,
    diagnostics_panel_buttons,
    diagnostics_status_defaults,
    local_ai_panel_fields,
    local_model_choices,
    settings_section_layout,
    voice_panel_fields,
    voice_status_defaults,
)


class AppSettingsUiTests(unittest.TestCase):
    def test_voice_panel_fields_keep_existing_row_order(self):
        self.assertEqual(
            voice_panel_fields(),
            [
                "Microphone",
                "Voice output",
                "Voice engine",
                "Piper voice",
                "Windows voice",
                "Voice speed",
                "Voice volume",
                "Wake sensitivity",
            ],
        )

    def test_voice_status_defaults_match_settings_tab_startup_text(self):
        self.assertEqual(
            voice_status_defaults(),
            {
                "mic_status": "Microphone: checking...",
                "wake_dependency_status": "Wake phrase: checking...",
                "tts_status": "Voice: checking...",
            },
        )

    def test_automation_panel_items_keep_existing_order(self):
        self.assertEqual(
            automation_panel_items(),
            [
                "Start in background tray mode",
                "Show desktop mascot widget",
                'Enable wake phrase "Hey Damien"',
                "Active companion checks",
                "Speak proactive notices aloud",
                "Launch Damien at Windows sign-in",
                "Dark mode",
            ],
        )

    def test_automation_status_defaults_match_settings_tab_startup_text(self):
        self.assertEqual(automation_status_defaults(), {"remote_status": "Remote: starting..."})

    def test_diagnostics_panel_buttons_keep_existing_order(self):
        self.assertEqual(
            diagnostics_panel_buttons(),
            ["Test Microphone", "Test Voice", "Calibrate Wake Phrase", "Voice Diagnostics"],
        )

    def test_diagnostics_status_defaults_match_settings_tab_startup_text(self):
        self.assertEqual(diagnostics_status_defaults(), {"wake_status": "Disabled"})

    def test_appearance_panel_fields_keep_existing_order(self):
        self.assertEqual(
            appearance_panel_fields(),
            ["UI style", "Accent color", "Custom accent", "Mascot size", "Mascot opacity", "Compact mode", "Reduce glow"],
        )

    def test_audit_status_text_matches_settings_tab_startup_text(self):
        settings = SimpleNamespace(audit_log_path="logs/audit.log")
        self.assertEqual(audit_status_text(settings), "Audit log: logs/audit.log")

    def test_local_model_choices_include_saved_model_first(self):
        settings = SimpleNamespace(model="llama3.2:latest")
        self.assertEqual(local_model_choices(settings, ["phi3:mini"]), ["llama3.2:latest", "phi3:mini"])

    def test_local_ai_panel_fields_include_remote_brain_controls(self):
        self.assertEqual(
            local_ai_panel_fields(),
            ["Ollama model", "Thinking mode", "Remote brain", "Brain server URL"],
        )

    def test_settings_section_layout_keeps_panel_order_and_grid(self):
        self.assertEqual(
            settings_section_layout(),
            [
                ("Local AI", 0, 0, {"padx": (0, 10), "pady": (0, 10)}),
                ("Voice", 0, 1, {"padx": (10, 0), "pady": (0, 10)}),
                ("Automation", 1, 0, {"padx": (0, 10), "pady": (10, 10)}),
                ("Diagnostics", 1, 1, {"padx": (10, 0), "pady": (10, 10)}),
                ("Appearance / QoL", 2, 0, {"columnspan": 2, "pady": (10, 10)}),
                ("Audit", 3, 0, {"columnspan": 2, "pady": (10, 0)}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
