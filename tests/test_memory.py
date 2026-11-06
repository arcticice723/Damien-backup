import tempfile
import unittest
from pathlib import Path

from jarvis_assistant.memory import LongTermMemory


class LongTermMemoryTests(unittest.TestCase):
    def test_memory_is_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "memory.jsonl"
            memory = LongTermMemory(path, enabled=False)
            memory.add("remember this")

            self.assertFalse(path.exists())

    def test_delete_all_removes_inspectable_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "memory.jsonl"
            memory = LongTermMemory(path, enabled=True)
            memory.add("remember this")
            memory.delete_all()

            self.assertEqual(memory.list_memories(), [])

    def test_memory_records_categories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "memory.jsonl"
            memory = LongTermMemory(path, enabled=True)

            memory.add_preference("Use concise replies")
            memory.add_episode_summary("We built a package")

            self.assertEqual(memory.list_memories("preference")[0]["content"], "Use concise replies")
            self.assertEqual(memory.list_memories("episode")[0]["content"], "We built a package")


if __name__ == "__main__":
    unittest.main()
