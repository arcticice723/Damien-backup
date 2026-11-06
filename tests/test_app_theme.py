import unittest
from dataclasses import dataclass

from jarvis_assistant.app_theme import theme_colors


@dataclass(frozen=True)
class Settings:
    theme_mode: str = "light"
    accent_color: str = "cyan"
    custom_accent_color: str = ""
    ui_style: str = "hybrid"
    reduce_glow: bool = False


class AppThemeTests(unittest.TestCase):
    def test_light_theme_uses_work_surface_palette(self):
        colors = theme_colors(Settings(theme_mode="light"))

        self.assertEqual(colors["bg"], "#eef3f7")
        self.assertEqual(colors["panel"], "#ffffff")
        self.assertEqual(colors["accent"], "#48d1b2")

    def test_dark_theme_uses_requested_accent(self):
        colors = theme_colors(Settings(theme_mode="dark", accent_color="custom", custom_accent_color="#ffcc66"))

        self.assertEqual(colors["accent"], "#ffcc66")
        self.assertIn("panel", colors)


if __name__ == "__main__":
    unittest.main()
