import unittest
from unittest.mock import MagicMock, patch

from jarvis_assistant.single_instance import ERROR_ALREADY_EXISTS, SingleInstance


class SingleInstanceTests(unittest.TestCase):
    def test_non_windows_acquires_without_mutex(self):
        with patch("jarvis_assistant.single_instance.sys.platform", "linux"):
            instance = SingleInstance()

            self.assertTrue(instance.acquire())

    def test_windows_existing_instance_returns_false(self):
        kernel32 = MagicMock()
        kernel32.CreateMutexW.return_value = 123
        kernel32.GetLastError.return_value = ERROR_ALREADY_EXISTS
        windll = MagicMock(kernel32=kernel32)

        with patch("jarvis_assistant.single_instance.sys.platform", "win32"):
            with patch("jarvis_assistant.single_instance.ctypes.windll", windll, create=True):
                with patch("jarvis_assistant.single_instance.focus_existing_window", return_value=True):
                    instance = SingleInstance()

                    self.assertFalse(instance.acquire())


if __name__ == "__main__":
    unittest.main()

