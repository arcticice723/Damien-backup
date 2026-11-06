import unittest

from jarvis_assistant.app_utility_actions import benchmark_prompt


class AppUtilityActionsTests(unittest.TestCase):
    def test_benchmark_prompt_keeps_privacy_smoke_test_request(self):
        self.assertEqual(
            benchmark_prompt(),
            "Give one concise sentence explaining why local AI privacy matters.",
        )


if __name__ == "__main__":
    unittest.main()
