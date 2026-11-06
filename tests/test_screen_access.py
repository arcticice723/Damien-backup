import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from jarvis_assistant.screen_access import ScreenReader


class ScreenAccessTests(unittest.TestCase):
    def test_capture_screen_saves_png_with_dimensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = Image.new("RGB", (32, 18), "navy")
            reader = ScreenReader(root, capture=lambda: image)

            result = reader.capture_screen()

            self.assertTrue(result.path.exists())
            self.assertEqual(result.width, 32)
            self.assertEqual(result.height, 18)
            self.assertEqual(result.path.parent.name, "screenshots")

    def test_read_screen_reports_saved_capture(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = Image.new("RGB", (20, 10), "white")
            reader = ScreenReader(root, capture=lambda: image)

            message = reader.read_screen()

        self.assertIn("captured your screen", message)
        self.assertIn("20x10", message)
        self.assertIn("Visual description and OCR", message)

    def test_understand_screen_logs_upgrade_when_ocr_backend_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = Image.new("RGB", (20, 10), "white")
            reader = ScreenReader(root, capture=lambda: image, ocr=lambda _path: "")

            message = reader.understand_screen("what is on my screen")
            queue_path = root / "logs" / "improvement_queue.jsonl"

            self.assertIn("captured your screen", message)
            self.assertIn("OCR or vision backend", message)
            self.assertTrue(queue_path.exists())

    def test_read_screen_respects_disabled_setting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "config").mkdir()
            (root / "config" / "settings.json").write_text(
                json.dumps({"screen_access_enabled": False}),
                encoding="utf-8",
            )
            reader = ScreenReader(root, capture=lambda: Image.new("RGB", (1, 1), "black"))

            message = reader.read_screen()

            self.assertIn("disabled", message)
            self.assertFalse(reader.screen_access_enabled())
            self.assertFalse((root / "screenshots").exists())
