import unittest

from jarvis_assistant.speech_controller import SpeechController


class FakeTts:
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.stopped = False

    def speak(self, text: str, should_stop=None, timeout_seconds=None) -> None:
        self.spoken.append(text)

    def stop(self) -> None:
        self.stopped = True


class SpeechControllerTests(unittest.TestCase):
    def test_queues_complete_segments_and_flushes_remainder(self):
        fake = FakeTts()
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda _reason: None,
            start_thread=lambda target: None,
        )

        controller.start_streaming()
        controller.queue_streaming_text("Systems online. Running checks")
        controller.finish_streaming()

        self.assertEqual(list(controller.drain_pending_segments()), ["Systems online.", "Running checks"])

    def test_stop_interrupts_existing_tts(self):
        fake = FakeTts()
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda _reason: None,
            start_thread=lambda target: None,
        )
        controller.tts = fake

        controller.stop()

        self.assertTrue(fake.stopped)

    def test_stop_clears_queued_streaming_segments(self):
        fake = FakeTts()
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda _reason: None,
            start_thread=lambda target: None,
        )

        controller.start_streaming()
        controller.queue_streaming_text("First item. Second item.")
        controller.stop()

        self.assertEqual(list(controller.drain_pending_segments()), [])

    def test_stop_ignores_late_streaming_text_until_restarted(self):
        fake = FakeTts()
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda _reason: None,
            start_thread=lambda target: None,
        )

        controller.start_streaming()
        controller.stop()
        controller.queue_streaming_text("This should not play.")

        self.assertEqual(list(controller.drain_pending_segments()), [])

    def test_speak_clears_stale_streaming_segments_before_new_response(self):
        fake = FakeTts()
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda _reason: None,
            start_thread=lambda target: None,
        )

        controller.start_streaming()
        controller.queue_streaming_text("Old readout. Still old.")
        controller.speak("Fresh answer.")

        self.assertEqual(list(controller.drain_pending_segments()), [])

    def test_speak_interrupts_active_tts_before_new_response(self):
        fake = FakeTts()
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda _reason: None,
            start_thread=lambda target: target(),
        )
        controller.tts = fake

        controller.speak("Fresh answer.")

        self.assertTrue(fake.stopped)
        self.assertEqual(fake.spoken, ["Fresh answer."])

    def test_start_streaming_interrupts_active_tts_before_streamed_response(self):
        fake = FakeTts()
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda _reason: None,
            start_thread=lambda target: None,
        )
        controller.tts = fake

        controller.start_streaming()

        self.assertTrue(fake.stopped)

    def test_start_streaming_pauses_wake_before_tts_can_speak(self):
        fake = FakeTts()
        wake_events: list[str] = []
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda reason: wake_events.append(f"resume:{reason}"),
            pause_wake=lambda reason: wake_events.append(f"pause:{reason}"),
            start_thread=lambda target: None,
        )

        controller.start_streaming()

        self.assertEqual(wake_events, ["pause:tts stream started"])

    def test_speak_pauses_wake_before_tts_can_speak(self):
        fake = FakeTts()
        wake_events: list[str] = []
        controller = SpeechController(
            tts_factory=lambda: fake,
            emit=lambda _kind, _payload: None,
            log=lambda _message: None,
            resume_wake=lambda reason: wake_events.append(f"resume:{reason}"),
            pause_wake=lambda reason: wake_events.append(f"pause:{reason}"),
            start_thread=lambda target: target(),
        )

        controller.speak("Fresh answer.")

        self.assertEqual(wake_events, ["pause:tts started", "resume:tts finished"])


if __name__ == "__main__":
    unittest.main()
