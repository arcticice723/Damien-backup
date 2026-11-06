import unittest

from jarvis_assistant.local_models import DEFAULT_OLLAMA_MODEL, fallback_model, recommended_model_order


class LocalModelProfileTests(unittest.TestCase):
    def test_default_model_is_general_latest(self):
        self.assertEqual(DEFAULT_OLLAMA_MODEL, "llama3:latest")

    def test_recommended_model_order_prioritizes_damien_profiles(self):
        installed = ["random:latest", "deepseek-coder:latest", "qwen3:4b", "llama3:latest", "llama3.2:3b"]

        ordered = recommended_model_order(installed)

        self.assertEqual(ordered[:4], ["llama3:latest", "qwen3:4b", "llama3.2:3b", "deepseek-coder:latest"])
        self.assertIn("random:latest", ordered)

    def test_fallback_model_skips_current_and_uses_lightweight_order(self):
        installed = ["llama3:latest", "qwen3:4b", "llama3.2:3b", "deepseek-coder:latest"]

        self.assertEqual(fallback_model("llama3:latest", installed), "llama3.2:3b")
        self.assertEqual(fallback_model("llama3.2:3b", installed), "qwen3:4b")
        self.assertIsNone(fallback_model("deepseek-coder:latest", ["deepseek-coder:latest"]))


if __name__ == "__main__":
    unittest.main()
