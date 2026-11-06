import unittest

from jarvis_assistant.interpretation import UtteranceInterpreter


class UtteranceInterpreterTests(unittest.TestCase):
    def test_corrects_common_stt_app_phrases(self):
        interpreter = UtteranceInterpreter()

        self.assertEqual(interpreter.interpret("lunch crunchy roll").corrected, "launch crunchyroll")
        self.assertEqual(interpreter.interpret("Open APEG's Legends.").corrected, "Open apex legends.")
        self.assertEqual(interpreter.interpret("open the i tunes app").corrected, "open the itunes app")

    def test_corrects_common_questions(self):
        interpreter = UtteranceInterpreter()

        self.assertEqual(interpreter.interpret("what dime is it").corrected, "what time is it")
        self.assertEqual(interpreter.interpret("what aps can you open").corrected, "what apps can you open")

    def test_strips_wake_and_polite_prefixes(self):
        interpreter = UtteranceInterpreter()

        self.assertEqual(interpreter.interpret("hey Damien play One Piece").corrected, "play One Piece")
        self.assertEqual(interpreter.interpret("Damien, can you shuffle workout playlist").corrected, "shuffle workout playlist")


if __name__ == "__main__":
    unittest.main()
