import tempfile
import unittest
from pathlib import Path

from jarvis_assistant.agent.notes import NoteIntentHandler, NoteStore
from jarvis_assistant.ai import ChatMessage

from tests.test_agent_runtime import build_runtime


class AgentNotesTests(unittest.TestCase):
    def test_note_store_add_list_and_search(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = NoteStore(Path(temp_dir) / "notes.jsonl")

            store.add("call the dentist")
            store.add("buy milk")

            self.assertEqual([note.content for note in store.list_recent()], ["call the dentist", "buy milk"])
            self.assertEqual([note.content for note in store.search("dentist")], ["call the dentist"])

    def test_note_intent_handler_saves_and_recalls_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = NoteIntentHandler(NoteStore(Path(temp_dir) / "notes.jsonl"))

            saved = handler.handle("remember that the spare key is in the desk drawer")
            recalled = handler.handle("what do you remember about spare key")

        self.assertIn("Saved note", saved)
        self.assertIn("I remember", recalled)
        self.assertIn("desk drawer", recalled)

    def test_note_intent_handler_saves_make_a_note_phrasing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = NoteIntentHandler(NoteStore(Path(temp_dir) / "notes.jsonl"))

            saved = handler.handle("make a note that the gate code is 4242")
            recalled = handler.handle("what do you remember about gate code")

        self.assertIn("Saved note", saved)
        self.assertIn("4242", recalled)

    def test_note_intent_handler_saves_direct_save_object_phrasing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            handler = NoteIntentHandler(NoteStore(Path(temp_dir) / "notes.jsonl"))

            saved = handler.handle("Save the creating rain cloud.")
            recalled = handler.handle("what do you remember about rain cloud")

        self.assertEqual(saved, "Saved note: creating rain cloud")
        self.assertIn("- creating rain cloud", recalled)

    def test_agent_runtime_handles_natural_note_commands(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            save = runtime.prepare(
                "remember as a note that the blue cable is for the monitor",
                [ChatMessage("user", "remember as a note that the blue cable is for the monitor")],
            )
            listed = runtime.prepare("show my notes", [ChatMessage("user", "show my notes")])
            searched = runtime.prepare("search notes for blue", [ChatMessage("user", "search notes for blue")])

        self.assertIn("Saved note", save.direct_response)
        self.assertIn("blue cable", listed.direct_response)
        self.assertIn("blue cable", searched.direct_response)

    def test_agent_runtime_saves_make_a_note_phrasing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "make a note that the gate code is 4242",
                [ChatMessage("user", "make a note that the gate code is 4242")],
            )
            recalled = runtime.prepare(
                "what do you remember about gate code",
                [ChatMessage("user", "what do you remember about gate code")],
            )

        self.assertIn("Saved note", saved.direct_response)
        self.assertIn("4242", recalled.direct_response)

    def test_agent_runtime_saves_direct_save_object_without_model_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "Save the creating rain cloud.",
                [ChatMessage("user", "Save the creating rain cloud.")],
            )
            recalled = runtime.prepare(
                "what do you remember about rain cloud",
                [ChatMessage("user", "what do you remember about rain cloud")],
            )

        self.assertEqual(saved.direct_response, "Saved note: creating rain cloud")
        self.assertEqual(saved.messages, [ChatMessage("user", "Save the creating rain cloud.")])
        self.assertIn("- creating rain cloud", recalled.direct_response)

    def test_agent_runtime_saves_remember_that_as_note(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "remember that the spare key is in the desk drawer",
                [ChatMessage("user", "remember that the spare key is in the desk drawer")],
            )
            searched = runtime.prepare("search notes for spare key", [ChatMessage("user", "search notes for spare key")])

        self.assertIn("Saved note", saved.direct_response)
        self.assertIn("spare key", searched.direct_response)

    def test_agent_runtime_saves_note_with_wake_name_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "Damien, remember that the spare key is in the desk drawer",
                [ChatMessage("user", "Damien, remember that the spare key is in the desk drawer")],
            )
            searched = runtime.prepare("search notes for spare key", [ChatMessage("user", "search notes for spare key")])

        self.assertEqual(saved.direct_response, "Saved note: the spare key is in the desk drawer")
        self.assertIn("- the spare key is in the desk drawer", searched.direct_response)

    def test_agent_runtime_saves_note_without_that_in_spoken_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "Hey Damien, remember the spare key is in the desk drawer",
                [ChatMessage("user", "Hey Damien, remember the spare key is in the desk drawer")],
            )
            searched = runtime.prepare("search notes for spare key", [ChatMessage("user", "search notes for spare key")])

        self.assertEqual(saved.direct_response, "Saved note: the spare key is in the desk drawer")
        self.assertIn("- the spare key is in the desk drawer", searched.direct_response)

    def test_agent_runtime_saves_keep_in_mind_phrasing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "keep in mind that the garage remote is in my backpack",
                [ChatMessage("user", "keep in mind that the garage remote is in my backpack")],
            )
            searched = runtime.prepare(
                "what do you remember about garage remote",
                [ChatMessage("user", "what do you remember about garage remote")],
            )

        self.assertEqual(saved.direct_response, "Saved note: the garage remote is in my backpack")
        self.assertIn("- the garage remote is in my backpack", searched.direct_response)

    def test_agent_runtime_saves_would_you_mind_remembering_phrasing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "would you mind remembering that the garage remote is in my backpack",
                [ChatMessage("user", "would you mind remembering that the garage remote is in my backpack")],
            )
            searched = runtime.prepare(
                "what do you remember about garage remote",
                [ChatMessage("user", "what do you remember about garage remote")],
            )

        self.assertEqual(saved.direct_response, "Saved note: the garage remote is in my backpack")
        self.assertIn("- the garage remote is in my backpack", searched.direct_response)

    def test_agent_runtime_saves_would_you_mind_keep_in_mind_phrasing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            saved = runtime.prepare(
                "would you mind keeping in mind that the garage remote is in my backpack",
                [ChatMessage("user", "would you mind keeping in mind that the garage remote is in my backpack")],
            )
            searched = runtime.prepare(
                "what do you remember about garage remote",
                [ChatMessage("user", "what do you remember about garage remote")],
            )

        self.assertEqual(saved.direct_response, "Saved note: the garage remote is in my backpack")
        self.assertIn("- the garage remote is in my backpack", searched.direct_response)

    def test_agent_runtime_answers_what_did_i_say_about_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that the spare key is in the desk drawer",
                [ChatMessage("user", "remember that the spare key is in the desk drawer")],
            )
            recalled = runtime.prepare(
                "what did I say about spare key",
                [ChatMessage("user", "what did I say about spare key")],
            )

        self.assertIsNotNone(recalled.direct_response)
        self.assertIn("You said", recalled.direct_response)
        self.assertIn("spare key", recalled.direct_response)
        self.assertIn("desk drawer", recalled.direct_response)

    def test_agent_runtime_answers_what_do_you_remember_about_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that my passport is in the blue folder",
                [ChatMessage("user", "remember that my passport is in the blue folder")],
            )
            recalled = runtime.prepare(
                "what do you remember about passport",
                [ChatMessage("user", "what do you remember about passport")],
            )

        self.assertIsNotNone(recalled.direct_response)
        self.assertIn("I remember", recalled.direct_response)
        self.assertIn("passport", recalled.direct_response)
        self.assertIn("blue folder", recalled.direct_response)

    def test_agent_runtime_lists_recent_notes_with_broad_memory_question(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that my passport is in the blue folder",
                [ChatMessage("user", "remember that my passport is in the blue folder")],
            )
            recalled = runtime.prepare(
                "what do you remember for me",
                [ChatMessage("user", "what do you remember for me")],
            )

        self.assertEqual(
            recalled.direct_response,
            "I remember:\n- my passport is in the blue folder",
        )

    def test_agent_runtime_lists_recent_notes_with_saved_context_question(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that my passport is in the blue folder",
                [ChatMessage("user", "remember that my passport is in the blue folder")],
            )
            recalled = runtime.prepare(
                "what did you save for me",
                [ChatMessage("user", "what did you save for me")],
            )

        self.assertEqual(
            recalled.direct_response,
            "I remember:\n- my passport is in the blue folder",
        )

    def test_agent_runtime_lists_recent_notes_with_casual_saved_context_question(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that my passport is in the blue folder",
                [ChatMessage("user", "remember that my passport is in the blue folder")],
            )
            recalled = runtime.prepare(
                "what have you got saved for me",
                [ChatMessage("user", "what have you got saved for me")],
            )

        self.assertEqual(
            recalled.direct_response,
            "I remember:\n- my passport is in the blue folder",
        )

    def test_agent_runtime_answers_where_did_i_put_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that my passport is in the blue folder",
                [ChatMessage("user", "remember that my passport is in the blue folder")],
            )
            recalled = runtime.prepare(
                "where did I put my passport",
                [ChatMessage("user", "where did I put my passport")],
            )

        self.assertIsNotNone(recalled.direct_response)
        self.assertIn("I remember", recalled.direct_response)
        self.assertIn("passport", recalled.direct_response)
        self.assertIn("blue folder", recalled.direct_response)

    def test_agent_runtime_answers_where_is_memory_questions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that my passport is in the blue folder",
                [ChatMessage("user", "remember that my passport is in the blue folder")],
            )
            recalled = runtime.prepare(
                "where is my passport",
                [ChatMessage("user", "where is my passport")],
            )

        self.assertIsNotNone(recalled.direct_response)
        self.assertIn("I remember", recalled.direct_response)
        self.assertIn("passport", recalled.direct_response)
        self.assertIn("blue folder", recalled.direct_response)

    def test_agent_runtime_answers_conversational_where_memory_questions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that my passport is in the blue folder",
                [ChatMessage("user", "remember that my passport is in the blue folder")],
            )
            recalled = runtime.prepare(
                "do you remember where my passport is",
                [ChatMessage("user", "do you remember where my passport is")],
            )

        self.assertIsNotNone(recalled.direct_response)
        self.assertIn("I remember", recalled.direct_response)
        self.assertIn("passport", recalled.direct_response)
        self.assertIn("blue folder", recalled.direct_response)

    def test_agent_runtime_matches_simple_plural_memory_questions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = build_runtime(Path(temp_dir))

            runtime.prepare(
                "remember that the spare key is in the desk drawer",
                [ChatMessage("user", "remember that the spare key is in the desk drawer")],
            )
            recalled = runtime.prepare(
                "where are my keys",
                [ChatMessage("user", "where are my keys")],
            )

        self.assertIsNotNone(recalled.direct_response)
        self.assertIn("I remember", recalled.direct_response)
        self.assertIn("spare key", recalled.direct_response)
        self.assertIn("desk drawer", recalled.direct_response)


if __name__ == "__main__":
    unittest.main()
