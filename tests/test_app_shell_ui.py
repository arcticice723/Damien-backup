import unittest

from jarvis_assistant.app_shell_ui import shell_style_spacing


class AppShellUiTests(unittest.TestCase):
    def test_style_spacing_uses_compact_padding(self):
        self.assertEqual(
            shell_style_spacing(compact_mode=True),
            {"button_padding": (10, 5), "accent_padding": (12, 6), "tab_padding": (14, 7)},
        )

    def test_style_spacing_uses_comfortable_padding(self):
        self.assertEqual(
            shell_style_spacing(compact_mode=False),
            {"button_padding": (12, 7), "accent_padding": (14, 8), "tab_padding": (18, 10)},
        )


if __name__ == "__main__":
    unittest.main()
