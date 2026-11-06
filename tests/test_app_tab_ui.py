import unittest

from jarvis_assistant.app_tab_ui import benchmark_tab_buttons, memory_tab_buttons


class AppTabUiTests(unittest.TestCase):
    def test_memory_tab_buttons_keep_existing_labels(self):
        self.assertEqual(memory_tab_buttons(), ["Refresh", "Delete All Memory"])

    def test_benchmark_tab_buttons_keep_existing_labels(self):
        self.assertEqual(benchmark_tab_buttons(), ["Run Quick Benchmark"])


if __name__ == "__main__":
    unittest.main()
