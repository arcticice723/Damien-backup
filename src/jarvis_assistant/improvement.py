from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .runtime import APP_ROOT

RepairRunner = Callable[[list[str], Path, Path], object]


class SelfRepairManager:
    def __init__(self, root: Path = APP_ROOT, runner: RepairRunner | None = None, codex_command: str | None = None) -> None:
        self.root = root
        self.workspace = _repair_workspace(root)
        self.runner = runner or _start_background_repair
        self.codex_command = codex_command or _codex_command()
        self.log_path = root / "logs" / "self_repair.jsonl"

    def request_repair(self, record: dict[str, str], task_path: Path) -> bool:
        fingerprint = _repair_fingerprint(record)
        if self._has_started(fingerprint):
            return False
        transcript_path = self.root / "logs" / "self_repair_processes" / f"{fingerprint or 'repair'}.log"
        prompt_path = self.root / "logs" / "self_repair_prompts" / f"{fingerprint or 'repair'}.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(_repair_prompt(record, task_path), encoding="utf-8")
        prompt = _repair_prompt_argument(record, prompt_path)
        command = _repair_command(
            self.codex_command,
            [
                "exec",
                "--cd",
                str(self.workspace),
                "--sandbox",
                "danger-full-access",
                prompt,
            ],
        )
        self._log(record, task_path, fingerprint, "starting", transcript_path)
        try:
            self.runner(command, self.workspace, transcript_path)
        except Exception as exc:
            self._log(record, task_path, fingerprint, f"failed_to_start: {exc}", transcript_path)
            return False
        self._log(record, task_path, fingerprint, "started", transcript_path)
        return True

    def _has_started(self, fingerprint: str) -> bool:
        if not self.log_path.exists():
            return False
        latest_status = ""
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("fingerprint") == fingerprint:
                latest_status = str(record.get("status") or "")
        return latest_status in {"starting", "started"}

    def _log(self, record: dict[str, str], task_path: Path, fingerprint: str, status: str, transcript_path: Path) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "request": str(record.get("request", "")),
            "task_path": str(task_path),
            "transcript_path": str(transcript_path),
            "status": status,
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=True) + "\n")


class ImprovementQueue:
    def __init__(self, root: Path = APP_ROOT, repair_manager: SelfRepairManager | None = None) -> None:
        self.root = root
        self.path = root / "logs" / "improvement_queue.jsonl"
        self.tasks_dir = root / "improvement_tasks"
        self.repair_manager = repair_manager
        if self.repair_manager is None and _same_path(root, APP_ROOT):
            self.repair_manager = SelfRepairManager(root)

    def log(self, request: str, reason: str, suggestion: str) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request": request.strip(),
            "reason": reason.strip(),
            "suggestion": suggestion.strip(),
            "status": "queued_for_codex",
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=True) + "\n")
        task_path = self.prepare_task(record)
        if self.repair_manager is not None:
            return self.repair_manager.request_repair(record, task_path)
        return False

    def records(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append({str(key): str(value) for key, value in record.items()})
        return records

    def latest(self) -> dict[str, str] | None:
        records = self.records()
        return records[-1] if records else None

    def latest_repair_status(self) -> str:
        record = self.latest()
        if record is None:
            return ""
        fingerprint = _repair_fingerprint(record)
        if not fingerprint:
            return ""
        repair_log = self.root / "logs" / "self_repair.jsonl"
        if not repair_log.exists():
            return ""
        latest_status = ""
        for line in repair_log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(payload.get("fingerprint", "")) == fingerprint:
                latest_status = str(payload.get("status", ""))
        return latest_status

    def latest_repair_summary(self) -> str:
        notes_path = self.root / "logs" / "self_repair_notes.md"
        if not notes_path.exists():
            return ""
        try:
            lines = notes_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""
        for line in reversed(lines):
            clean = line.strip()
            if not clean:
                continue
            match = re.match(r"^-\s*Change:\s*(?P<summary>.+)$", clean, flags=re.IGNORECASE)
            if match:
                return match.group("summary").strip()
        return ""

    def summary(self, limit: int = 5) -> str:
        records = self.records()
        if not records:
            return "No queued Damien upgrades yet."
        lines = ["Queued Damien upgrades:"]
        for index, record in enumerate(records[-limit:], start=1):
            lines.append(
                f"{index}. {record.get('request', '').strip()} - {record.get('suggestion', '').strip()}"
            )
        return "\n".join(lines)

    def prepare_latest_task(self) -> Path:
        record = self.latest()
        if record is None:
            raise RuntimeError("No failed command is queued for a Codex upgrade yet.")
        return self.prepare_task(record)

    def prepare_task(self, record: dict[str, str]) -> Path:
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        stamp = _task_stamp(str(record.get("created_at", "")))
        path = self.tasks_dir / f"{stamp}-damien-upgrade.md"
        path.write_text(_task_markdown(record), encoding="utf-8")
        return path

    def retry_latest_message(self) -> str:
        record = self.latest()
        if record is None:
            return "No failed command is queued to retry yet."
        return (
            "The last failed command still needs an upgrade before retrying: "
            f"{record.get('request', '').strip()}"
        )


def build_missing_capability_response(request: str, queue: ImprovementQueue, suggestion: str) -> str:
    repair_started = queue.log(
        request=request,
        reason="Damien did not have a concrete local tool for this request.",
        suggestion=suggestion,
    )
    if repair_started:
        return (
            "I don't have that wired in yet, so I started a Codex repair for it now. "
            f"Upgrade target: {suggestion}"
        )
    return (
        "I don't have that wired in yet. "
        f"I logged it as an upgrade for Codex: {suggestion}"
    )


class UpgradeIntentHandler:
    def __init__(
        self,
        queue: ImprovementQueue,
        suggestion: str = "Add or improve the Damien tool that handles this request.",
    ) -> None:
        self.queue = queue
        self.suggestion = suggestion

    def handle(self, text: str) -> str | None:
        if not (
            looks_like_missing_capability_request(text)
            or looks_like_assistant_benchmark_complaint(text)
            or looks_like_unsupported_action_request(text)
        ):
            return None
        return build_missing_capability_response(text, self.queue, self.suggestion)


def looks_like_missing_capability_request(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    has_damien = "damien" in normalized
    asks_for_upgrade = re.search(r"\b(should|supposed to|needs? to|add|upgrade|improve|wire|integrate)\b", normalized)
    mentions_capability = re.search(
        r"\b(ability|capability|access|control|operate|click|screen|ui|codex|help|self|itself)\b",
        normalized,
    )
    return bool(has_damien and asks_for_upgrade and mentions_capability)


def looks_like_assistant_benchmark_complaint(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if not normalized:
        return False
    mentions_assistant_standard = re.search(r"\b(siri|cortana|jarvis|alexa|google assistant)\b", normalized)
    points_at_this_assistant = re.search(
        r"\b(this|it|you|assistant|damien)\b.*\b(should|supposed to|why|where|there yet|better|improve|automatic|accurate)\b",
        normalized,
    )
    mentions_core_behavior = re.search(
        r"\b(self improvement|self-improvement|speech to text|stt|voice|automatic|automatically|accurate|proactive)\b",
        normalized,
    )
    return bool(mentions_assistant_standard and (points_at_this_assistant or mentions_core_behavior))


def looks_like_unsupported_action_request(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if not normalized:
        return False
    if re.match(r"^(?:what|why|how|who|where|when|tell me|explain|describe|chat|talk)\b", normalized):
        return False
    asks_for_action = re.search(
        r"\b("
        r"turn\s+(?:on|off)|switch\s+(?:on|off)|set|change|adjust|raise|lower|mute|unmute|"
        r"connect|disconnect|control|operate|click|press|tap|start|stop|resume|pause|"
        r"launch|open|close|send|make|create|schedule"
        r")\b",
        normalized,
    )
    mentions_pc_or_device_target = re.search(
        r"\b("
        r"my\s+)?("
        r"pc|computer|laptop|desktop|screen|window|app|program|browser|tab|device|phone|"
        r"lights?|lamp|thermostat|camera|speaker|headphones|volume|video|music|discord|game|"
        r"calendar|email|message|file|folder"
        r")\b",
        normalized,
    )
    return bool(asks_for_action and mentions_pc_or_device_target)


def is_generic_windows_assistant_response(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return bool(
        "as a windows desktop assistant" in normalized
        or "i can provide information and answer questions about" in normalized
        or ("windows basics" in normalized and "troubleshooting" in normalized and "file management" in normalized)
    )


def _task_stamp(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-")
    return cleaned[:32] or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _task_markdown(record: dict[str, str]) -> str:
    return (
        "# Damien Upgrade Task\n\n"
        "## User Request\n"
        f"{record.get('request', '').strip()}\n\n"
        "## What Failed\n"
        f"{record.get('reason', '').strip()}\n\n"
        "## Suggested Upgrade\n"
        f"{record.get('suggestion', '').strip()}\n\n"
        "## Implementation Notes\n"
        "- Add or update a focused Damien tool/routine for this request.\n"
        "- Add tests that prove the command routes correctly and handles failure clearly.\n"
        "- Keep destructive actions blocked unless the user explicitly approves them.\n"
        "- Rebuild and restart Damien after the upgrade.\n"
    )


def _repair_fingerprint(record: dict[str, str]) -> str:
    value = "\n".join(
        [
            str(record.get("request", "")).strip().casefold(),
            str(record.get("reason", "")).strip().casefold(),
            str(record.get("suggestion", "")).strip().casefold(),
        ]
    )
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:120]


def _repair_prompt(record: dict[str, str], task_path: Path) -> str:
    return (
        "Damien failed a user request and must improve itself immediately.\n\n"
        f"Task file: {task_path}\n"
        f"User request: {record.get('request', '').strip()}\n"
        f"What failed: {record.get('reason', '').strip()}\n"
        f"Suggested upgrade: {record.get('suggestion', '').strip()}\n\n"
        "Act as Codex inside this Damien repo. Investigate the relevant code and logs, add failing tests first, "
        "implement the smallest focused fix, run the focused tests and then the full test suite if feasible. "
        "Do not delete files, wipe data, reset git, or make destructive changes. "
        "If tests pass and the app needs packaging, rebuild Damien. "
        "Leave a concise note in logs/self_repair_notes.md describing what changed or why repair was blocked."
    )


def _repair_prompt_argument(record: dict[str, str], prompt_path: Path) -> str:
    request = re.sub(r"\s+", " ", str(record.get("request", "")).strip())
    request_text = f" for: {request}" if request else ""
    return f"Damien failed a user request{request_text}. Read and execute the repair prompt file: {prompt_path}"


def _start_background_repair(command: list[str], cwd: Path, transcript_path: Path) -> subprocess.Popen:
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript = transcript_path.open("ab")
    try:
        return subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=transcript,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        transcript.close()


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.absolute() == right.absolute()


def _repair_workspace(root: Path) -> Path:
    candidates = [root, *root.parents]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (candidate / "src").exists():
            return candidate
    return root


def _codex_command() -> str:
    if os.name == "nt":
        for name in ("codex.cmd", "codex.bat"):
            path = shutil.which(name)
            if path:
                return path
        return "codex"
    for name in ("codex.exe", "codex.cmd", "codex.bat", "codex"):
        path = shutil.which(name)
        if path:
            return path
    return "codex"


def _repair_command(codex_command: str, args: list[str]) -> list[str]:
    if os.name == "nt" and codex_command.lower() == "codex":
        return ["cmd.exe", "/d", "/s", "/c", codex_command, *args]
    return [codex_command, *args]
