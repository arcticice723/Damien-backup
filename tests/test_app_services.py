import unittest
from types import SimpleNamespace

from jarvis_assistant.app_services import (
    app_service_role_names,
    build_local_ollama_provider,
    ollama_runtime_base_url,
    voice_readiness_status,
)


class Value:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


class AppServicesTests(unittest.TestCase):
    def test_service_role_names_describe_runtime_bundle_order(self):
        self.assertEqual(
            app_service_role_names(),
            [
                "history",
                "commands",
                "local_ai",
                "cloud_ai",
                "retrieval",
                "memory",
                "audit",
                "improvement_queue",
                "tools",
                "orchestrator",
                "recorder",
                "events",
            ],
        )

    def test_build_local_ollama_provider_uses_settings_runtime_options(self):
        settings = SimpleNamespace(
            ollama_base_url="http://127.0.0.1:11434",
            remote_brain_enabled=False,
            remote_brain_base_url="",
            temperature=0.2,
            num_ctx=8192,
            thinking_mode="off",
        )

        provider = build_local_ollama_provider(settings, "llama3.2:latest")

        self.assertEqual(provider.model, "llama3.2:latest")
        self.assertEqual(provider.base_url, "http://127.0.0.1:11434")
        self.assertEqual(provider.temperature, 0.2)
        self.assertEqual(provider.num_ctx, 8192)
        self.assertEqual(provider.thinking_mode, "off")

    def test_ollama_runtime_base_url_uses_remote_brain_only_when_enabled(self):
        settings = SimpleNamespace(
            ollama_base_url="http://127.0.0.1:11434",
            remote_brain_enabled=True,
            remote_brain_base_url="http://192.168.1.50:11434/",
        )

        self.assertEqual(ollama_runtime_base_url(settings), "http://192.168.1.50:11434")

    def test_ollama_runtime_base_url_stays_local_when_remote_brain_url_is_blank(self):
        settings = SimpleNamespace(
            ollama_base_url="http://127.0.0.1:11434",
            remote_brain_enabled=True,
            remote_brain_base_url="",
        )

        self.assertEqual(ollama_runtime_base_url(settings), "http://127.0.0.1:11434")

    def test_voice_readiness_status_summarizes_live_app_voice_state(self):
        app = SimpleNamespace(
            mic_status=Value("Microphone: available - USB Microphone"),
            wake_summary=Value("Listening for wake phrase"),
            voice_summary=Value("Windows SAPI ready - Headphones"),
        )

        self.assertEqual(
            voice_readiness_status(app),
            "Voice status: Microphone: available - USB Microphone; Listening for wake phrase; Windows SAPI ready - Headphones.",
        )

    def test_voice_readiness_status_includes_active_companion_checks(self):
        app = SimpleNamespace(
            mic_status=Value("Microphone: available - USB Microphone"),
            wake_summary=Value("Listening for wake phrase"),
            voice_summary=Value("Windows SAPI ready - Headphones"),
            proactive_summary=Value("Active companion checks on"),
        )

        self.assertEqual(
            voice_readiness_status(app),
            "Voice status: Microphone: available - USB Microphone; Listening for wake phrase; "
            "Windows SAPI ready - Headphones; Active companion checks on.",
        )


if __name__ == "__main__":
    unittest.main()
