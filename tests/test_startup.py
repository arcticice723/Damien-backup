import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.startup import startup_command


class StartupTests(unittest.TestCase):
    def test_startup_command_points_to_main_py(self):
        with patch("jarvis_assistant.startup.sys.executable", r"C:\Project\.venv\Scripts\python.exe"):
            command = startup_command(Path(r"C:\Project"))

        self.assertIn("main.py", command)
        self.assertIn(r"C:\Project", command)

    def test_startup_command_uses_packaged_exe_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            exe = root / "Damien.exe"
            exe.write_text("", encoding="utf-8")

            command = startup_command(root)

        self.assertEqual(command, f'"{exe}"')


if __name__ == "__main__":
    unittest.main()
