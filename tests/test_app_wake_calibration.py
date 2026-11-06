import unittest

from jarvis_assistant.app_wake_calibration import calibration_header_lines, updated_wake_variants


class AppWakeCalibrationTests(unittest.TestCase):
    def test_calibration_header_uses_default_microphone_name_when_blank(self):
        self.assertEqual(
            calibration_header_lines(""),
            ["Wake calibration:", "Microphone: System default microphone"],
        )

    def test_updated_wake_variants_adds_new_matched_normalized_phrase_once(self):
        variants = updated_wake_variants(["hey damien"], matched=True, normalized="hey daemon")

        self.assertEqual(variants, ["hey damien", "hey daemon"])
        self.assertEqual(updated_wake_variants(variants, matched=True, normalized="hey daemon"), variants)

    def test_updated_wake_variants_ignores_unmatched_or_empty_phrase(self):
        self.assertEqual(updated_wake_variants(["hey damien"], matched=False, normalized="hey daemon"), ["hey damien"])
        self.assertEqual(updated_wake_variants(["hey damien"], matched=True, normalized=""), ["hey damien"])


if __name__ == "__main__":
    unittest.main()
