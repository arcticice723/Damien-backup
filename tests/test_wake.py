import unittest

from jarvis_assistant.wake import WakePhraseDetector


class WakePhraseTests(unittest.TestCase):
    def test_normalize_matches_hey_damien(self):
        self.assertEqual(WakePhraseDetector._normalize("Hey, Damien!"), "hey damien")

    def test_matches_common_wake_variants(self):
        detector = WakePhraseDetector(
            wake_phrase="hey damien",
            wake_phrase_variants=["hey damian", "damien", "hey daemon"],
            wake_sensitivity=0.72,
            on_detected=lambda: None,
            on_status=lambda _text: None,
            check_seconds=1.0,
            model_name="tiny",
            device="cpu",
            compute_type="int8",
        )

        for text in ["hey damien", "hey damian", "hey daemon"]:
            matched, _phrase = detector.matches(text)
            self.assertTrue(matched, text)

    def test_single_assistant_name_does_not_wake_from_video_audio(self):
        detector = WakePhraseDetector(
            wake_phrase="hey damien",
            wake_phrase_variants=["hey damian", "damien", "hey daemon"],
            wake_sensitivity=0.72,
            on_detected=lambda: None,
            on_status=lambda _text: None,
            check_seconds=1.0,
            model_name="tiny",
            device="cpu",
            compute_type="int8",
        )

        for text in ["damien", "Group of Damien's.", "I can listen for Damien."]:
            matched, _phrase = detector.matches(text)
            self.assertFalse(matched, text)

    def test_sensitivity_allows_close_match(self):
        detector = WakePhraseDetector(
            wake_phrase="hey damien",
            wake_phrase_variants=[],
            wake_sensitivity=0.88,
            on_detected=lambda: None,
            on_status=lambda _text: None,
            check_seconds=1.0,
            model_name="tiny",
            device="cpu",
            compute_type="int8",
        )

        matched, phrase = detector.matches("hey damon")

        self.assertTrue(matched)
        self.assertEqual(phrase, "hey damien")

    def test_command_gate_rejects_overlapping_wake_commands(self):
        gate = WakePhraseDetector.CommandGate()

        self.assertTrue(gate.try_begin())
        self.assertFalse(gate.try_begin())

        gate.finish()
        self.assertTrue(gate.try_begin())


if __name__ == "__main__":
    unittest.main()
