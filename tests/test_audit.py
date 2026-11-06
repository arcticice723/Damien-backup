import json
import tempfile
import unittest
from pathlib import Path

from jarvis_assistant.audit import AuditEvent, AuditLogger


class AuditLoggerTests(unittest.TestCase):
    def test_writes_jsonl_audit_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "logs" / "audit.jsonl"
            logger = AuditLogger(path)

            logger.log(AuditEvent(user_request="status", provider="ollama", tools_called=["system_status"], outcome="ok"))

            payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(payload["provider"], "ollama")
        self.assertEqual(payload["tools_called"], ["system_status"])
        self.assertIn("timestamp", payload)


if __name__ == "__main__":
    unittest.main()

