from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from ..improvement import ImprovementQueue
from .notes import NoteStore
from .reminders import ReminderStore


@dataclass(frozen=True)
class ProactiveNotice:
    id: str
    message: str
    reason: str


@dataclass(frozen=True)
class UnfinishedTaskRecord:
    id: str
    created_at: str
    title: str
    detail: str
    status: str = "open"
    completed_at: str = ""


class UnfinishedTaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def add(self, title: str, detail: str) -> UnfinishedTaskRecord:
        clean_title = title.strip()
        clean_detail = detail.strip()
        if not clean_title:
            raise ValueError("unfinished task title is required")
        existing = self._matching_open_task(clean_title, clean_detail)
        if existing is not None:
            return existing
        record = UnfinishedTaskRecord(
            id=uuid.uuid4().hex[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            title=clean_title,
            detail=clean_detail,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.__dict__, ensure_ascii=True) + "\n")
        return record

    def complete_latest(self) -> UnfinishedTaskRecord | None:
        records = self._read_all()
        latest = next((record for record in reversed(records) if record.status == "open"), None)
        if latest is None:
            return None
        completed = UnfinishedTaskRecord(
            id=latest.id,
            created_at=latest.created_at,
            title=latest.title,
            detail=latest.detail,
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._write_all([completed if record.id == latest.id else record for record in records])
        return completed

    def reopen(self, task_id: str) -> UnfinishedTaskRecord | None:
        records = self._read_all()
        restored: UnfinishedTaskRecord | None = None
        updated: list[UnfinishedTaskRecord] = []
        for record in records:
            if record.id == task_id and record.status == "completed":
                restored = UnfinishedTaskRecord(
                    id=record.id,
                    created_at=record.created_at,
                    title=record.title,
                    detail=record.detail,
                )
                updated.append(restored)
            else:
                updated.append(record)
        if restored is not None:
            self._write_all(updated)
        return restored

    def open(self) -> list[UnfinishedTaskRecord]:
        return [record for record in self._read_all() if record.status == "open"]

    def summary(self, limit: int = 5) -> str:
        records = self.open()
        if not records:
            return "No unfinished tasks."
        lines = ["Unfinished tasks:"]
        for index, record in enumerate(records[-limit:], start=1):
            detail = f" - {record.detail}" if record.detail else ""
            lines.append(f"{index}. {record.title}{detail}")
        return "\n".join(lines)

    def _read_all(self) -> list[UnfinishedTaskRecord]:
        if not self.path.exists():
            return []
        records: list[UnfinishedTaskRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            title = str(payload.get("title", "")).strip()
            if not title:
                continue
            records.append(
                UnfinishedTaskRecord(
                    id=str(payload.get("id", "")),
                    created_at=str(payload.get("created_at", "")),
                    title=title,
                    detail=str(payload.get("detail", "")).strip(),
                    status=str(payload.get("status", "open")),
                    completed_at=str(payload.get("completed_at", "")),
                )
            )
        return records

    def _write_all(self, records: list[UnfinishedTaskRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record.__dict__, ensure_ascii=True) + "\n")

    def _matching_open_task(self, title: str, detail: str) -> UnfinishedTaskRecord | None:
        wanted_title = _normalized_task_text(title)
        wanted_detail = _normalized_task_text(detail)
        for record in self.open():
            if _normalized_task_text(record.title) == wanted_title and _normalized_task_text(record.detail) == wanted_detail:
                return record
        return None


class ProactiveEngine:
    def __init__(
        self,
        reminders: ReminderStore,
        state_path: Path,
        improvements: ImprovementQueue | None = None,
        unfinished_tasks: UnfinishedTaskStore | None = None,
        notes: NoteStore | None = None,
        audit_path: Path | None = None,
        notice_allowed: Callable[[ProactiveNotice], bool] | None = None,
    ) -> None:
        self.reminders = reminders
        self.state_path = state_path
        self.improvements = improvements
        self.unfinished_tasks = unfinished_tasks
        self.notes = notes
        self.audit_path = audit_path
        self.notice_allowed = notice_allowed or (lambda _notice: True)

    def check(self, now: datetime) -> list[ProactiveNotice]:
        state = self._read_state()
        quiet_until = state.get("quiet_until", "")
        if quiet_until:
            try:
                if datetime.fromisoformat(str(quiet_until)) > _ensure_timezone(now):
                    return []
            except ValueError:
                pass
        delivered = set(state.get("delivered", []))
        notices: list[ProactiveNotice] = []
        for reminder in self.reminders.due(now):
            notice_id = f"reminder:{reminder.id}"
            if self._is_snoozed(notice_id, state, now):
                continue
            if self._is_dismissed(notice_id, state):
                continue
            if notice_id in delivered:
                continue
            notice = ProactiveNotice(notice_id, f"Reminder: {reminder.message}", "due_reminder")
            if not self._notice_allowed(notice):
                continue
            notices.append(notice)
            delivered.add(notice_id)
        if self.improvements is not None:
            latest = self.improvements.latest()
            if latest is not None:
                suggestion = latest.get("suggestion", "").strip()
                created_at = latest.get("created_at", "").strip()
                notice_id = f"improvement:{created_at}:{suggestion}"
                if (
                    suggestion
                    and not self._is_snoozed(notice_id, state, now)
                    and not self._is_dismissed(notice_id, state)
                ):
                    repair_status = self.improvements.latest_repair_status()
                    if repair_status == "completed":
                        finished_notice_id = f"repair-finished:{created_at}:{suggestion}"
                        if (
                            finished_notice_id not in delivered
                            and not self._is_snoozed(finished_notice_id, state, now)
                            and not self._is_dismissed(finished_notice_id, state)
                        ):
                            summary = self.improvements.latest_repair_summary() or suggestion
                            notice = ProactiveNotice(
                                finished_notice_id,
                                f"Repair finished: {summary}",
                                "self_repair_finished",
                            )
                            if self._notice_allowed(notice):
                                notices.append(notice)
                                delivered.add(finished_notice_id)
                    elif repair_status == "started" and notice_id not in delivered:
                        notice = ProactiveNotice(notice_id, f"Repair started: {suggestion}", "self_repair_started")
                        if self._notice_allowed(notice):
                            notices.append(notice)
                            delivered.add(notice_id)
                    elif notice_id not in delivered:
                        notice = ProactiveNotice(notice_id, f"Opportunity: {suggestion}", "upgrade_opportunity")
                        if self._notice_allowed(notice):
                            notices.append(notice)
                            delivered.add(notice_id)
        if self.unfinished_tasks is not None:
            for task in self.unfinished_tasks.open():
                notice_id = f"unfinished:{task.id}"
                if self._is_snoozed(notice_id, state, now):
                    continue
                if self._is_dismissed(notice_id, state):
                    continue
                if notice_id in delivered:
                    continue
                detail = f" - {task.detail}" if task.detail else ""
                notice = ProactiveNotice(notice_id, f"Unfinished: {task.title}{detail}", "unfinished_task")
                if not self._notice_allowed(notice):
                    continue
                notices.append(notice)
                delivered.add(notice_id)
        if self.notes is not None:
            for note in self.notes.list_recent(limit=20):
                notice_id = f"note:{note.id}"
                if self._is_snoozed(notice_id, state, now):
                    continue
                if self._is_dismissed(notice_id, state):
                    continue
                if notice_id in delivered:
                    continue
                if not is_time_sensitive_note(note.content):
                    continue
                notice = ProactiveNotice(notice_id, f"Heads up: {note.content}", "saved_note_opportunity")
                if not self._notice_allowed(notice):
                    continue
                notices.append(notice)
                delivered.add(notice_id)
        routine_notice = self._latest_repeated_routine_notice()
        if (
            routine_notice is not None
            and routine_notice.id not in delivered
            and not self._is_snoozed(routine_notice.id, state, now)
            and not self._is_dismissed(routine_notice.id, state)
        ):
            if self._notice_allowed(routine_notice):
                notices.append(routine_notice)
                delivered.add(routine_notice.id)
        if notices:
            state["delivered"] = sorted(delivered)
            self._write_state(state)
        return notices

    def latest_upgrade_notice_id(self) -> str | None:
        if self.improvements is None:
            return None
        latest = self.improvements.latest()
        if latest is None:
            return None
        suggestion = latest.get("suggestion", "").strip()
        created_at = latest.get("created_at", "").strip()
        if not suggestion:
            return None
        return f"improvement:{created_at}:{suggestion}"

    def latest_due_reminder_notice_id(self, now: datetime) -> str | None:
        due = self.reminders.due(now)
        for reminder in due:
            notice_id = f"reminder:{reminder.id}"
            if not self.is_dismissed(notice_id):
                return notice_id
        return None

    def latest_unfinished_notice_id(self) -> str | None:
        if self.unfinished_tasks is None:
            return None
        for task in reversed(self.unfinished_tasks.open()):
            notice_id = f"unfinished:{task.id}"
            if not self.is_dismissed(notice_id):
                return notice_id
        return None

    def latest_note_notice_id(self) -> str | None:
        if self.notes is None:
            return None
        for note in reversed(self.notes.list_recent(limit=20)):
            notice_id = f"note:{note.id}"
            if is_time_sensitive_note(note.content) and not self.is_dismissed(notice_id):
                return notice_id
        return None

    def latest_routine(self) -> tuple[str, str] | None:
        notice = self._latest_repeated_routine_notice()
        if notice is None:
            return None
        if self.is_dismissed(notice.id):
            return None
        label = _routine_label_from_message(notice.message)
        if not label:
            return None
        return notice.id, label

    def accept_routine(self, notice_id: str, label: str) -> None:
        state = self._read_state()
        accepted = state.get("accepted_routines", [])
        if not isinstance(accepted, list):
            accepted = []
        record = {"id": notice_id, "label": label}
        existing_ids = {
            str(item.get("id", ""))
            for item in accepted
            if isinstance(item, dict)
        }
        if notice_id not in existing_ids:
            accepted.append(record)
        state["accepted_routines"] = accepted
        self._write_state(state)

    def latest_accepted_routine_label(self) -> str | None:
        accepted = self._read_state().get("accepted_routines", [])
        if not isinstance(accepted, list):
            return None
        for item in reversed(accepted):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            if label:
                return label
        return None

    def accepted_routines_summary(self, limit: int = 5) -> str:
        accepted = self._read_state().get("accepted_routines", [])
        if not isinstance(accepted, list):
            return "No saved routines."
        labels: list[str] = []
        for item in accepted:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            if label:
                labels.append(label)
        if not labels:
            return "No saved routines."
        lines = ["Saved routines:"]
        for index, label in enumerate(labels[-limit:], start=1):
            lines.append(f"{index}. {label}")
        return "\n".join(lines)

    def forget_accepted_routine(self, number: int) -> str | None:
        if number < 1:
            return None
        state = self._read_state()
        accepted = state.get("accepted_routines", [])
        if not isinstance(accepted, list):
            return None
        valid_records = [item for item in accepted if isinstance(item, dict) and str(item.get("label", "")).strip()]
        index = number - 1
        if index >= len(valid_records):
            return None
        removed = valid_records.pop(index)
        state["accepted_routines"] = valid_records
        self._write_state(state)
        return str(removed.get("label", "")).strip()

    def quiet_for(self, duration: timedelta, now: datetime | None = None) -> datetime:
        current = _ensure_timezone(now or datetime.now(timezone.utc))
        quiet_until = current + duration
        state = self._read_state()
        state["quiet_until"] = quiet_until.isoformat()
        self._write_state(state)
        return quiet_until

    def active_quiet_until(self, now: datetime | None = None) -> datetime | None:
        quiet_until = self._read_state().get("quiet_until", "")
        if not quiet_until:
            return None
        try:
            until = _ensure_timezone(datetime.fromisoformat(str(quiet_until)))
        except ValueError:
            return None
        current = _ensure_timezone(now or datetime.now(timezone.utc))
        if until <= current:
            return None
        return until

    def resume_notices(self) -> None:
        state = self._read_state()
        state["quiet_until"] = ""
        self._write_state(state)

    def dismiss(self, notice_id: str) -> None:
        state = self._read_state()
        delivered = set(state.get("delivered", []))
        delivered.add(notice_id)
        state["delivered"] = sorted(delivered)
        dismissed = set(state.get("dismissed", []))
        dismissed.add(notice_id)
        state["dismissed"] = sorted(dismissed)
        self._write_state(state)

    def restore_notice(self, notice_id: str) -> None:
        state = self._read_state()
        delivered = set(state.get("delivered", []))
        delivered.discard(notice_id)
        state["delivered"] = sorted(delivered)
        dismissed = set(state.get("dismissed", []))
        dismissed.discard(notice_id)
        state["dismissed"] = sorted(dismissed)
        self._write_state(state)

    def is_delivered(self, notice_id: str) -> bool:
        delivered = self._read_state().get("delivered", [])
        if not isinstance(delivered, list):
            return False
        return notice_id in {str(item) for item in delivered}

    def is_dismissed(self, notice_id: str) -> bool:
        return self._is_dismissed(notice_id, self._read_state())

    def snooze(self, notice_id: str, duration: timedelta, now: datetime | None = None) -> datetime:
        current = _ensure_timezone(now or datetime.now(timezone.utc))
        snoozed_until = current + duration
        state = self._read_state()
        delivered = set(state.get("delivered", []))
        delivered.discard(notice_id)
        state["delivered"] = sorted(delivered)
        snoozed = state.get("snoozed", {})
        if not isinstance(snoozed, dict):
            snoozed = {}
        snoozed[notice_id] = snoozed_until.isoformat()
        state["snoozed"] = snoozed
        self._write_state(state)
        return snoozed_until

    def _read_state(self) -> dict[str, object]:
        if not self.state_path.exists():
            return {"delivered": []}
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"delivered": []}
        if not isinstance(payload, dict):
            return {"delivered": []}
        if not isinstance(payload.get("delivered"), list):
            payload["delivered"] = []
        if "dismissed" in payload and not isinstance(payload.get("dismissed"), list):
            payload["dismissed"] = []
        return payload

    def _write_state(self, state: dict[str, object]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def _is_snoozed(self, notice_id: str, state: dict[str, object], now: datetime) -> bool:
        snoozed = state.get("snoozed", {})
        if not isinstance(snoozed, dict):
            return False
        raw_until = snoozed.get(notice_id)
        if not raw_until:
            return False
        try:
            return datetime.fromisoformat(str(raw_until)) > _ensure_timezone(now)
        except ValueError:
            return False

    def _is_dismissed(self, notice_id: str, state: dict[str, object]) -> bool:
        dismissed = state.get("dismissed", [])
        if not isinstance(dismissed, list):
            return False
        return notice_id in {str(item) for item in dismissed}

    def _notice_allowed(self, notice: ProactiveNotice) -> bool:
        try:
            return self.notice_allowed(notice)
        except Exception:
            return False

    def _latest_repeated_routine_notice(self) -> ProactiveNotice | None:
        if self.audit_path is None or not self.audit_path.exists():
            return None
        counts: Counter[str] = Counter()
        labels: dict[str, str] = {}
        latest_index: dict[str, int] = {}
        try:
            lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            tools_called = payload.get("tools_called", [])
            if not isinstance(tools_called, list) or not tools_called:
                continue
            outcome = str(payload.get("outcome", "")).strip().casefold()
            if outcome.startswith("denied") or "confirmation required" in outcome:
                continue
            label = re.sub(r"\s+", " ", str(payload.get("user_request", "")).strip())
            key = label.casefold()
            if not key:
                continue
            counts[key] += 1
            labels[key] = label
            latest_index[key] = index
        repeated = [key for key, count in counts.items() if count >= 3]
        if not repeated:
            return None
        key = max(repeated, key=lambda value: latest_index[value])
        notice_id = f"routine:{uuid.uuid5(uuid.NAMESPACE_URL, key).hex[:12]}"
        return ProactiveNotice(
            notice_id,
            f"Routine: You often ask me to {labels[key]}. I can help make that quicker.",
            "repeated_routine",
        )


class ProactiveControlHandler:
    def __init__(self, proactive: ProactiveEngine, now: Callable[[], datetime] | None = None) -> None:
        self.proactive = proactive
        self.now = now

    def handle(self, text: str) -> str | None:
        relative_snooze = re.match(
            r"^\s*remind\s+me\s+(?:about\s+(?:that|this|it)\s+)?in\s+(?P<count>\d+)\s+(?P<unit>minutes?|hours?)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if relative_snooze:
            now = self._current_time()
            notice_id = self._latest_snoozable_notice_id(now)
            if notice_id is not None:
                count = int(relative_snooze.group("count"))
                unit = relative_snooze.group("unit").lower()
                duration = timedelta(hours=count) if unit.startswith("hour") else timedelta(minutes=count)
                self.proactive.snooze(notice_id, duration, now)
                return _snooze_response(count, unit)

        if re.match(
            r"^\s*(?:not\s+now|give\s+me\s+a\s+bit|remind\s+me\s+(?:about\s+(?:that|this|it)\s+)?later|snooze\s+(?:that|this|it))\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            now = self._current_time()
            notice_id = self._latest_snoozable_notice_id(now)
            if notice_id is None:
                return None
            self.proactive.snooze(notice_id, timedelta(minutes=30), now)
            return "I will remind you later."

        if re.match(
            r"^\s*(?:what(?:'s| is)|show|list|read)\s+(?:still\s+)?unfinished(?:\s+tasks?)?\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            if self.proactive.unfinished_tasks is None:
                return "No unfinished tasks."
            return self.proactive.unfinished_tasks.summary()

        if re.match(
            r"^\s*(?:stop\s+reminding\s+me\s+about|do\s+not\s+remind\s+me\s+about|don't\s+remind\s+me\s+about)\s+(?:that|it)\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            notice_id = self._latest_dismissable_notice_id(self._current_time())
            if notice_id is None:
                return "No reminder is waiting right now."
            self.proactive.dismiss(notice_id)
            return "I will stop reminding you about that."

        if re.match(r"^\s*(?:dismiss|ignore|clear|drop)\s+(?:that|it)\s*$", text, flags=re.IGNORECASE):
            notice_id = self._latest_dismissable_notice_id(self._current_time())
            if notice_id is not None:
                self.proactive.dismiss(notice_id)
                return "Dismissed that."

        if re.match(
            r"^\s*(?:clear|complete|dismiss)\s+(?:that\s+|the\s+|latest\s+)?unfinished\s+task\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            if self.proactive.unfinished_tasks is None:
                return "No unfinished task is waiting right now."
            completed = self.proactive.unfinished_tasks.complete_latest()
            if completed is None:
                return "No unfinished task is waiting right now."
            self.proactive.dismiss(f"unfinished:{completed.id}")
            return f"Cleared unfinished task: {completed.title}"

        if re.match(
            r"^\s*(?:what|show|list|read)\s+(?:saved\s+|remembered\s+)?routines\s*(?:do\s+you\s+remember)?\s*$|^\s*what\s+routines\s+do\s+you\s+remember\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            return self.proactive.accepted_routines_summary()

        forget_routine = re.match(
            r"^\s*(?:forget|remove|delete)\s+(?:saved\s+|remembered\s+)?routine\s+(?P<number>\d+)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if forget_routine:
            label = self.proactive.forget_accepted_routine(int(forget_routine.group("number")))
            if label is None:
                return "No saved routine matches that number."
            return f"Forgot saved routine: {label}"

        if re.match(
            r"^\s*(?:yes|yeah|yep|sure|ok(?:ay)?)\s+(?:make\s+that\s+quicker|do\s+that|remember\s+that\s+routine)\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            routine = self.proactive.latest_routine()
            if routine is None:
                return "No routine suggestion is waiting right now."
            notice_id, label = routine
            self.proactive.accept_routine(notice_id, label)
            return "I will remember that routine."

        if re.match(r"^\s*(?:stop\s+suggesting|do\s+not\s+suggest|don't\s+suggest)\s+(?:that|it)\s*$", text, flags=re.IGNORECASE):
            notice_id = self._latest_suggestion_notice_id()
            if notice_id is None:
                return "No suggestion is waiting right now."
            self.proactive.dismiss(notice_id)
            return "I will stop suggesting that."

        if re.match(
            r"^\s*(?:dismiss|ignore|clear)\s+(?:that\s+|the\s+|latest\s+)?(?:upgrade\s+)?opportunit(?:y|ies)\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            notice_id = self.proactive.latest_upgrade_notice_id()
            if notice_id is None:
                return "No upgrade opportunity is waiting right now."
            self.proactive.dismiss(notice_id)
            return "Dismissed that upgrade opportunity."

        if re.match(
            r"^\s*(?:are\s+you\s+(?:in\s+)?quiet\s+mode|are\s+you\s+staying\s+quiet|are\s+you\s+quiet|can\s+you\s+speak\s+up|are\s+you\s+watching\s+out(?:\s+for\s+me)?|are\s+you\s+keeping\s+an?\s+eye\s+out(?:\s+for\s+me)?)\??\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            now = self._current_time()
            quiet_until = self.proactive.active_quiet_until(now)
            if quiet_until is None:
                return "I am ready to speak up."
            quiet_until = quiet_until.astimezone(now.tzinfo or timezone.utc)
            return f"I am staying quiet until {quiet_until.strftime('%I:%M %p')}."

        if re.match(
            r"^\s*(?:you\s+can\s+speak\s+up\s+again|you\s+don'?t\s+need\s+to\s+be\s+quiet\s+anymore|speak\s+up\s+again|resume\s+(?:proactive\s+)?(?:notices|suggestions)|turn\s+quiet\s+mode\s+off)\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            self.proactive.resume_notices()
            return "I can speak up again."

        if re.match(
            r"^\s*(?:(?:can\s+you\s+)?hold\s+off|(?:can\s+you\s+)?give\s+me\s+some\s+space)\s+for\s+a\s+bit\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            self.proactive.quiet_for(timedelta(minutes=30), self._current_time())
            return "I will stay quiet for 30 minutes."

        quiet = re.match(
            r"^\s*(?:(?:can\s+you\s+)?(?:be quiet|stop talking|give me some space|hold off)|quiet mode)\s+for\s+(?:(?P<count>\d+|one)\s+|an?\s+)?(?P<unit>minutes?|hours?)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if not quiet:
            return None
        raw_count = (quiet.group("count") or "one").lower()
        count = 1 if raw_count == "one" else int(raw_count)
        unit = quiet.group("unit").lower()
        duration = timedelta(hours=count) if unit.startswith("hour") else timedelta(minutes=count)
        self.proactive.quiet_for(duration, self._current_time())
        if unit.startswith("hour") and count == 1:
            return "I will stay quiet for an hour."
        if unit.startswith("minute") and count == 1:
            return "I will stay quiet for one minute."
        return f"I will stay quiet for {count} {unit}."

    def _current_time(self) -> datetime:
        if self.now is not None:
            return _ensure_timezone(self.now())
        return datetime.now(timezone.utc)

    def _latest_snoozable_notice_id(self, now: datetime) -> str | None:
        notice_id = self.proactive.latest_due_reminder_notice_id(now)
        if notice_id is not None:
            return notice_id
        notice_id = self.proactive.latest_unfinished_notice_id()
        if notice_id is not None:
            return notice_id
        notice_id = self.proactive.latest_note_notice_id()
        if notice_id is not None:
            return notice_id
        routine = self.proactive.latest_routine()
        if routine is not None:
            return routine[0]
        notice_id = self.proactive.latest_upgrade_notice_id()
        if notice_id is not None:
            return notice_id
        return None

    def _latest_dismissable_notice_id(self, now: datetime) -> str | None:
        notice_id = self._latest_snoozable_notice_id(now)
        if notice_id is not None:
            return notice_id
        routine = self.proactive.latest_routine()
        if routine is not None:
            return routine[0]
        return None

    def _latest_suggestion_notice_id(self) -> str | None:
        routine = self.proactive.latest_routine()
        if routine is not None:
            return routine[0]
        return self.proactive.latest_upgrade_notice_id()


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalized_task_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _snooze_response(count: int, unit: str) -> str:
    if unit.startswith("hour"):
        value = "an hour" if count == 1 else f"{count} hours"
    else:
        value = "one minute" if count == 1 else f"{count} minutes"
    return f"I will remind you in {value}."


def is_time_sensitive_note(content: str) -> bool:
    value = content.casefold()
    return re.search(
        r"\b(today|tonight|tomorrow|this morning|this afternoon|this evening|by \d{1,2}(?::\d{2})?\s*(?:am|pm)?|at \d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
        value,
    ) is not None


def _routine_label_from_message(message: str) -> str:
    match = re.match(r"^Routine: You often ask me to (?P<label>.+?)\. I can help make that quicker\.$", message)
    return match.group("label") if match else ""
