from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .spoken_text import strip_wake_prefix


@dataclass(frozen=True)
class ParsedReminder:
    message: str
    due_at: datetime


@dataclass(frozen=True)
class ReminderRecord:
    id: str
    created_at: str
    due_at: str
    message: str
    status: str = "pending"
    completed_at: str = ""


class ReminderStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def create(self, message: str, due_at: datetime) -> ReminderRecord:
        value = message.strip()
        if not value:
            raise ValueError("reminder message is required")
        record = ReminderRecord(
            id=uuid.uuid4().hex[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            due_at=_ensure_timezone(due_at).isoformat(),
            message=value,
        )
        records = self._read_all()
        records.append(record)
        self._write_all(records)
        return record

    def pending(self, now: datetime | None = None) -> list[ReminderRecord]:
        return [record for record in self._read_all() if record.status == "pending"]

    def due(self, now: datetime) -> list[ReminderRecord]:
        current = _ensure_timezone(now)
        return [
            record
            for record in self.pending(now)
            if datetime.fromisoformat(record.due_at) <= current
        ]

    def complete(self, reminder_id: str) -> ReminderRecord | None:
        records = self._read_all()
        completed: ReminderRecord | None = None
        updated: list[ReminderRecord] = []
        for record in records:
            if record.id == reminder_id and record.status == "pending":
                completed = ReminderRecord(
                    id=record.id,
                    created_at=record.created_at,
                    due_at=record.due_at,
                    message=record.message,
                    status="completed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                updated.append(completed)
            else:
                updated.append(record)
        if completed is not None:
            self._write_all(updated)
        return completed

    def reopen(self, reminder_id: str) -> ReminderRecord | None:
        records = self._read_all()
        restored: ReminderRecord | None = None
        updated: list[ReminderRecord] = []
        for record in records:
            if record.id == reminder_id and record.status == "completed":
                restored = ReminderRecord(
                    id=record.id,
                    created_at=record.created_at,
                    due_at=record.due_at,
                    message=record.message,
                )
                updated.append(restored)
            else:
                updated.append(record)
        if restored is not None:
            self._write_all(updated)
        return restored

    def complete_by_number(self, number: int) -> ReminderRecord | None:
        pending = self.pending()
        if number < 1 or number > len(pending):
            return None
        return self.complete(pending[number - 1].id)

    def _read_all(self) -> list[ReminderRecord]:
        if not self.path.exists():
            return []
        records: list[ReminderRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            records.append(
                ReminderRecord(
                    id=str(payload.get("id", "")),
                    created_at=str(payload.get("created_at", "")),
                    due_at=str(payload.get("due_at", "")),
                    message=str(payload.get("message", "")),
                    status=str(payload.get("status", "pending")),
                    completed_at=str(payload.get("completed_at", "")),
                )
            )
        return records

    def _write_all(self, records: list[ReminderRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record.__dict__, ensure_ascii=True) + "\n")


class ReminderIntentHandler:
    def __init__(self, reminders: ReminderStore, now: Callable[[], datetime] | None = None) -> None:
        self.reminders = reminders
        self.now = now
        self.pending_message: str | None = None

    def handle(self, text: str) -> str | None:
        now = self._current_time()
        text = strip_wake_prefix(text)
        text = re.sub(r"^\s*(?:would\s+you\s+)?mind\s+reminding\s+me\b", "remind me", text, flags=re.IGNORECASE)
        if self.pending_message:
            if re.match(r"^\s*(?:never\s+mind|nevermind|cancel(?:\s+that)?|forget\s+it|drop\s+it)\s*[.!?]?\s*$", text, flags=re.IGNORECASE):
                self.pending_message = None
                return "Canceled that reminder."
            timing = _normalize_followup_timing(text)
            followup = parse_reminder(f"remind me {timing} to {self.pending_message}", now)
            if followup is not None:
                self.pending_message = None
                return self._create_reminder_response(followup)
        companion_reminder = re.match(
            r"^\s*(?:tell\s+me|give\s+me\s+a\s+nudge)\s+(?P<timing>.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if companion_reminder:
            candidate = f"remind me {companion_reminder.group('timing').strip()}"
            parsed = parse_reminder(candidate, now)
            if parsed is None:
                pending = re.match(r"^\s*remind\s+me\s+to\s+(?P<message>.+)$", candidate, flags=re.IGNORECASE)
                if not pending:
                    return None
                self.pending_message = pending.group("message").strip()
                return "When should I remind you?"
            self.pending_message = None
            return self._create_reminder_response(parsed)
        if re.match(r"^\s*remind\s+me\b", text, flags=re.IGNORECASE):
            parsed = parse_reminder(text, now)
            if parsed is None:
                pending = re.match(r"^\s*remind\s+me\s+to\s+(?P<message>.+)$", text, flags=re.IGNORECASE)
                if pending:
                    self.pending_message = pending.group("message").strip()
                return "When should I remind you?"
            self.pending_message = None
            return self._create_reminder_response(parsed)
        if re.match(r"^\s*(?:list|show|read)\s+(?:my\s+)?reminders\b", text, flags=re.IGNORECASE):
            pending = self.reminders.pending(now)
            if not pending:
                return "No pending reminders."
            lines = []
            for index, reminder in enumerate(pending, start=1):
                due = datetime.fromisoformat(reminder.due_at).astimezone().strftime("%b %d at %I:%M %p")
                lines.append(f"{index}. {reminder.message} - {due}")
            return "Pending reminders:\n" + "\n".join(lines)
        complete = re.match(
            r"^\s*(?:complete|dismiss|clear)\s+reminder\s+(?P<number>\d+)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if complete:
            record = self.reminders.complete_by_number(int(complete.group("number")))
            if record is None:
                return "I could not find that pending reminder."
            return f"Completed reminder: {record.message}"
        if re.match(
            r"^\s*(?:complete|dismiss|clear)\s+(?:that\s+|the\s+|current\s+|latest\s+)?reminder\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            due = self.reminders.due(now)
            if not due:
                return "No due reminder is waiting right now."
            record = self.reminders.complete(due[0].id)
            if record is None:
                return "I could not find that pending reminder."
            return f"Completed reminder: {record.message}"
        return None

    def _current_time(self) -> datetime:
        if self.now is not None:
            return _ensure_timezone(self.now())
        return datetime.now(timezone.utc)

    def _create_reminder_response(self, parsed: ParsedReminder) -> str:
        record = self.reminders.create(parsed.message, parsed.due_at)
        due_text = parsed.due_at.astimezone().strftime("%A at %I:%M %p")
        return f"Reminder set for {due_text}: {record.message}"


def parse_reminder(text: str, now: datetime) -> ParsedReminder | None:
    current = _ensure_timezone(now)
    relative = re.match(
        r"^\s*remind\s+me\s+in\s+(?P<count>\d+)\s+(?P<unit>minutes?|hours?)\s+to\s+(?P<message>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if relative:
        count = int(relative.group("count"))
        unit = relative.group("unit").lower()
        delta = timedelta(hours=count) if unit.startswith("hour") else timedelta(minutes=count)
        return ParsedReminder(relative.group("message").strip(), current + delta)

    trailing_relative = re.match(
        r"^\s*remind\s+me\s+to\s+(?P<message>.+?)\s+in\s+(?P<count>\d+)\s+(?P<unit>minutes?|hours?)\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if trailing_relative:
        count = int(trailing_relative.group("count"))
        unit = trailing_relative.group("unit").lower()
        delta = timedelta(hours=count) if unit.startswith("hour") else timedelta(minutes=count)
        return ParsedReminder(trailing_relative.group("message").strip(), current + delta)

    tomorrow_daypart = re.match(
        r"^\s*remind\s+me\s+tomorrow\s+(?P<daypart>morning|afternoon|evening|tonight)\s+to\s+(?P<message>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if tomorrow_daypart:
        due = _daypart_time_on_date(tomorrow_daypart.group("daypart"), current + timedelta(days=1))
        return ParsedReminder(tomorrow_daypart.group("message").strip(), due)

    trailing_tomorrow_daypart = re.match(
        r"^\s*remind\s+me\s+to\s+(?P<message>.+?)\s+tomorrow\s+(?P<daypart>morning|afternoon|evening|tonight)\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if trailing_tomorrow_daypart:
        due = _daypart_time_on_date(trailing_tomorrow_daypart.group("daypart"), current + timedelta(days=1))
        return ParsedReminder(trailing_tomorrow_daypart.group("message").strip(), due)

    trailing_tomorrow = re.match(
        r"^\s*remind\s+me\s+to\s+(?P<message>.+?)\s+tomorrow\s+at\s+(?P<time>[\d:]+\s*(?:am|pm)?)\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if trailing_tomorrow:
        due = _parse_time_on_date(trailing_tomorrow.group("time"), current + timedelta(days=1))
        return ParsedReminder(trailing_tomorrow.group("message").strip(), due) if due else None

    current_daypart = re.match(
        r"^\s*remind\s+me\s+(?:(?:this\s+)?(?P<daypart>evening)|(?P<tonight>tonight))\s+to\s+(?P<message>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if current_daypart:
        daypart = current_daypart.group("daypart") or current_daypart.group("tonight")
        due = _next_daypart_time(daypart, current)
        return ParsedReminder(current_daypart.group("message").strip(), due)

    tomorrow = re.match(
        r"^\s*remind\s+me\s+tomorrow\s+at\s+(?P<time>[\d:]+\s*(?:am|pm)?)\s+to\s+(?P<message>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if tomorrow:
        due = _parse_time_on_date(tomorrow.group("time"), current + timedelta(days=1))
        return ParsedReminder(tomorrow.group("message").strip(), due) if due else None

    time_then_tomorrow = re.match(
        r"^\s*remind\s+me\s+at\s+(?P<time>[\d:]+\s*(?:am|pm)?)\s+tomorrow\s+to\s+(?P<message>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if time_then_tomorrow:
        due = _parse_time_on_date(time_then_tomorrow.group("time"), current + timedelta(days=1))
        return ParsedReminder(time_then_tomorrow.group("message").strip(), due) if due else None

    absolute = re.match(
        r"^\s*remind\s+me\s+at\s+(?P<time>[\d:]+\s*(?:am|pm)?)\s+to\s+(?P<message>.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if absolute:
        due = _parse_time_on_date(absolute.group("time"), current)
        if due and due <= current:
            due += timedelta(days=1)
        return ParsedReminder(absolute.group("message").strip(), due) if due else None

    return None


def _normalize_followup_timing(text: str) -> str:
    cleaned = re.sub(r"\s*,?\s+please\s*[.!?]?\s*$", "", text.strip(), flags=re.IGNORECASE)
    give_me = re.match(r"^\s*give\s+me\s+(?P<timing>.+)$", cleaned, flags=re.IGNORECASE)
    if give_me:
        return f"in {give_me.group('timing').strip()}"
    from_now = re.match(r"^\s*(?P<timing>\d+\s+(?:minutes?|hours?))\s+from\s+now\s*$", cleaned, flags=re.IGNORECASE)
    if from_now:
        return f"in {from_now.group('timing').strip()}"
    return cleaned


def _parse_time_on_date(value: str, base: datetime) -> datetime | None:
    cleaned = re.sub(r"\s+", "", value.strip().lower())
    match = re.match(r"^(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?(?P<ampm>am|pm)?$", cleaned)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = match.group("ampm")
    if minute > 59:
        return None
    if ampm:
        if hour < 1 or hour > 12:
            return None
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
    elif hour > 23:
        return None
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _daypart_time_on_date(value: str, base: datetime) -> datetime:
    hour_by_daypart = {
        "morning": 9,
        "afternoon": 14,
        "evening": 18,
        "tonight": 20,
    }
    return base.replace(hour=hour_by_daypart[value.lower()], minute=0, second=0, microsecond=0)


def _next_daypart_time(value: str, current: datetime) -> datetime:
    due = _daypart_time_on_date(value, current)
    if due <= current:
        return _daypart_time_on_date(value, current + timedelta(days=1))
    return due


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
