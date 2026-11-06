import unittest
from dataclasses import dataclass

from jarvis_assistant.ai import ConnectionStatus
from jarvis_assistant.app_status import (
    connected_ollama_status_view,
    cloud_status_text,
    model_profile_summary,
    normalize_connection_status,
    offline_ollama_status_view,
)


@dataclass(frozen=True)
class Settings:
    free_only_mode: bool = True
    enable_cloud_provider: bool = False
    model: str = "llama3:latest"
    cloud_model: str = "gpt-test"
    automation_risk_mode: str = "low_risk_auto"
    ollama_base_url: str = "http://127.0.0.1:11434"


class AppStatusTests(unittest.TestCase):
    def test_cloud_status_text_describes_free_only_mode(self):
        text = cloud_status_text(Settings(free_only_mode=True))

        self.assertIn("Free-only mode: on", text)
        self.assertIn("llama3:latest", text)

    def test_cloud_status_text_describes_hybrid_mode(self):
        text = cloud_status_text(Settings(free_only_mode=False, enable_cloud_provider=True))

        self.assertIn("Hybrid routing: cloud enabled", text)
        self.assertIn("cloud model gpt-test", text)

    def test_model_profile_summary_has_empty_fallback(self):
        self.assertEqual(model_profile_summary([]), "Installed Ollama models appear here after download.")

    def test_normalize_connection_status_accepts_bool_and_text(self):
        online = normalize_connection_status(True, "http://localhost:11434")
        offline = normalize_connection_status("nope", "http://localhost:11434")

        self.assertEqual(online, ConnectionStatus(True, "http://localhost:11434/api/tags", ""))
        self.assertEqual(offline, ConnectionStatus(False, "http://localhost:11434/api/tags", "nope"))

    def test_connected_ollama_status_view_describes_model_and_tools(self):
        view = connected_ollama_status_view(
            base_url="http://localhost:11434",
            model="llama3:latest",
            model_exists=True,
            tools_enabled=True,
            tools_supported=True,
        )

        self.assertIn("llama3:latest (found in ollama list)", view.message)
        self.assertEqual(view.banner_bg, "#17251d")
        self.assertEqual(view.summary, "llama3:latest connected")

    def test_offline_ollama_status_view_describes_probe(self):
        status = ConnectionStatus(False, "http://localhost:11434/api/tags", "connection refused")

        view = offline_ollama_status_view("http://localhost:11434", status)

        self.assertIn("connection refused", view.message)
        self.assertEqual(view.banner_bg, "#2a2020")
        self.assertEqual(view.status, "Ollama is offline. Chat responses are paused until local Ollama is reachable.")


if __name__ == "__main__":
    unittest.main()
