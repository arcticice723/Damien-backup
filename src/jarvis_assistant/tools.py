from __future__ import annotations

import os
import platform
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum

from .commands import CommandDispatcher
from .convenience import ConvenienceTools
from .game_lobby import has_lobby_profile
from .memory import LongTermMemory
from .retrieval import ApprovedDocumentRetriever
from .system_metrics import get_gpu_memory
from .runtime import APP_ROOT


class RiskLevel(str, Enum):
    LOW = "low"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True)
class ToolResult:
    name: str
    risk: RiskLevel
    content: str
    executed: bool = True
    confirmation_required: bool = False


@dataclass(frozen=True)
class PlannedTool:
    name: str
    risk: RiskLevel
    reason: str
    args: dict[str, str] = field(default_factory=dict)


class ToolRegistry:
    RISKY_PATTERN = re.compile(
        r"\b(delete|remove|erase|format|shutdown|restart|install|uninstall|buy|purchase|send email|submit|download)\b",
        re.IGNORECASE,
    )
    FILE_SEARCH_PATTERN = re.compile(r"\b(search|find|look up)\b.*\b(files?|documents?|docs?|notes?)\b", re.IGNORECASE)
    WEB_PATTERN = re.compile(r"\b(web|internet|online|search the web|look up online)\b", re.IGNORECASE)
    OPEN_WEB_PATTERN = re.compile(r"^\s*(?:open|launch|go to)\s+(?:the\s+)?(?:website\s+)?(?P<target>(?:https?://)?[a-z0-9.-]+\.[a-z]{2,}.*)$", re.IGNORECASE)
    CLIPBOARD_PATTERN = re.compile(r"^\s*(?:copy|put)\s+(?P<value>.+?)\s+(?:to|on)\s+(?:the\s+)?clipboard\s*$", re.IGNORECASE)
    NOTE_PATTERN = re.compile(r"^\s*(?:take|make|save)\s+(?:a\s+)?note(?: that|:)?\s+(?P<value>.+)$", re.IGNORECASE)
    LIST_NOTES_PATTERN = re.compile(r"\b(show|list|read)\s+(?:my\s+)?notes\b", re.IGNORECASE)
    TIME_PATTERN = re.compile(r"\b(what time is it|current time|what day is it|today's date|date today)\b", re.IGNORECASE)
    OPEN_AREA_PATTERN = re.compile(r"^\s*open\s+(?P<area>approved documents|documents|notes|logs|settings|config)\s*(?:folder)?\s*$", re.IGNORECASE)
    LIST_APPS_PATTERN = re.compile(r"\b(what apps can you open|list approved apps|approved apps)\b", re.IGNORECASE)
    DISCORD_CALL_PATTERNS = (
        re.compile(
            r"^\s*(?:start|make|open)?\s*(?:a\s+)?discord\s+(?:voice\s+)?call\s+(?:with|to)?\s*(?P<target>.+?)\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?:start|make|open)?\s*(?:a\s+)?(?:voice\s+)?call\s+(?:with|to)?\s*(?P<target>.+?)\s+(?:on|in)\s+discord\s*$",
            re.IGNORECASE,
        ),
    )
    NATURAL_DISCORD_CALL_PATTERN = re.compile(
        r"^\s*(?:call|voice\s+call)\s+(?P<target>.+?)\s*$",
        re.IGNORECASE,
    )
    DISCORD_ANSWER_CALL_PATTERN = re.compile(
        r"^\s*(?:answer|accept|receive|pick\s+up|join)\s+(?:the\s+)?(?:incoming\s+)?(?:discord\s+)?(?:voice\s+)?call(?:\s+(?:on|in)\s+discord)?\s*$|"
        r"^\s*(?:answer|accept|receive|pick\s+up|join)\s+(?:the\s+)?(?:incoming\s+)?(?:call)\s+(?:on|in)\s+discord\s*$",
        re.IGNORECASE,
    )
    ROBLOX_GAME_PATTERNS = (
        re.compile(
            r"^\s*(?:open|launch|start|play)\s+(?P<game>.+?)\s+(?:on|in)\s+roblox[.!?]?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?:open|launch|start|play)\s+roblox\s+(?:game|experience)\s+(?P<game>.+?)[.!?]?\s*$",
            re.IGNORECASE,
        ),
    )
    EDITOR_PROJECT_PATTERNS = (
        re.compile(
            r"^\s*(?:open|launch|start)\s+(?P<project>.+?)\s+(?:in|with|using)\s+(?P<editor>unreal(?:\s+engine)?|ue5?|roblox(?:\s+studio)?)\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?:open|launch|start)\s+(?P<editor>unreal(?:\s+engine)?|ue5?|roblox(?:\s+studio)?)\s+(?:project|place|game)\s+(?P<project>.+?)\s*$",
            re.IGNORECASE,
        ),
    )
    MASCOT_UI_PATTERN = re.compile(
        r"^\s*(?:open|launch|start|show|bring\s+up)\s+(?:the\s+)?(?:damien\s+)?(?:mascot|companion|butler)(?:\s+companion|\s+mascot)?\s*$",
        re.IGNORECASE,
    )
    SCREEN_ACCESS_PATTERN = re.compile(
        r"\b(read|scan|look at|see|check|capture|screenshot|what'?s on|what is on|show me)\b.*\b(my\s+)?screen\b|\b(take a screenshot|screen capture)\b",
        re.IGNORECASE,
    )
    SAFE_UI_CLICK_PATTERN = re.compile(r"^\s*(?:click|press|tap)\s+(?P<label>continue|launch|play|start|ok|yes)\s*$", re.IGNORECASE)
    UI_BUTTON_CLICK_PATTERN = re.compile(r"^\s*click\s+ui\s+button\s*[:\-]\s*(?P<label>.+?)\s*$", re.IGNORECASE)
    POWERSHELL_PATTERN = re.compile(r"^\s*(?:run|execute)\s+powershell\s*[:\-]\s*(?P<command>.+?)\s*$", re.IGNORECASE | re.DOTALL)
    CONFIRM_PENDING_ACTION_PATTERN = re.compile(r"^\s*confirm\s*$", re.IGNORECASE)
    CANCEL_PENDING_ACTION_PATTERN = re.compile(r"^\s*cancel\s*$", re.IGNORECASE)
    LOBBY_FOLLOWUP_PATTERN = re.compile(
        r"^\s*(?:(?:take|get|bring)(?:\s+me)?\s+to|go\s+to|continue\s+to)\s+(?:the\s+)?lobby\s*$",
        re.IGNORECASE,
    )
    NAMED_LOBBY_PATTERN = re.compile(
        r"^\s*(?:take|get|bring)\s+(?:me\s+)?(?P<app>.+?)\s+to\s+(?:the\s+)?lobby\s*$",
        re.IGNORECASE,
    )
    LIST_IMPROVEMENTS_PATTERN = re.compile(
        r"\b(show|list|read|what)\b.*\b(improvement|upgrade|fail|failed|queue)\b",
        re.IGNORECASE,
    )
    PREPARE_IMPROVEMENT_PATTERN = re.compile(
        r"\b(?:ask|tell)\s+codex\s+to\s+(?:upgrade|improve|fix)\s+(?:that|it|latest|last)\b|"
        r"\b(?:prepare|make|create)\b.*\b(?:latest|last)\b.*\b(?:upgrade|improvement)\b.*\btask\b",
        re.IGNORECASE,
    )
    RETRY_FAILED_PATTERN = re.compile(r"\b(retry|try again)\b.*\b(last|latest)?\s*(failed|failure|command)\b", re.IGNORECASE)
    SHUFFLE_PLAYLIST_PATTERNS = (
        re.compile(r"^\s*(?:shuffle|play\s+shuffle)\s+(?:my\s+)?(?P<playlist>.+?)\s+playlist\s*$", re.IGNORECASE),
        re.compile(r"^\s*(?:shuffle|play\s+shuffle)\s+(?:my\s+)?playlist\s+(?P<playlist>.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*(?:shuffle|play\s+shuffle)\s+(?:my\s+)?(?P<playlist>.+?)\s*$", re.IGNORECASE),
    )
    PLAY_PLAYLIST_PATTERNS = (
        re.compile(r"^\s*play\s+(?:my\s+)?(?P<playlist>.+?)\s+playlist\s*$", re.IGNORECASE),
        re.compile(r"^\s*play\s+(?:my\s+)?playlist\s+(?P<playlist>.+?)\s*$", re.IGNORECASE),
    )
    VAGUE_PLAYLIST_PATTERN = re.compile(r"^\s*(?:shuffle|play\s+shuffle|play)\s+(?:my\s+)?(?:another\s+)?playlist\s*$", re.IGNORECASE)
    PLAY_CRUNCHYROLL_PATTERN = re.compile(
        r"^\s*(?:play|watch|continue|resume)\s+(?P<title>.+?)(?:\s+(?:on|in)\s+crunchyroll)?\s*$",
        re.IGNORECASE,
    )
    VAGUE_CRUNCHYROLL_PATTERN = re.compile(
        r"^\s*(?:play|watch|continue|resume)(?:\s+(?:watching|anime|crunchyroll|show|episode|series|it|that|this))?\s*$",
        re.IGNORECASE,
    )
    SET_CRUNCHYROLL_PROFILE_PATTERN = re.compile(
        r"^\s*(?:set|use|switch\s+to)\s+(?:my\s+)?crunchyroll\s+profile\s+(?:to|as)?\s*(?P<profile>.+?)\s*$",
        re.IGNORECASE,
    )
    REMEMBER_PATTERN = re.compile(r"^\s*remember(?: that)?\s+(?P<value>.+)$", re.IGNORECASE)
    RECALL_PATTERN = re.compile(r"\b(what do you remember|show memory|list memories)\b", re.IGNORECASE)
    STATUS_PATTERN = re.compile(r"\b(system status|pc status|gpu|memory|vram)\b", re.IGNORECASE)
    CAPABILITIES_PATTERN = re.compile(r"\b(what can you do|help|abilities|commands)\b", re.IGNORECASE)
    QUICK_MODE_PATTERN = re.compile(r"^\s*(?P<mode>anime|gaming|focus)\s+mode\s*$", re.IGNORECASE)
    MEDIA_CONTROL_PATTERN = re.compile(
        r"^\s*(?P<action>pause|unpause|resume|play|next|skip|previous|back)(?:\s+(?:my\s+|the\s+)?(?:song|track|music|itunes|media|video|episode))?[.!?]?\s*$",
        re.IGNORECASE,
    )
    NATURAL_MEDIA_CONTROL_PATTERN = re.compile(
        r"^\s*(?:play|start|resume)\s+(?:some\s+)?(?:music|itunes|media|a\s+song|the\s+song)\s*$",
        re.IGNORECASE,
    )
    NEXT_MEDIA_PATTERN = re.compile(r"^\s*(?:play\s+)?(?:the\s+)?(?:next|skip)\s+(?:song|track)\s*$", re.IGNORECASE)
    PREVIOUS_MEDIA_PATTERN = re.compile(r"^\s*(?:play\s+)?(?:the\s+)?(?:previous|last|back)\s+(?:song|track)\s*$", re.IGNORECASE)

    def __init__(
        self,
        commands: CommandDispatcher,
        retriever: ApprovedDocumentRetriever,
        memory: LongTermMemory,
        convenience: ConvenienceTools | None = None,
        risk_mode: str = "low_risk_auto",
    ) -> None:
        self.commands = commands
        self.retriever = retriever
        self.memory = memory
        self.convenience = convenience or ConvenienceTools()
        self.risk_mode = risk_mode
        self._pending_powershell: tuple[str, float] | None = None
        self._pending_ui_click: tuple[str, float] | None = None
        self._pending_action_lock = threading.Lock()

    def plan(self, text: str) -> PlannedTool | None:
        text = _strip_confirmation_command_prefix(text)
        with self._pending_action_lock:
            if self._pending_powershell and time.monotonic() - self._pending_powershell[1] > 120:
                self._pending_powershell = None
            if self._pending_ui_click and time.monotonic() - self._pending_ui_click[1] > 120:
                self._pending_ui_click = None
            if self.CONFIRM_PENDING_ACTION_PATTERN.match(text):
                if self._pending_powershell is not None:
                    command, _created_at = self._pending_powershell
                    self._pending_powershell = None
                    return PlannedTool("run_powershell", RiskLevel.LOW, "User confirmed this PowerShell command.", {"command": command})
                if self._pending_ui_click is not None:
                    label, _created_at = self._pending_ui_click
                    self._pending_ui_click = None
                    return PlannedTool("click_ui_button", RiskLevel.LOW, "User confirmed this UI button click.", {"label": label})
                return PlannedTool("no_pending_confirmation", RiskLevel.LOW, "There is no pending action to confirm.")
            if self.CANCEL_PENDING_ACTION_PATTERN.match(text):
                had_pending = self._pending_powershell is not None or self._pending_ui_click is not None
                self._pending_powershell = None
                self._pending_ui_click = None
                return PlannedTool(
                    "cancel_powershell",
                    RiskLevel.LOW,
                    "Cancel the pending PowerShell command.",
                    {"had_pending": str(had_pending)},
                )
        clipboard = self.CLIPBOARD_PATTERN.match(text)
        if clipboard:
            return PlannedTool("copy_to_clipboard", RiskLevel.LOW, "Copy user-provided text to clipboard.", {"value": clipboard.group("value")})
        note = self.NOTE_PATTERN.match(text)
        if note:
            return PlannedTool("add_note", RiskLevel.LOW, "Save a local Damien note.", {"value": note.group("value")})
        if self.RISKY_PATTERN.search(text):
            return PlannedTool("blocked_high_risk_action", RiskLevel.DENY, "Dangerous action denied by policy.")
        ui_click = self.UI_BUTTON_CLICK_PATTERN.match(text)
        if ui_click:
            label = ui_click.group("label").strip().strip("'\"")
            if not label or len(label) > 120:
                return PlannedTool("missing_ui_button_label", RiskLevel.LOW, "Tell me the exact visible button label.")
            with self._pending_action_lock:
                self._pending_powershell = None
                self._pending_ui_click = (label, time.monotonic())
            return PlannedTool(
                "ui_click_confirmation",
                RiskLevel.CONFIRM,
                f"Click the visible button {label!r}? Reply CONFIRM to click or CANCEL to discard it.",
            )
        powershell = self.POWERSHELL_PATTERN.match(text)
        if powershell:
            command = powershell.group("command").strip()
            with self._pending_action_lock:
                self._pending_ui_click = None
                self._pending_powershell = (command, time.monotonic())
            return PlannedTool(
                "powershell_confirmation",
                RiskLevel.CONFIRM,
                f"Run this PowerShell command?\n{command}\nReply CONFIRM to run it or CANCEL to discard it.",
            )
        if self.CAPABILITIES_PATTERN.search(text):
            return PlannedTool("capabilities", RiskLevel.LOW, "List Damien's enabled local abilities.")
        if self.MASCOT_UI_PATTERN.match(text):
            return PlannedTool("mascot_ui_info", RiskLevel.LOW, "Explain that Damien's mascot is a UI feature, not a launcher.")
        if self.SCREEN_ACCESS_PATTERN.search(text):
            return PlannedTool("read_screen", RiskLevel.LOW, "Capture the current screen on request.")
        safe_click = self.SAFE_UI_CLICK_PATTERN.match(text)
        if safe_click:
            return PlannedTool(
                "safe_ui_click",
                RiskLevel.LOW,
                "Click an approved low-risk visible UI button.",
                {"label": safe_click.group("label")},
            )
        if self.LOBBY_FOLLOWUP_PATTERN.match(text):
            return PlannedTool("take_me_to_lobby", RiskLevel.LOW, "Run the last game lobby automation.")
        named_lobby = self.NAMED_LOBBY_PATTERN.match(text)
        if named_lobby:
            resolved_name, _app = self.commands._resolve_app(named_lobby.group("app"))
            if resolved_name and has_lobby_profile(resolved_name):
                return PlannedTool(
                    "take_me_to_lobby",
                    RiskLevel.LOW,
                    "Run a specific game lobby automation.",
                    {"app_name": resolved_name},
                )
        if self.RETRY_FAILED_PATTERN.search(text):
            return PlannedTool("retry_latest_failed_command", RiskLevel.LOW, "Report the latest failed command for retry.")
        if self.PREPARE_IMPROVEMENT_PATTERN.search(text):
            return PlannedTool("prepare_latest_improvement_task", RiskLevel.LOW, "Prepare the latest Codex upgrade task.")
        if self.LIST_IMPROVEMENTS_PATTERN.search(text):
            return PlannedTool("list_improvements", RiskLevel.LOW, "List queued Damien upgrade requests.")
        if self.DISCORD_ANSWER_CALL_PATTERN.match(text):
            return PlannedTool("discord_answer_call", RiskLevel.LOW, "Answer an incoming Discord call.")
        for roblox_game in (pattern.match(text) for pattern in self.ROBLOX_GAME_PATTERNS):
            if roblox_game:
                game = _clean_roblox_game_name(roblox_game.group("game"))
                if game:
                    return PlannedTool(
                        "open_roblox_game",
                        RiskLevel.LOW,
                        "Open a saved Roblox experience or Roblox search.",
                        {"game": game},
                    )
                return PlannedTool("missing_roblox_game_name", RiskLevel.LOW, "Ask which Roblox game to open.")
        for editor_project in (pattern.match(text) for pattern in self.EDITOR_PROJECT_PATTERNS):
            if editor_project:
                project = _clean_editor_project_name(editor_project.group("project"))
                editor = editor_project.group("editor")
                if project:
                    return PlannedTool(
                        "open_editor_project",
                        RiskLevel.LOW,
                        "Open an Unreal Engine or Roblox Studio project.",
                        {"editor": editor, "project": project},
                    )
                return PlannedTool("missing_editor_project_name", RiskLevel.LOW, "Ask which editor project to open.", {"editor": editor})
        for discord_call in (pattern.match(text) for pattern in self.DISCORD_CALL_PATTERNS):
            if discord_call:
                target = _clean_discord_call_target(discord_call.group("target"))
                if target:
                    return PlannedTool("discord_call", RiskLevel.LOW, "Start an approved Discord voice call.", {"target": target})
                return PlannedTool("missing_discord_call_target", RiskLevel.LOW, "Ask who to call on Discord.")
        natural_discord_call = self.NATURAL_DISCORD_CALL_PATTERN.match(text)
        if natural_discord_call:
            target = _clean_discord_call_target(natural_discord_call.group("target"))
            if target:
                return PlannedTool("discord_call", RiskLevel.LOW, "Start an approved Discord voice call.", {"target": target})
            return PlannedTool("missing_discord_call_target", RiskLevel.LOW, "Ask who to call on Discord.")
        quick_mode = self.QUICK_MODE_PATTERN.match(text)
        if quick_mode:
            return PlannedTool("quick_mode", RiskLevel.LOW, "Run a local convenience mode.", {"mode": quick_mode.group("mode").lower()})
        if self.NATURAL_MEDIA_CONTROL_PATTERN.match(text):
            return PlannedTool("media_control", RiskLevel.LOW, "Send a media key command.", {"action": "play"})
        if self.NEXT_MEDIA_PATTERN.match(text):
            return PlannedTool("media_control", RiskLevel.LOW, "Send a media key command.", {"action": "next"})
        if self.PREVIOUS_MEDIA_PATTERN.match(text):
            return PlannedTool("media_control", RiskLevel.LOW, "Send a media key command.", {"action": "previous"})
        media_control = self.MEDIA_CONTROL_PATTERN.match(text)
        if media_control:
            action = media_control.group("action").lower()
            if action == "skip":
                action = "next"
            if action == "unpause":
                action = "resume"
            return PlannedTool("media_control", RiskLevel.LOW, "Send a media key command.", {"action": action})
        open_area = self.OPEN_AREA_PATTERN.match(text)
        if open_area:
            return PlannedTool("open_project_area", RiskLevel.LOW, "Open an approved Damien project folder.", {"area": open_area.group("area")})
        open_web = self.OPEN_WEB_PATTERN.match(text)
        if open_web:
            return PlannedTool("open_web", RiskLevel.LOW, "Open a website or browser search.", {"target": open_web.group("target")})
        if self.commands.OPEN_APP_PATTERN.match(text):
            return PlannedTool("open_approved_app", RiskLevel.LOW, "Approved app command.", {"text": text})
        if self.commands.CLOSE_APP_PATTERN.match(text):
            return PlannedTool("close_approved_app", RiskLevel.LOW, "Close an approved app.", {"text": text})
        if self.LIST_APPS_PATTERN.search(text):
            return PlannedTool("list_approved_apps", RiskLevel.LOW, "List approved app launch shortcuts.")
        for shuffle_playlist in (pattern.match(text) for pattern in self.SHUFFLE_PLAYLIST_PATTERNS):
            if shuffle_playlist:
                playlist = _clean_playlist_name(shuffle_playlist.group("playlist"))
                if playlist:
                    return PlannedTool("itunes_playlist", RiskLevel.LOW, "Shuffle an iTunes playlist.", {"playlist": playlist, "shuffle": "true"})
        for play_playlist in (pattern.match(text) for pattern in self.PLAY_PLAYLIST_PATTERNS):
            if play_playlist:
                playlist = _clean_playlist_name(play_playlist.group("playlist"))
                if playlist:
                    return PlannedTool("itunes_playlist", RiskLevel.LOW, "Play an iTunes playlist.", {"playlist": playlist, "shuffle": "false"})
        if self.VAGUE_PLAYLIST_PATTERN.match(text):
            return PlannedTool("missing_playlist_name", RiskLevel.LOW, "Ask for a playlist name.")
        if self.VAGUE_CRUNCHYROLL_PATTERN.match(text):
            return PlannedTool("missing_crunchyroll_title", RiskLevel.LOW, "Ask for a Crunchyroll title.")
        play_crunchyroll = self.PLAY_CRUNCHYROLL_PATTERN.match(text)
        if play_crunchyroll and not _looks_like_tool_command(play_crunchyroll.group("title")):
            title = _clean_crunchyroll_title(play_crunchyroll.group("title"))
            if title:
                return PlannedTool("crunchyroll_title", RiskLevel.LOW, "Open a Crunchyroll title search.", {"title": title})
            return PlannedTool("missing_crunchyroll_title", RiskLevel.LOW, "Ask for a Crunchyroll title.")
        crunchyroll_profile = self.SET_CRUNCHYROLL_PROFILE_PATTERN.match(text)
        if crunchyroll_profile:
            return PlannedTool(
                "set_crunchyroll_profile",
                RiskLevel.LOW,
                "Save the preferred Crunchyroll profile name.",
                {"profile": crunchyroll_profile.group("profile")},
            )
        if self.LIST_NOTES_PATTERN.search(text):
            return PlannedTool("list_notes", RiskLevel.LOW, "Read local Damien notes.")
        if self.TIME_PATTERN.search(text):
            return PlannedTool("local_time", RiskLevel.LOW, "Read local date and time.")
        remember = self.REMEMBER_PATTERN.match(text)
        if remember:
            return PlannedTool("remember", RiskLevel.LOW, "User asked Damien to remember a durable fact.", {"value": remember.group("value")})
        if self.RECALL_PATTERN.search(text):
            return PlannedTool("recall_memory", RiskLevel.LOW, "User asked to inspect memory.")
        if self.FILE_SEARCH_PATTERN.search(text):
            return PlannedTool("search_approved_files", RiskLevel.LOW, "Search approved local files.", {"query": text})
        if self.WEB_PATTERN.search(text):
            return PlannedTool("web_search", RiskLevel.LOW, "Controlled web lookup.", {"query": text})
        if self.STATUS_PATTERN.search(text):
            return PlannedTool("system_status", RiskLevel.LOW, "Read local system status.")
        return None

    def execute(self, planned: PlannedTool) -> ToolResult:
        if planned.risk == RiskLevel.DENY:
            return ToolResult(planned.name, planned.risk, f"Denied: {planned.reason}", executed=False)
        if planned.risk == RiskLevel.CONFIRM:
            return ToolResult(
                planned.name,
                planned.risk,
                f"Confirmation required: {planned.reason}",
                executed=False,
                confirmation_required=True,
            )
        if planned.name == "open_approved_app":
            return ToolResult(planned.name, planned.risk, self.commands.try_handle_text(planned.args["text"]) or "No app action found.")
        if planned.name == "close_approved_app":
            return ToolResult(planned.name, planned.risk, self.commands.try_handle_text(planned.args["text"]) or "No app action found.")
        if planned.name == "capabilities":
            return ToolResult(planned.name, planned.risk, self._capabilities())
        if planned.name == "run_powershell":
            return ToolResult(planned.name, planned.risk, self._run_powershell(planned.args["command"]))
        if planned.name == "click_ui_button":
            return ToolResult(planned.name, planned.risk, self.convenience.click_ui_button(planned.args["label"]))
        if planned.name == "missing_ui_button_label":
            return ToolResult(planned.name, planned.risk, planned.reason)
        if planned.name == "cancel_powershell":
            message = "Cancelled the pending PowerShell command." if planned.args.get("had_pending") == "True" else "There was no pending PowerShell command."
            return ToolResult(planned.name, planned.risk, message)
        if planned.name == "no_pending_confirmation":
            return ToolResult(planned.name, planned.risk, planned.reason)
        if planned.name == "quick_mode":
            return ToolResult(planned.name, planned.risk, self._quick_mode(planned.args["mode"]))
        if planned.name == "media_control":
            return ToolResult(planned.name, planned.risk, self.convenience.media_control(planned.args["action"]))
        if planned.name == "mascot_ui_info":
            return ToolResult(
                planned.name,
                planned.risk,
                "The butler mascot is part of Damien's UI design, not a separate VPet launcher.",
            )
        if planned.name == "read_screen":
            return ToolResult(planned.name, planned.risk, self.convenience.read_screen())
        if planned.name == "safe_ui_click":
            return ToolResult(planned.name, planned.risk, self.convenience.safe_ui_click(planned.args["label"]))
        if planned.name == "take_me_to_lobby":
            app_name = planned.args.get("app_name")
            if app_name:
                return ToolResult(planned.name, planned.risk, self.convenience.take_me_to_lobby(app_name))
            return ToolResult(planned.name, planned.risk, self.convenience.take_me_to_lobby())
        if planned.name == "list_improvements":
            return ToolResult(planned.name, planned.risk, self.convenience.list_improvements())
        if planned.name == "prepare_latest_improvement_task":
            return ToolResult(planned.name, planned.risk, self.convenience.prepare_latest_improvement_task())
        if planned.name == "retry_latest_failed_command":
            return ToolResult(planned.name, planned.risk, self.convenience.retry_latest_failed_command())
        if planned.name == "discord_call":
            return ToolResult(planned.name, planned.risk, self.convenience.discord_call(planned.args["target"]))
        if planned.name == "discord_answer_call":
            return ToolResult(planned.name, planned.risk, self.convenience.discord_answer_call())
        if planned.name == "missing_discord_call_target":
            return ToolResult(planned.name, planned.risk, "Who should I call on Discord?")
        if planned.name == "open_editor_project":
            return ToolResult(
                planned.name,
                planned.risk,
                self.convenience.open_editor_project(planned.args["editor"], planned.args["project"]),
            )
        if planned.name == "missing_editor_project_name":
            return ToolResult(planned.name, planned.risk, f"Which {planned.args.get('editor', 'editor')} project should I open?")
        if planned.name == "open_roblox_game":
            return ToolResult(planned.name, planned.risk, self.convenience.open_roblox_game(planned.args["game"]))
        if planned.name == "missing_roblox_game_name":
            return ToolResult(planned.name, planned.risk, "Which Roblox game should I open?")
        if planned.name == "list_approved_apps":
            approved = ", ".join(sorted(self.commands.apps))
            return ToolResult(planned.name, planned.risk, f"Approved apps I can open: {approved}.")
        if planned.name == "open_web":
            return ToolResult(planned.name, planned.risk, self.convenience.open_web(planned.args["target"]))
        if planned.name == "crunchyroll_title":
            return ToolResult(planned.name, planned.risk, self.convenience.open_crunchyroll_title(planned.args["title"]))
        if planned.name == "set_crunchyroll_profile":
            return ToolResult(planned.name, planned.risk, self.convenience.set_crunchyroll_profile(planned.args["profile"]))
        if planned.name == "itunes_playlist":
            return ToolResult(
                planned.name,
                planned.risk,
                self.convenience.play_itunes_playlist(
                    planned.args["playlist"],
                    shuffle=planned.args.get("shuffle") == "true",
                ),
            )
        if planned.name == "missing_playlist_name":
            return ToolResult(planned.name, planned.risk, "Which iTunes playlist should I use?")
        if planned.name == "missing_crunchyroll_title":
            return ToolResult(planned.name, planned.risk, "Which Crunchyroll title should I open?")
        if planned.name == "copy_to_clipboard":
            return ToolResult(planned.name, planned.risk, self.convenience.copy_to_clipboard(planned.args["value"]))
        if planned.name == "add_note":
            return ToolResult(planned.name, planned.risk, self.convenience.add_note(planned.args["value"]))
        if planned.name == "list_notes":
            return ToolResult(planned.name, planned.risk, self.convenience.list_notes())
        if planned.name == "local_time":
            return ToolResult(planned.name, planned.risk, self.convenience.local_time())
        if planned.name == "open_project_area":
            return ToolResult(planned.name, planned.risk, self.convenience.open_project_area(planned.args["area"]))
        if planned.name == "remember":
            value = planned.args["value"].strip()
            if not self.memory.enabled:
                return ToolResult(
                    planned.name,
                    planned.risk,
                    "Memory is disabled. Enable long-term memory in settings before I store durable facts.",
                    executed=False,
                )
            self.memory.add(value, category="fact")
            return ToolResult(planned.name, planned.risk, f"Logged to memory: {value}")
        if planned.name == "recall_memory":
            memories = self.memory.list_memories()
            if not memories:
                return ToolResult(planned.name, planned.risk, "Memory is empty or disabled.")
            lines = [f"- [{memory.get('category', 'fact')}] {memory.get('content', '')}" for memory in memories[-10:]]
            return ToolResult(planned.name, planned.risk, "Inspectable memory:\n" + "\n".join(lines))
        if planned.name == "search_approved_files":
            results = self.retriever.search(planned.args["query"], limit=5)
            if not results:
                return ToolResult(planned.name, planned.risk, "I did not find matching approved local files.")
            return ToolResult(planned.name, planned.risk, "Approved file matches:\n" + "\n\n".join(results))
        if planned.name == "web_search":
            return ToolResult(planned.name, planned.risk, self._web_search(planned.args["query"]))
        if planned.name == "system_status":
            return ToolResult(planned.name, planned.risk, self._system_status())
        return ToolResult(planned.name, planned.risk, "No handler registered.", executed=False)

    def _run_powershell(self, command: str) -> str:
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                cwd=APP_ROOT,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            return "PowerShell stopped after the 60 second time limit."
        except OSError as exc:
            return f"PowerShell could not start: {exc}"
        output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
        if not output:
            output = "Command completed successfully with no output." if completed.returncode == 0 else "PowerShell returned no output."
        status = "completed" if completed.returncode == 0 else f"exited with code {completed.returncode}"
        return f"PowerShell {status}:\n{output[:12_000]}"

    def _capabilities(self) -> str:
        return (
            "I can listen for Hey Damien, open and close approved Desktop apps, search approved files, open websites, "
            "start Discord calls for people or group chats, control Crunchyroll title lookup with a saved profile, "
            "open Roblox games, open Unreal Engine and Roblox Studio projects, "
            "capture the screen on request, "
            "click approved low-risk UI buttons or click an exact visible button after confirmation, retry the last game lobby entry, "
            "run a specifically requested PowerShell command after showing it and requiring you to confirm it, "
            "queue missing abilities as Codex-ready self-improvement tasks, "
            "play or shuffle iTunes playlists, run anime/gaming/focus modes, "
            "read system status, take notes, copy text to clipboard, and answer through the local Ollama model."
        )

    def _quick_mode(self, mode: str) -> str:
        actions: list[str] = []
        if mode == "anime":
            actions.append(self.convenience.open_crunchyroll_title("One Piece"))
            discord = self.commands.open_approved_app("discord")
            if not discord.startswith("Denied:"):
                actions.append(discord)
        elif mode == "gaming":
            discord = self.commands.open_approved_app("discord")
            actions.append(discord)
            games = [name for name in self.commands.apps if any(token in name for token in ("game", "steam", "apex", "brawlhalla"))]
            if games:
                actions.append(self.commands.open_approved_app(games[0]))
        elif mode == "focus":
            chrome = self.commands.open_approved_app("chrome")
            actions.append(chrome)
            actions.append(self.convenience.open_project_area("documents"))
        else:
            return f"I do not have a {mode} mode yet."
        return f"{mode.title()} mode:\n" + "\n".join(actions)

    def _system_status(self) -> str:
        gpu = get_gpu_memory()
        parts = [f"OS: {platform.platform()}", f"CPU: {platform.processor() or 'unknown'}"]
        if gpu:
            parts.append(
                f"GPU: {gpu.get('name', 'Unavailable')}, "
                f"{gpu.get('used_mb', '0')}/{gpu.get('total_mb', '0')} MB VRAM used"
            )
        return "System status:\n" + "\n".join(parts)

    def _web_search(self, query: str) -> str:
        if os.environ.get("DAMIEN_DISABLE_WEB_TOOLS") == "1":
            return "Web tools are disabled by environment policy."
        cleaned = re.sub(r"\b(search the web|look up online|web|internet|online)\b", " ", query, flags=re.IGNORECASE).strip()
        url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(cleaned or query)
        request = urllib.request.Request(url, headers={"User-Agent": "DamienAssistant/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                html = response.read(200_000).decode("utf-8", errors="ignore")
        except Exception as exc:
            return f"Web search failed: {exc}"
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL)
        lines = []
        for index, title in enumerate(titles[:3]):
            title = _strip_html(title)
            snippet = _strip_html(snippets[index]) if index < len(snippets) else ""
            lines.append(f"{index + 1}. {title}" + (f" - {snippet}" if snippet else ""))
        return "Web results:\n" + "\n".join(lines) if lines else "No web results were found."


def _strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'")
    return re.sub(r"\s+", " ", value).strip()


def _strip_confirmation_command_prefix(value: str) -> str:
    match = re.match(
        r"^\s*(?:yes|yeah|yep|sure|ok|okay|correct|right)(?:[.!?,]+|\s+)(?:\s*(?:and|then)\s+)?(?P<command>.+?)\s*$",
        value,
        re.IGNORECASE,
    )
    return match.group("command") if match else value


def _clean_playlist_name(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:called|named|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:on|in)\s+(?:itunes|music)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if cleaned.casefold() in {"playlist", "another playlist", "another"}:
        return ""
    return cleaned


def _clean_crunchyroll_title(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:the|my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:on|in)\s+crunchyroll$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if cleaned.casefold() in {"watching", "anime", "show", "episode", "series", "it", "that", "this", "another"}:
        return ""
    return cleaned


def _clean_discord_call_target(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:with|to|the)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:on|in)\s+discord$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if cleaned.casefold() in {"", "someone", "person", "people", "dm"}:
        return ""
    return cleaned


def _clean_editor_project_name(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:project|place|game|called|named|the|my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:project|place|game)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def _clean_roblox_game_name(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:game|experience|called|named|the|my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:game|experience)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def _looks_like_tool_command(value: str) -> bool:
    return bool(re.search(r"\b(clipboard|note|notes|documents?|files?|apps?|settings|folder)\b", value, re.IGNORECASE))
