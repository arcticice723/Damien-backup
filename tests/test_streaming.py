import unittest

from jarvis_assistant.app_helpers import pop_ready_speech_segments, stream_chunk_mode, update_stream_response


class StreamingTests(unittest.TestCase):
    def test_delta_chunks_append_to_one_response(self):
        text = ""
        for chunk in ["Another", " test", "! I'm ready."]:
            text = update_stream_response(text, chunk)

        self.assertEqual(text, "Another test! I'm ready.")
        self.assertNotIn("Another\nAnother test", text)

    def test_full_partial_chunks_replace_current_response(self):
        text = ""
        for chunk in ["Another", "Another test", "Another test! I'm ready."]:
            text = update_stream_response(text, chunk)

        self.assertEqual(text, "Another test! I'm ready.")
        self.assertNotIn("AnotherAnother", text)

    def test_stream_chunk_mode_identifies_delta_and_full_partial(self):
        self.assertEqual(stream_chunk_mode("Another", " test"), "delta")
        self.assertEqual(stream_chunk_mode("Another", "Another test"), "full_partial")

    def test_streaming_speech_waits_for_complete_sentences(self):
        segments, remainder = pop_ready_speech_segments("Systems are online. Running checks")
        self.assertEqual(segments, ["Systems are online."])
        self.assertEqual(remainder, " Running checks")

        segments, remainder = pop_ready_speech_segments(remainder, force=True)
        self.assertEqual(segments, ["Running checks"])
        self.assertEqual(remainder, "")

    def test_streaming_speech_does_not_split_numbered_list_markers(self):
        segments, remainder = pop_ready_speech_segments("1. **Windows basics**: I can help. 2. Discord")

        self.assertEqual(segments, ["1. **Windows basics**: I can help."])
        self.assertEqual(remainder, " 2. Discord")


if __name__ == "__main__":
    unittest.main()
