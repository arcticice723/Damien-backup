import unittest

from jarvis_assistant.app_ollama_control import (
    fallback_switch_result,
    ollama_check_message,
    selected_model_settings_update,
    startup_detail_from_stderr,
    status_with_startup_detail,
)
from jarvis_assistant.ai import ConnectionStatus


class AppOllamaControlTests(unittest.TestCase):
    def test_startup_detail_from_stderr_treats_bind_errors_as_running_probe(self):
        detail = startup_detail_from_stderr("listen tcp 127.0.0.1:11434: bind: Only one usage of each socket address")

        self.assertIn("port is already in use", detail)
        self.assertIn("likely already running", detail)

    def test_startup_detail_from_stderr_reports_other_fast_exits(self):
        self.assertEqual(startup_detail_from_stderr("boom"), "ollama serve exited: boom")
        self.assertEqual(startup_detail_from_stderr("  "), "")

    def test_status_with_startup_detail_appends_detail_only_when_offline(self):
        offline = status_with_startup_detail(ConnectionStatus(False, "http://local/api/tags", "down"), "not found")
        online = status_with_startup_detail(ConnectionStatus(True, "http://local/api/tags", "ok"), "ignored")

        self.assertEqual(offline.detail, "down Startup detail: not found")
        self.assertEqual(online.detail, "ok")

    def test_fallback_switch_result_describes_selected_lightweight_model(self):
        result = fallback_switch_result("llama3:latest", ["llama3:latest", "llama3.2:3b"], "out of memory")

        self.assertTrue(result.available)
        self.assertEqual(result.next_model, "llama3.2:3b")
        self.assertIn("model_fallback_selected", result.log_message)
        self.assertEqual(result.summary, "llama3.2:3b fallback")

    def test_fallback_switch_result_reports_unavailable_model(self):
        result = fallback_switch_result("deepseek-coder:latest", ["deepseek-coder:latest"], "out of memory")

        self.assertFalse(result.available)
        self.assertIsNone(result.next_model)
        self.assertIn("model_fallback_unavailable", result.log_message)
        self.assertIsNone(result.summary)

    def test_selected_model_settings_update_trims_model_and_defaults_thinking_mode(self):
        self.assertEqual(
            selected_model_settings_update(" llama3.2:latest ", " ", False, " "),
            {
                "model": "llama3.2:latest",
                "thinking_mode": "auto",
                "remote_brain_enabled": False,
                "remote_brain_base_url": "",
            },
        )

    def test_selected_model_settings_update_saves_remote_brain_endpoint(self):
        self.assertEqual(
            selected_model_settings_update("llama3.2:latest", "on", True, " http://192.168.1.50:11434/ "),
            {
                "model": "llama3.2:latest",
                "thinking_mode": "on",
                "remote_brain_enabled": True,
                "remote_brain_base_url": "http://192.168.1.50:11434",
            },
        )

    def test_ollama_check_message_matches_status_banner_text(self):
        self.assertEqual(ollama_check_message(), "Checking local Ollama connection...")


if __name__ == "__main__":
    unittest.main()
