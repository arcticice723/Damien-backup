import unittest

from jarvis_assistant.app_appearance_control import theme_mode_update


class AppAppearanceControlTests(unittest.TestCase):
    def test_theme_mode_update_maps_boolean_choice_to_setting(self):
        self.assertEqual(theme_mode_update(True), {"theme_mode": "dark"})
        self.assertEqual(theme_mode_update(False), {"theme_mode": "light"})


if __name__ == "__main__":
    unittest.main()
