import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis_assistant.improvement import (
    ImprovementQueue,
    SelfRepairManager,
    UpgradeIntentHandler,
    _start_background_repair,
    build_missing_capability_response,
    is_generic_windows_assistant_response,
)


class ImprovementTests(unittest.TestCase):
    def test_background_repair_closes_parent_transcript_handle_after_spawn(self):
        class FakeTranscript:
            closed = False

            def close(self):
                self.closed = True

        transcript = FakeTranscript()

        with patch.object(Path, "open", return_value=transcript), patch(
            "jarvis_assistant.improvement.subprocess.Popen", return_value=object()
        ):
            _start_background_repair(["codex", "exec"], Path("."), Path("repair.log"))

        self.assertTrue(transcript.closed)

    def test_missing_capability_response_logs_codex_ready_upgrade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = ImprovementQueue(root)

            message = build_missing_capability_response(
                "Damien should operate this app for me",
                queue,
                suggestion="Add a safe UI automation tool.",
            )

            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]

            self.assertIn("logged it as an upgrade for Codex", message)
            self.assertEqual(records[0]["request"], "Damien should operate this app for me")
            self.assertEqual(records[0]["suggestion"], "Add a safe UI automation tool.")
            self.assertTrue((root / "improvement_tasks").exists())

    def test_upgrade_intent_handler_logs_missing_capability_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = ImprovementQueue(root)
            handler = UpgradeIntentHandler(queue)

            message = handler.handle("Damien should operate this app for me")

            records = [
                json.loads(line)
                for line in (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertIsNotNone(message)
        self.assertIn("upgrade for Codex", message)
        self.assertEqual(records[0]["request"], "Damien should operate this app for me")

    def test_missing_capability_response_says_repair_started_when_codex_launches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = SelfRepairManager(root, runner=lambda command, cwd, transcript: None)
            queue = ImprovementQueue(root, repair_manager=manager)

            message = build_missing_capability_response(
                "Damien should operate this app for me",
                queue,
                suggestion="Add a safe UI automation tool.",
            )

            self.assertIn("started a Codex repair", message)

    def test_queue_can_list_and_prepare_latest_codex_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = ImprovementQueue(root)
            queue.log("Open a new game lobby", "No game routine exists.", "Add a game lobby profile.")

            summary = queue.summary()
            task_path = queue.prepare_latest_task()
            task_text = task_path.read_text(encoding="utf-8")

        self.assertIn("Open a new game lobby", summary)
        self.assertIn("Add a game lobby profile", task_text)
        self.assertEqual(task_path.parent.name, "improvement_tasks")

    def test_self_repair_manager_launches_codex_for_new_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            calls = []
            manager = SelfRepairManager(
                root,
                runner=lambda command, cwd, transcript: calls.append((command, cwd)),
                codex_command="C:\\Tools\\codex.exe",
            )
            queue = ImprovementQueue(root, repair_manager=manager)

            queue.log("Call spoiled on Discord", "Button was not found.", "Improve Discord call automation.")

            self.assertEqual(len(calls), 1)
            command, cwd = calls[0]
            self.assertEqual(cwd, root)
            self.assertEqual(command[:4], ["C:\\Tools\\codex.exe", "exec", "--cd", str(root)])
            self.assertNotIn("--ask-for-approval", command)
            self.assertIn("Call spoiled on Discord", " ".join(command))
            log_records = [
                json.loads(line)
                for line in (root / "logs" / "self_repair.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(log_records[-1]["transcript_path"].endswith(".log"))

    def test_self_repair_manager_uses_durable_prompt_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            calls = []
            manager = SelfRepairManager(
                root,
                runner=lambda command, cwd, transcript: calls.append((command, cwd)),
                codex_command="C:\\Tools\\codex.exe",
            )
            task_path = root / "improvement_tasks" / "task.md"
            task_path.parent.mkdir()
            task_path.write_text("# Task\n", encoding="utf-8")

            manager.request_repair(
                {
                    "request": "Take Apex Legends to lobby",
                    "reason": "Could not find the Continue button.",
                    "suggestion": "Improve Apex lobby automation.",
                },
                task_path,
            )

            command, _cwd = calls[0]
            prompt_arg = command[-1]
            self.assertNotIn("\n", prompt_arg)
            self.assertIn("repair prompt file", prompt_arg)

            prompt_path = root / "logs" / "self_repair_prompts" / "take-apex-legends-to-lobby-could-not-find-the-continue-button-improve-apex-lobby-automation.md"
            self.assertTrue(prompt_path.exists())
            prompt_text = prompt_path.read_text(encoding="utf-8")
            self.assertIn("Task file:", prompt_text)
            self.assertIn("Take Apex Legends to lobby", prompt_text)

    def test_self_repair_manager_deduplicates_same_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            calls = []
            manager = SelfRepairManager(root, runner=lambda command, cwd, transcript: calls.append((command, cwd)))
            queue = ImprovementQueue(root, repair_manager=manager)

            queue.log("Call spoiled on Discord", "Button was not found.", "Improve Discord call automation.")
            queue.log("Call spoiled on Discord", "Button was not found.", "Improve Discord call automation.")

            self.assertEqual(len(calls), 1)

    def test_self_repair_manager_retries_after_failed_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            calls = []
            manager = SelfRepairManager(root, runner=lambda command, cwd, transcript: calls.append((command, cwd)))
            queue = ImprovementQueue(root, repair_manager=manager)

            queue.log("Call spoiled on Discord", "Button was not found.", "Improve Discord call automation.")
            fingerprint = json.loads((root / "logs" / "self_repair.jsonl").read_text(encoding="utf-8").splitlines()[-1])[
                "fingerprint"
            ]
            with (root / "logs" / "self_repair.jsonl").open("a", encoding="utf-8") as file:
                file.write(json.dumps({"fingerprint": fingerprint, "status": "failed_to_start"}) + "\n")
            queue.log("Call spoiled on Discord", "Button was not found.", "Improve Discord call automation.")

            self.assertEqual(len(calls), 2)

    def test_self_repair_manager_uses_source_workspace_when_running_from_dist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "pyproject.toml").write_text("[project]\nname='damien'\n", encoding="utf-8")
            (workspace / "src").mkdir()
            runtime_root = workspace / "dist_qol" / "Damien"
            runtime_root.mkdir(parents=True)
            task_path = runtime_root / "improvement_tasks" / "task.md"
            task_path.parent.mkdir()
            task_path.write_text("# Task\n", encoding="utf-8")
            calls = []
            manager = SelfRepairManager(
                runtime_root,
                runner=lambda command, cwd, transcript: calls.append((command, cwd)),
                codex_command="C:\\Tools\\codex.exe",
            )

            manager.request_repair(
                {
                    "request": "Call spoiled on Discord",
                    "reason": "Button was not found.",
                    "suggestion": "Improve Discord call automation.",
                },
                task_path,
            )

            command, cwd = calls[0]
            self.assertEqual(cwd, workspace)
            self.assertEqual(command[:4], ["C:\\Tools\\codex.exe", "exec", "--cd", str(workspace)])

    def test_self_repair_manager_wraps_codex_command_for_windows_shell_resolution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            calls = []
            manager = SelfRepairManager(
                root,
                runner=lambda command, cwd, transcript: calls.append((command, cwd)),
                codex_command="codex",
            )

            manager.request_repair(
                {
                    "request": "Call spoiled on Discord",
                    "reason": "Button was not found.",
                    "suggestion": "Improve Discord call automation.",
                },
                root / "task.md",
            )

            command, _cwd = calls[0]
            self.assertEqual(command[:5], ["cmd.exe", "/d", "/s", "/c", "codex"])

    def test_empty_queue_messages_are_actionable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            queue = ImprovementQueue(Path(temp_dir))

            self.assertIn("No queued Damien upgrades", queue.summary())
            self.assertIn("No failed command", queue.retry_latest_message())

    def test_detects_generic_windows_assistant_filler(self):
        self.assertTrue(
            is_generic_windows_assistant_response(
                "As a Windows desktop assistant, I can provide information and answer questions about Windows."
            )
        )
        self.assertFalse(is_generic_windows_assistant_response("I can open Discord and take notes."))


if __name__ == "__main__":
    unittest.main()
