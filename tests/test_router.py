import os
import unittest
from unittest.mock import patch

from jarvis_assistant.config import load_settings
from jarvis_assistant.router import ProviderRouter


class ProviderRouterTests(unittest.TestCase):
    def test_cloud_disabled_routes_local(self):
        router = ProviderRouter(load_settings())

        decision = router.route("research a complex plan")

        self.assertEqual(decision.provider, "ollama")
        self.assertFalse(decision.cloud_data_sent)

    def test_cloud_enabled_without_key_routes_local(self):
        settings = load_settings()
        object.__setattr__(settings, "free_only_mode", False)
        object.__setattr__(settings, "enable_cloud_provider", True)

        with patch.dict(os.environ, {}, clear=True):
            decision = ProviderRouter(settings).route("research a complex plan")

        self.assertEqual(decision.provider, "ollama")
        self.assertIn("OPENAI_API_KEY", decision.reason)

    def test_cloud_enabled_with_key_routes_complex_request_to_cloud(self):
        settings = load_settings()
        object.__setattr__(settings, "free_only_mode", False)
        object.__setattr__(settings, "enable_cloud_provider", True)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "present"}, clear=True):
            decision = ProviderRouter(settings).route("research and compare options")

        self.assertEqual(decision.provider, "openai")
        self.assertTrue(decision.cloud_data_sent)

    def test_free_only_mode_blocks_cloud_even_with_key(self):
        settings = load_settings()
        object.__setattr__(settings, "free_only_mode", True)
        object.__setattr__(settings, "enable_cloud_provider", True)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "present"}, clear=True):
            decision = ProviderRouter(settings).route("research and compare options")

        self.assertEqual(decision.provider, "ollama")
        self.assertFalse(decision.cloud_data_sent)
        self.assertIn("Free-only mode", decision.reason)


if __name__ == "__main__":
    unittest.main()
