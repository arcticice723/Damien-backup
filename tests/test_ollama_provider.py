import json
from io import BytesIO
import urllib.error
import unittest
from unittest.mock import MagicMock, patch

from jarvis_assistant.ai import ChatMessage, OllamaProvider
from jarvis_assistant.ai.ollama import is_model_load_error


class OllamaProviderTests(unittest.TestCase):
    def test_generate_posts_chat_payload(self):
        response = MagicMock()
        response.__enter__.return_value.__iter__.return_value = iter(
            [
                json.dumps({"message": {"content": "Hello."}, "done": False}).encode("utf-8"),
                json.dumps({"message": {}, "done": True, "eval_count": 1, "eval_duration": 1_000_000_000}).encode("utf-8"),
            ]
        )

        with patch("jarvis_assistant.ai.ollama.urllib.request.urlopen", return_value=response) as urlopen:
            provider = OllamaProvider("llama3:latest", "http://127.0.0.1:11434", 0.25, 4096)
            result = provider.generate([ChatMessage("user", "Hi")])

        self.assertEqual(result, "Hello.")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "llama3:latest")
        self.assertEqual(payload["messages"][0]["content"], "Hi")

    def test_is_reachable_returns_true_for_tags_endpoint(self):
        response = MagicMock()
        response.__enter__.return_value = response

        with patch("jarvis_assistant.ai.ollama.urllib.request.urlopen", return_value=response):
            provider = OllamaProvider("llama3:latest", "http://127.0.0.1:11434", 0.25, 4096)

            self.assertTrue(provider.is_reachable())

    def test_check_connection_includes_tags_url_and_success_detail(self):
        response = MagicMock()
        response.__enter__.return_value = response

        with patch("jarvis_assistant.ai.ollama.urllib.request.urlopen", return_value=response):
            provider = OllamaProvider("llama3:latest", "http://127.0.0.1:11434", 0.25, 4096)
            status = provider.check_connection()

        self.assertTrue(status.reachable)
        self.assertEqual(status.url, "http://127.0.0.1:11434/api/tags")
        self.assertIn("responded", status.detail)

    def test_is_reachable_returns_false_when_ollama_is_down(self):
        with patch("jarvis_assistant.ai.ollama.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            provider = OllamaProvider("llama3:latest", "http://127.0.0.1:11434", 0.25, 4096)

            self.assertFalse(provider.is_reachable())

    def test_check_connection_reports_error_detail_when_down(self):
        with patch("jarvis_assistant.ai.ollama.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            provider = OllamaProvider("llama3:latest", "http://127.0.0.1:11434", 0.25, 4096)
            status = provider.check_connection()

        self.assertFalse(status.reachable)
        self.assertEqual(status.url, "http://127.0.0.1:11434/api/tags")
        self.assertIn("down", status.detail)

    def test_model_supports_tools_reads_ollama_capabilities(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {
                "models": [
                    {"name": "llama3:latest", "model": "llama3:latest", "capabilities": ["completion"]},
                    {"name": "tool-model:latest", "model": "tool-model:latest", "capabilities": ["completion", "tools"]},
                ]
            }
        ).encode("utf-8")

        with patch("jarvis_assistant.ai.ollama.urllib.request.urlopen", return_value=response):
            provider = OllamaProvider("llama3:latest", "http://127.0.0.1:11434", 0.25, 4096)

            self.assertTrue(provider.model_exists())
            self.assertFalse(provider.model_supports_tools())

    def test_invalid_chat_payload_error_includes_response_body(self):
        error = urllib.error.HTTPError(
            url="http://127.0.0.1:11434/api/chat",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=BytesIO(b'{"error":"model does not support tools"}'),
        )

        with patch("jarvis_assistant.ai.ollama.urllib.request.urlopen", side_effect=error):
            provider = OllamaProvider("llama3:latest", "http://127.0.0.1:11434", 0.25, 4096)

            with self.assertRaises(RuntimeError) as raised:
                provider.generate([ChatMessage("user", "Hi")])

        message = str(raised.exception)
        self.assertIn("http://127.0.0.1:11434/api/chat", message)
        self.assertIn("llama3:latest", message)
        self.assertIn("model does not support tools", message)

    def test_model_load_error_detects_cuda_allocation_failure(self):
        body = "llama runner process has terminated: unable to allocate CUDA_Host buffer"

        self.assertTrue(is_model_load_error(body))


if __name__ == "__main__":
    unittest.main()
