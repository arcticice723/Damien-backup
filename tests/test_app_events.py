import queue
import unittest

from jarvis_assistant.app_events import DamienEventDispatcher


class FakeApp:
    def __init__(self) -> None:
        self.events = queue.Queue()
        self.current_response = ""
        self.current_response_speak = True
        self.debug_assistant_block_count = 2
        self.stream_logs: list[str] = []
        self.replaced_lines: list[str] = []
        self.queued_speech: list[str] = []

    def _log_stream_debug(self, message: str) -> None:
        self.stream_logs.append(message)

    def _replace_last_assistant_line(self, text: str) -> None:
        self.replaced_lines.append(text)

    def _queue_streaming_speech(self, text: str) -> None:
        self.queued_speech.append(text)


class AppEventsTests(unittest.TestCase):
    def test_dispatcher_drains_empty_queue_without_calling_app(self):
        app = FakeApp()

        DamienEventDispatcher(app).poll_once()

        self.assertEqual(app.current_response, "")
        self.assertEqual(app.replaced_lines, [])

    def test_dispatcher_appends_stream_text_and_queues_only_new_speech(self):
        app = FakeApp()
        app.current_response = "Hello"
        app.events.put(("stream_text", ", boss."))

        DamienEventDispatcher(app).poll_once()

        self.assertEqual(app.current_response, "Hello, boss.")
        self.assertEqual(app.replaced_lines, ["Hello, boss."])
        self.assertEqual(app.queued_speech, [", boss."])
        self.assertIn("stream_text_event", app.stream_logs[0])


if __name__ == "__main__":
    unittest.main()
