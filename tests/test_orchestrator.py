import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import jarvis_assistant.orchestrator as orchestrator_module
from jarvis_assistant.ai import ChatMessage
from jarvis_assistant.audit import AuditLogger
from jarvis_assistant.commands import ApprovedApp, CommandDispatcher
from jarvis_assistant.config import load_settings
from jarvis_assistant.improvement import ImprovementQueue
from jarvis_assistant.memory import LongTermMemory
from jarvis_assistant.orchestrator import AssistantOrchestrator
from jarvis_assistant.retrieval import ApprovedDocumentRetriever
from jarvis_assistant.router import ProviderRouter
from jarvis_assistant.tools import ToolRegistry


class AssistantOrchestratorTests(unittest.TestCase):
    def _orchestrator(self, root: Path, tools: ToolRegistry | None = None) -> AssistantOrchestrator:
        settings = load_settings(root / "settings.json")
        return AssistantOrchestrator(
            ProviderRouter(settings),
            tools
            or ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            ),
            AuditLogger(root / "audit.jsonl", enabled=False),
            persona_style="cinematic",
            root=root,
        )

    def test_orchestrator_does_not_keep_legacy_multitask_parser(self):
        self.assertFalse(hasattr(AssistantOrchestrator, "_multitask_plans"))
        self.assertFalse(hasattr(AssistantOrchestrator, "_voice_preface"))
        self.assertFalse(hasattr(AssistantOrchestrator, "_audit_outcome"))
        self.assertFalse(hasattr(orchestrator_module, "_split_multitask_text"))

    def test_latest_user_message_stays_last_after_persona_context(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                ToolRegistry(
                    CommandDispatcher({}),
                    ApprovedDocumentRetriever(root / "docs"),
                    LongTermMemory(root / "memory.jsonl", enabled=False),
                ),
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
            )

            result = orchestrator.prepare(
                "test",
                [ChatMessage("system", "system prompt"), ChatMessage("user", "test")],
            )

        self.assertEqual(result.messages[-1], ChatMessage("user", "test"))
        self.assertEqual(result.messages[-2].role, "system")
        self.assertIn("speaking aloud", result.messages[-2].content)
        self.assertIn("short, clear spoken sentences", result.messages[-2].content)

    def test_voice_readiness_provider_reaches_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                ToolRegistry(
                    CommandDispatcher({}),
                    ApprovedDocumentRetriever(root / "docs"),
                    LongTermMemory(root / "memory.jsonl", enabled=False),
                ),
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
                voice_status_provider=lambda: "Voice ready: microphone, wake phrase, and speaker are available.",
            )

            result = orchestrator.prepare(
                "are you ready to listen and talk",
                [ChatMessage("user", "are you ready to listen and talk")],
            )

        self.assertEqual(result.direct_response, "Voice ready: microphone, wake phrase, and speaker are available.")

    def test_corrects_stt_noise_before_tool_routing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                ToolRegistry(
                    CommandDispatcher({"apex legends": ApprovedApp("Apex Legends", r"C:\Users\kaish\Desktop\Apex Legends.url")}),
                    ApprovedDocumentRetriever(root / "docs"),
                    LongTermMemory(root / "memory.jsonl", enabled=False),
                ),
                AuditLogger(root / "audit.jsonl", enabled=True),
                persona_style="cinematic",
                root=root,
            )

            with patch("jarvis_assistant.commands.os.startfile") as startfile:
                result = orchestrator.prepare("Lunch APEG's Legends.", [ChatMessage("user", "Lunch APEG's Legends.")])

        self.assertEqual(result.direct_response, "Opening Apex Legends. I will monitor the screen until the lobby is confirmed.")
        self.assertEqual(result.interpretation.corrected, "Launch apex legends.")
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Apex Legends.url")

    def test_strips_wake_phrase_before_media_tool_routing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                tools,
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
            )

            with patch.object(tools.convenience, "open_crunchyroll_title") as open_title:
                open_title.return_value = "Opened Crunchyroll for One Piece."
                result = orchestrator.prepare("hey Damien play One Piece", [ChatMessage("user", "hey Damien play One Piece")])

        self.assertEqual(result.direct_response, "Opened Crunchyroll for One Piece.")
        self.assertEqual(result.interpretation.corrected, "play One Piece")
        open_title.assert_called_once_with("One Piece")

    def test_second_playlist_command_does_not_replay_previous_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                tools,
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
            )

            with patch.object(tools.convenience, "play_itunes_playlist") as play_playlist:
                play_playlist.side_effect = [
                    "Shuffling iTunes playlist: workout.",
                    "Shuffling iTunes playlist: chill.",
                ]
                first = orchestrator.prepare("shuffle workout playlist", [ChatMessage("user", "shuffle workout playlist")])
                second = orchestrator.prepare(
                    "shuffle playlist chill",
                    [
                        ChatMessage("user", "shuffle workout playlist"),
                        ChatMessage("assistant", "Shuffling iTunes playlist: workout."),
                        ChatMessage("user", "shuffle playlist chill"),
                    ],
                )

        self.assertEqual(first.direct_response, "Shuffling iTunes playlist: workout.")
        self.assertEqual(second.direct_response, "Shuffling iTunes playlist: chill.")
        self.assertEqual(play_playlist.call_args_list[0].args, ("workout",))
        self.assertEqual(play_playlist.call_args_list[0].kwargs, {"shuffle": True})
        self.assertEqual(play_playlist.call_args_list[1].args, ("chill",))
        self.assertEqual(play_playlist.call_args_list[1].kwargs, {"shuffle": True})

    def test_second_media_command_does_not_replay_previous_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                tools,
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
            )

            with patch.object(tools.convenience, "media_control") as media_control:
                media_control.side_effect = ["Media pause.", "Media next."]
                first = orchestrator.prepare("pause", [ChatMessage("user", "pause")])
                second = orchestrator.prepare(
                    "skip song",
                    [
                        ChatMessage("user", "pause"),
                        ChatMessage("assistant", "Media pause."),
                        ChatMessage("user", "skip song"),
                    ],
                )

        self.assertEqual(first.direct_response, "Media pause.")
        self.assertEqual(second.direct_response, "Media next.")
        self.assertEqual(media_control.call_args_list[0].args, ("pause",))
        self.assertEqual(media_control.call_args_list[1].args, ("next",))

    def test_unpause_video_routes_to_media_control(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                tools,
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
            )

            with patch.object(tools.convenience, "media_control") as media_control:
                media_control.return_value = "Media resume."
                result = orchestrator.prepare("unpause my video", [ChatMessage("user", "unpause my video")])

        self.assertEqual(result.direct_response, "Media resume.")
        self.assertEqual(result.messages, [ChatMessage("user", "unpause my video")])
        media_control.assert_called_once_with("resume")

    def test_vague_crunchyroll_command_does_not_replay_previous_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = load_settings(root / "settings.json")
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = AssistantOrchestrator(
                ProviderRouter(settings),
                tools,
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                root=root,
            )

            with patch.object(tools.convenience, "open_crunchyroll_title") as open_title:
                open_title.return_value = "Opened Crunchyroll for One Piece."
                first = orchestrator.prepare("play One Piece", [ChatMessage("user", "play One Piece")])
                second = orchestrator.prepare(
                    "continue watching",
                    [
                        ChatMessage("user", "play One Piece"),
                        ChatMessage("assistant", "Opened Crunchyroll for One Piece."),
                        ChatMessage("user", "continue watching"),
                    ],
                )

        self.assertEqual(first.direct_response, "Opened Crunchyroll for One Piece.")
        self.assertEqual(second.direct_response, "Which Crunchyroll title should I open?")
        open_title.assert_called_once_with("One Piece")

    def test_typo_and_stt_scenarios_route_to_tools(self):
        scenarios = {
            "hey Damien pause": "media_control",
            "Damien, skip song": "media_control",
            "Damien, can you shuffle playlist workout": "itunes_playlist",
            "play shuffle late night playlist": "itunes_playlist",
            "hey damian watch One Piece": "crunchyroll_title",
            "lunch crunchy roll": "open_approved_app",
            "what dime is it": "local_time",
            "what aps can you open": "list_approved_apps",
            "open the i tunes app": "open_approved_app",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher(
                    {
                        "crunchyroll": ApprovedApp("Crunchyroll", r"C:\Users\kaish\Desktop\Crunchyroll.url"),
                        "itunes": ApprovedApp("iTunes", r"C:\Program Files\iTunes\iTunes.exe"),
                    }
                ),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = self._orchestrator(root, tools)

            for command, expected_tool in scenarios.items():
                with self.subTest(command=command):
                    with patch.object(tools, "execute") as execute:
                        execute.return_value = type(
                            "Result",
                            (),
                            {
                                "name": expected_tool,
                                "risk": type("Risk", (), {"value": "low"})(),
                                "content": "ok",
                                "confirmation_required": False,
                            },
                        )()
                        result = orchestrator.prepare(command, [ChatMessage("user", command)])

                    self.assertEqual(result.direct_response, "ok")
                    self.assertEqual(execute.call_args.args[0].name, expected_tool)

    def test_missing_capability_request_logs_upgrade_instead_of_defaulting_to_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            orchestrator = AssistantOrchestrator(
                ProviderRouter(load_settings(root / "settings.json")),
                ToolRegistry(
                    CommandDispatcher({}),
                    ApprovedDocumentRetriever(root / "docs"),
                    LongTermMemory(root / "memory.jsonl", enabled=False),
                ),
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                improvement_queue=ImprovementQueue(root),
                root=root,
            )

            result = orchestrator.prepare(
                "Damien should ask Codex to add this ability",
                [ChatMessage("user", "Damien should ask Codex to add this ability")],
            )

            queue_path = root / "logs" / "improvement_queue.jsonl"

            self.assertIsNotNone(result.direct_response)
            self.assertIn("logged it as an upgrade for Codex", result.direct_response)
            self.assertTrue(queue_path.exists())

    def test_assistant_benchmark_complaint_starts_upgrade_instead_of_defaulting_to_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            orchestrator = AssistantOrchestrator(
                ProviderRouter(load_settings(root / "settings.json")),
                ToolRegistry(
                    CommandDispatcher({}),
                    ApprovedDocumentRetriever(root / "docs"),
                    LongTermMemory(root / "memory.jsonl", enabled=False),
                ),
                AuditLogger(root / "audit.jsonl", enabled=False),
                persona_style="cinematic",
                improvement_queue=ImprovementQueue(root),
                root=root,
            )

            result = orchestrator.prepare(
                "this should be like siri cortana jarvis why arent we there yet",
                [ChatMessage("user", "this should be like siri cortana jarvis why arent we there yet")],
            )

            records = (root / "logs" / "improvement_queue.jsonl").read_text(encoding="utf-8")

        self.assertIsNotNone(result.direct_response)
        self.assertIn("upgrade for Codex", result.direct_response)
        self.assertIn("siri cortana jarvis", records)

    def test_multitask_executes_multiple_low_risk_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({"notepad": ApprovedApp("Notepad", "notepad.exe", process_names=("notepad.exe",))}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = self._orchestrator(root, tools)

            with patch("jarvis_assistant.commands.subprocess.Popen") as popen, patch.object(
                tools.convenience, "local_time", return_value="Local time: Tuesday at 1:00 PM"
            ):
                result = orchestrator.prepare(
                    "open notepad and what time is it",
                    [ChatMessage("user", "open notepad and what time is it")],
                )

        self.assertIn("Opening Notepad.", result.direct_response)
        self.assertIn("Local time: Tuesday at 1:00 PM", result.direct_response)
        self.assertEqual([tool.name for tool in result.tool_results], ["open_approved_app", "local_time"])
        popen.assert_called_once()

    def test_multitask_runs_discord_call_and_game_lobby_routine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({"apex legends": ApprovedApp("Apex Legends", r"C:\Users\kaish\Desktop\Apex Legends.url")}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = self._orchestrator(root, tools)

            with patch.object(tools.convenience, "discord_call", return_value="Starting Discord call with the group chat."), patch(
                "jarvis_assistant.commands.os.startfile"
            ) as startfile, patch("jarvis_assistant.commands.schedule_lobby_entry") as lobby:
                result = orchestrator.prepare(
                    "call the group chat, open Apex Legends, and take me to lobby",
                    [ChatMessage("user", "call the group chat, open Apex Legends, and take me to lobby")],
                )

        self.assertIn("Starting Discord call with the group chat.", result.direct_response)
        self.assertIn("Opening Apex Legends. I will monitor the screen until the lobby is confirmed.", result.direct_response)
        self.assertEqual([tool.name for tool in result.tool_results], ["discord_call", "open_approved_app"])
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Apex Legends.url")
        lobby.assert_called_once_with("apex legends")

    def test_multitask_runs_roblox_game_and_short_discord_call(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = self._orchestrator(root, tools)

            with patch.object(
                tools.convenience,
                "open_roblox_game",
                return_value="Opening Roblox search for Devil Hunters.",
            ), patch.object(
                tools.convenience,
                "discord_call",
                return_value="Starting Discord call with m.",
            ):
                result = orchestrator.prepare(
                    "open Devil Hunters on Roblox and call m",
                    [ChatMessage("user", "open Devil Hunters on Roblox and call m")],
                )

        self.assertIn("Opening Roblox search for Devil Hunters.", result.direct_response)
        self.assertIn("Starting Discord call with m.", result.direct_response)
        self.assertEqual([tool.name for tool in result.tool_results], ["open_roblox_game", "discord_call"])

    def test_single_roblox_game_command_does_not_fall_through_to_approved_apps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = self._orchestrator(root, tools)

            with patch.object(
                tools.convenience,
                "open_roblox_game",
                return_value="I do not have Devil Hunters saved yet, so I opened Roblox search for it.",
            ):
                result = orchestrator.prepare(
                    "Open Devil Hunters on Roblox.",
                    [ChatMessage("user", "Open Devil Hunters on Roblox.")],
                )

        self.assertEqual(result.direct_response, "I do not have Devil Hunters saved yet, so I opened Roblox search for it.")
        self.assertEqual([tool.name for tool in result.tool_results], ["open_roblox_game"])

    def test_multitask_recovers_split_call_target_from_stt_punctuation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            tools = ToolRegistry(
                CommandDispatcher({"roblox": ApprovedApp("Roblox Player", r"C:\Users\kaish\Desktop\Roblox.lnk")}),
                ApprovedDocumentRetriever(root / "docs"),
                LongTermMemory(root / "memory.jsonl", enabled=False),
            )
            orchestrator = self._orchestrator(root, tools)

            with patch("jarvis_assistant.commands.os.startfile") as startfile, patch.object(
                tools.convenience,
                "discord_call",
                return_value="Starting Discord call with messy dee.",
            ):
                result = orchestrator.prepare(
                    "Open Roblox, and, call, messy dee.",
                    [ChatMessage("user", "Open Roblox, and, call, messy dee.")],
                )

        self.assertIn("Opening Roblox Player.", result.direct_response)
        self.assertIn("Starting Discord call with messy dee.", result.direct_response)
        self.assertEqual([tool.name for tool in result.tool_results], ["open_approved_app", "discord_call"])
        startfile.assert_called_once_with(r"C:\Users\kaish\Desktop\Roblox.lnk")

    def test_handles_reminder_through_agent_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            orchestrator = self._orchestrator(root)
            orchestrator.agent.now = lambda: datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

            result = orchestrator.prepare(
                "remind me in 10 minutes to drink water",
                [ChatMessage("user", "remind me in 10 minutes to drink water")],
            )

        self.assertIn("Reminder set", result.direct_response)
        self.assertIn("drink water", result.direct_response)

    def test_check_proactive_returns_due_reminder_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
            orchestrator = self._orchestrator(root)
            orchestrator.agent.now = lambda: now
            orchestrator.prepare("remind me in 1 minutes to stretch", [ChatMessage("user", "remind me in 1 minutes to stretch")])
            orchestrator.agent.now = lambda: datetime(2026, 7, 27, 12, 1, tzinfo=timezone.utc)

            first = orchestrator.check_proactive()
            second = orchestrator.check_proactive()

        self.assertEqual(first, ["Reminder: stretch"])
        self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main()
