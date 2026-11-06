import unittest

from jarvis_assistant.app_debug_streaming import debug_streaming_scenarios


class AppDebugStreamingTests(unittest.TestCase):
    def test_debug_streaming_scenarios_cover_delta_and_full_partial_modes(self):
        labels = [label for label, _chunks in debug_streaming_scenarios()]

        self.assertEqual(labels, ["debug delta stream", "debug full partial stream"])


if __name__ == "__main__":
    unittest.main()
