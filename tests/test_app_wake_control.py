import unittest

from jarvis_assistant.app_wake_control import wake_phrase_settings_update


class AppWakeControlTests(unittest.TestCase):
    def test_wake_phrase_settings_update_maps_toggle_state(self):
        self.assertEqual(wake_phrase_settings_update(True), {"wake_phrase_enabled": True})
        self.assertEqual(wake_phrase_settings_update(False), {"wake_phrase_enabled": False})


if __name__ == "__main__":
    unittest.main()
