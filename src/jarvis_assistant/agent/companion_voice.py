from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from ..improvement import ImprovementQueue
from .notes import NoteStore
from .proactive import ProactiveEngine, UnfinishedTaskStore, is_time_sensitive_note
from .reminders import ReminderRecord, ReminderStore


def _normalize_phrase(text: str) -> str:
    collapsed = text.casefold().replace("'", "").replace("’", "")
    cleaned = re.sub(r"[^\w\s]", " ", collapsed)
    words = ["i" if word == "eye" else word for word in cleaned.split()]
    if words and words[0] in {"hey", "ok", "okay"}:
        words = words[1:]
    if words and words[0] in {"damien", "damian", "daemon", "daymien", "daymian", "damon"}:
        words = words[1:]
    while words:
        if words[0] == "please":
            words = words[1:]
            continue
        if len(words) >= 2 and words[:2] in (["can", "you"], ["could", "you"], ["would", "you"], ["will", "you"]):
            words = words[2:]
            continue
        break
    return " ".join(words)


class IntentPhraseMatcher:
    def __init__(self, phrases: Iterable[str]) -> None:
        self.phrases = {_normalize_phrase(phrase) for phrase in phrases}

    def matches(self, text: str) -> bool:
        return _normalize_phrase(text) in self.phrases


class AttentionCheckMatcher:
    def __init__(self, phrases: Iterable[str]) -> None:
        self.exact = IntentPhraseMatcher(phrases)

    def matches(self, text: str) -> bool:
        phrase = _normalize_phrase(text)
        if self.exact.matches(phrase):
            return True
        return (
            re.fullmatch(r"(?:do you )?need (?:anything from me|me for anything)", phrase) is not None
            or re.fullmatch(r"do i need to (?:do|handle) anything", phrase) is not None
            or re.fullmatch(r"is there anything i should (?:do|handle|look at)", phrase) is not None
            or re.fullmatch(r"what(?: is|s) waiting for me", phrase) is not None
        )


class ActiveStatusMatcher:
    def __init__(self, phrases: Iterable[str]) -> None:
        self.exact = IntentPhraseMatcher(phrases)

    def matches(self, text: str) -> bool:
        phrase = _normalize_phrase(text)
        if self.exact.matches(phrase):
            return True
        return (
            re.fullmatch(r"what are you (?:doing|working on|tracking|watching)(?: for me)?(?: now)?", phrase) is not None
            or re.fullmatch(r"what are you watching out for(?: for me)?", phrase) is not None
            or re.fullmatch(r"what are you keeping an? eye (?:on|out for)(?: for me)?", phrase) is not None
        )


class PresenceCheckMatcher:
    def matches(self, text: str) -> bool:
        phrase = _normalize_phrase(text)
        return re.fullmatch(r"(?:are )?you (?:there|awake|listening|with me)", phrase) is not None


PROACTIVE_EXPLANATION = IntentPhraseMatcher(
    [
        "why did you say",
        "why did you say that",
        "why did you tell me",
        "why did you tell me that",
        "why did you speak up",
        "why did you speak up that",
    ]
)
PROACTIVE_REPLAY = IntentPhraseMatcher(
    [
        "what did you just say",
        "what did you say",
        "what was that",
        "repeat that",
        "say that again",
    ]
)
HANDLED_ACKNOWLEDGEMENT = IntentPhraseMatcher(
    [
        "that's handled",
        "that's done",
        "done",
        "handled",
        "i handled that",
        "i did that",
        "i took care of it",
        "i took care of that",
        "handle the first one",
        "handled the first one",
        "take care of the first one",
        "i took care of the first one",
        "mark the first one handled",
        "mark the first one done",
    ]
)
UNDO_HANDLED = IntentPhraseMatcher(["undo that", "undo", "put that back", "restore that"])
SHORT_ACKNOWLEDGEMENT = IntentPhraseMatcher(
    [
        "thanks",
        "thank you",
        "got it",
        "okay",
        "ok",
        "alright",
    ]
)
ATTENTION_CHECK = AttentionCheckMatcher(
    [
        "what needs my attention",
        "check in",
        "anything need my attention",
        "what should i look at",
        "what do i need to handle",
        "what's on my plate",
        "what's next",
        "anything going on",
    ]
)
ATTENTION_COUNT = IntentPhraseMatcher(
    [
        "how much is waiting",
        "how many things are waiting",
        "how many things need me",
        "how many things need my attention",
        "how much needs my attention",
        "is much waiting",
    ]
)
READ_ATTENTION = IntentPhraseMatcher(
    [
        "read it to me",
        "read them to me",
        "read what is waiting",
        "read what's waiting",
        "read what needs my attention",
        "say what is waiting",
        "say what needs my attention",
    ]
)
FIRST_ATTENTION = IntentPhraseMatcher(
    [
        "what should i handle first",
        "what should i do first",
        "what should i look at first",
        "what is first",
        "what's first",
    ]
)
NEXT_ATTENTION = IntentPhraseMatcher(
    [
        "what should i handle next",
        "what should i do next",
        "what should i tackle next",
        "what do i handle next",
        "what do i do next",
        "what else",
        "anything else",
        "what else is waiting",
        "what else needs me",
    ]
)
FIRST_ATTENTION_REASON = IntentPhraseMatcher(
    [
        "why that first",
        "why is that first",
        "why should i handle that first",
        "why should i do that first",
    ]
)
DAY_BRIEF = IntentPhraseMatcher(
    [
        "start my day",
        "morning brief",
        "give me my brief",
        "what's my day look like",
    ]
)
EVENING_RECAP = IntentPhraseMatcher(["wrap up my day", "end my day", "evening recap", "close out my day"])
ACTIVE_STATUS = ActiveStatusMatcher(
    [
        "what are you keeping track of",
        "what are you on top of for me",
    ]
)
VOICE_HELP = IntentPhraseMatcher(
    [
        "what can i say",
        "what can i say to you",
        "what can you do",
        "help me talk to you",
    ]
)
VOICE_READINESS = IntentPhraseMatcher(
    [
        "are you ready to listen and talk",
        "are you ready to hear me and talk",
        "are you listening",
        "are you active",
        "are you active and speaking up",
        "is your voice ready",
        "are you speaking notices aloud",
        "will you speak notices aloud",
        "speak notices aloud",
    ]
)
PRESENCE_CHECK = PresenceCheckMatcher()
RETURN_CHECK = IntentPhraseMatcher(
    [
        "i'm back",
        "im back",
        "i am back",
        "back",
        "i'm here",
        "im here",
        "i am here",
    ]
)
CATCH_UP = IntentPhraseMatcher(
    [
        "what did i miss",
        "did i miss anything",
        "catch me up",
        "catch me up on what i missed",
        "anything happen while i was gone",
        "what happened while i was gone",
    ]
)
SAVED_ROUTINE_REQUEST = IntentPhraseMatcher(
    [
        "do my saved routine",
        "run my saved routine",
        "do my routine",
        "run my routine",
        "start my routine",
        "kick off my routine",
        "do that routine",
        "run that routine",
    ]
)


class CompanionVoiceIntents:
    def __init__(
        self,
        reminders: ReminderStore,
        notes: NoteStore,
        unfinished_tasks: UnfinishedTaskStore,
        proactive: ProactiveEngine,
        improvement_queue: ImprovementQueue,
        audit_path: Path | None,
        now: Callable[[], object],
        voice_status_provider: Callable[[], str] | None = None,
    ) -> None:
        self.reminders = reminders
        self.notes = notes
        self.unfinished_tasks = unfinished_tasks
        self.proactive = proactive
        self.improvement_queue = improvement_queue
        self.audit_path = audit_path
        self.now = now
        self.voice_status_provider = voice_status_provider
        self.last_handled_item: tuple[str, str] | None = None

    def handle(self, text: str) -> str | None:
        for handler in (
            self._proactive_replay_request,
            self._proactive_explanation_request,
            self._undo_handled_request,
            self._handled_acknowledgement_request,
            self._short_acknowledgement_request,
            self._first_attention_request,
            self._next_attention_request,
            self._first_attention_reason_request,
            self._attention_count_request,
            self._read_attention_request,
            self._attention_check_request,
            self._day_brief_request,
            self._evening_recap_request,
            self._active_status_request,
            self._voice_readiness_request,
            self._return_check_request,
            self._catch_up_request,
            self._presence_check_request,
            self._voice_help_request,
        ):
            response = handler(text)
            if response is not None:
                return response
        return None

    def _current_time(self):
        return self.now()

    def _proactive_explanation_request(self, text: str) -> str | None:
        if not PROACTIVE_EXPLANATION.matches(text):
            return None
        outcome = self._latest_proactive_outcome()
        if outcome:
            return f"I spoke up because {_notice_reason_from_outcome(outcome)}"
        return "I do not have a recent proactive reason logged."

    def _proactive_replay_request(self, text: str) -> str | None:
        if not PROACTIVE_REPLAY.matches(text):
            return None
        outcome = self._latest_proactive_outcome()
        if not outcome:
            return "I do not have a recent proactive notice logged."
        return f"I just said: {_notice_message_from_outcome(outcome)}"

    def _latest_proactive_outcome(self) -> str:
        if self.audit_path is None or not self.audit_path.exists():
            return ""
        try:
            lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ""
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            tools_called = payload.get("tools_called", [])
            if not isinstance(tools_called, list) or "proactive_notice" not in tools_called:
                continue
            outcome = str(payload.get("outcome", "")).strip()
            if outcome:
                return outcome
        return ""

    def _handled_acknowledgement_request(self, text: str) -> str | None:
        if not HANDLED_ACKNOWLEDGEMENT.matches(text):
            return None
        actionable_reminder = next(iter(self._actionable_due_reminders(self._current_time())), None)
        if actionable_reminder is not None:
            completed = self.reminders.complete(actionable_reminder.id)
            if completed is not None:
                self.last_handled_item = ("reminder", completed.id)
                return f"Handled: {completed.message}"
        completed_task = self.unfinished_tasks.complete_latest()
        if completed_task is not None:
            self.last_handled_item = ("unfinished", completed_task.id)
            self.proactive.dismiss(f"unfinished:{completed_task.id}")
            return f"Handled: {completed_task.title}"
        actionable_note = self._actionable_time_sensitive_note()
        if actionable_note is not None:
            self.last_handled_item = ("note", actionable_note.id)
            self.proactive.dismiss(f"note:{actionable_note.id}")
            return f"Handled: {actionable_note.content}"
        return "I do not see anything waiting to mark handled."

    def _short_acknowledgement_request(self, text: str) -> str | None:
        phrase = _normalize_phrase(text)
        phrase = re.sub(r"\s+(?:damien|damian|daemon|daymien|daymian|damon)$", "", phrase)
        if phrase not in SHORT_ACKNOWLEDGEMENT.phrases:
            return None
        if phrase in {"thanks", "thank you"}:
            return "Anytime."
        return "Got it."

    def _undo_handled_request(self, text: str) -> str | None:
        if not UNDO_HANDLED.matches(text):
            return None
        if self.last_handled_item is None:
            return "I do not have a handled item to undo."
        kind, item_id = self.last_handled_item
        if kind == "reminder":
            restored = self.reminders.reopen(item_id)
            if restored is not None:
                self.last_handled_item = None
                return f"Restored reminder: {restored.message}"
        if kind == "unfinished":
            restored_task = self.unfinished_tasks.reopen(item_id)
            if restored_task is not None:
                self.last_handled_item = None
                return f"Restored followup: {restored_task.title}"
        if kind == "note":
            restored_note = self._find_note(item_id)
            if restored_note is not None:
                self.proactive.restore_notice(f"note:{restored_note.id}")
                self.last_handled_item = None
                return f"Restored heads up: {restored_note.content}"
        return "I could not restore that handled item."

    def _attention_check_request(self, text: str) -> str | None:
        if not ATTENTION_CHECK.matches(text):
            return None
        lines = self._attention_lines()
        if not lines:
            return "Nothing needs your attention right now."
        return "Here is what needs attention:\n" + "\n".join(lines)

    def _attention_count_request(self, text: str) -> str | None:
        if not ATTENTION_COUNT.matches(text):
            return None
        lines = self._attention_lines(include_quiet=False)
        if not lines:
            return "Nothing needs your attention right now."
        item = self._first_attention_item()
        count = len(lines)
        label = "1 thing" if count == 1 else f"{count} things"
        verb = "needs" if count == 1 else "need"
        if item is None:
            return f"{label} {verb} your attention."
        return f"{label} {verb} your attention. First: {item}"

    def _read_attention_request(self, text: str) -> str | None:
        if not READ_ATTENTION.matches(text):
            return None
        lines = self._attention_lines()
        if not lines:
            return "Nothing needs your attention right now."
        return "Reading what needs attention:\n" + "\n".join(lines)

    def _first_attention_request(self, text: str) -> str | None:
        if not FIRST_ATTENTION.matches(text):
            return None
        item = self._first_attention_item()
        if item is None:
            return "Nothing needs your attention right now."
        return f"First: {item}"

    def _next_attention_request(self, text: str) -> str | None:
        if not NEXT_ATTENTION.matches(text):
            return None
        item = self._first_attention_item()
        if item is None:
            return "Nothing needs your attention right now."
        return f"Next: {item}"

    def _first_attention_reason_request(self, text: str) -> str | None:
        if not FIRST_ATTENTION_REASON.matches(text):
            return None
        reason = self._first_attention_reason()
        if reason is None:
            return "Nothing needs your attention right now."
        return reason

    def _day_brief_request(self, text: str) -> str | None:
        if not DAY_BRIEF.matches(text):
            return None
        now = self._current_time()
        lines: list[str] = []
        quiet_line = self._quiet_mode_line(now, "Quiet mode: staying quiet")
        if quiet_line is not None:
            lines.append(quiet_line)
        due_reminders = self._actionable_due_reminders(now)
        if due_reminders:
            lines.append(f"- Due now: {due_reminders[0].message}")
        later_today = []
        for reminder in self.reminders.pending(now):
            due_at = _parse_stored_datetime(reminder.due_at)
            if due_at is None or due_at <= now or due_at.date() != now.date():
                continue
            later_today.append((due_at, reminder.message))
        if later_today:
            due_at, message = sorted(later_today, key=lambda item: item[0])[0]
            lines.append(f"- Later today: {message} at {due_at.strftime('%I:%M %p')}")
        unfinished = self.unfinished_tasks.open()
        if unfinished:
            lines.append(f"- Still open: {unfinished[-1].title}")
        if not lines:
            return "Good morning. Nothing is waiting on you right now."
        return "Good morning. Here's your brief:\n" + "\n".join(lines)

    def _evening_recap_request(self, text: str) -> str | None:
        if not EVENING_RECAP.matches(text):
            return None
        now = self._current_time()
        lines: list[str] = []
        quiet_line = self._quiet_mode_line(now, "Quiet mode: staying quiet")
        if quiet_line is not None:
            lines.append(quiet_line)
        tomorrow_reminders = []
        for reminder in self.reminders.pending(now):
            due_at = _parse_stored_datetime(reminder.due_at)
            if due_at is None or due_at.date() != (now + timedelta(days=1)).date():
                continue
            tomorrow_reminders.append((due_at, reminder.message))
        if tomorrow_reminders:
            due_at, message = sorted(tomorrow_reminders, key=lambda item: item[0])[0]
            lines.append(f"- Tomorrow: {message} at {due_at.strftime('%I:%M %p')}")
        unfinished = self.unfinished_tasks.open()
        if unfinished:
            lines.append(f"- Still open: {unfinished[-1].title}")
        if not lines:
            return "Here's your evening recap: nothing is waiting on you."
        return "Here's your evening recap:\n" + "\n".join(lines)

    def _active_status_request(self, text: str) -> str | None:
        if not ACTIVE_STATUS.matches(text):
            return None
        lines: list[str] = []
        now = self._current_time()
        quiet_line = self._quiet_mode_line(now, "Staying quiet")
        if quiet_line is not None:
            lines.append(quiet_line)
        pending_reminders = self.reminders.pending(now)
        if pending_reminders:
            latest = pending_reminders[-1].message
            lines.append(f"- {_count_label(len(pending_reminders), 'pending reminder')}: {latest}")
        saved_notes = self.notes.list_recent()
        if saved_notes:
            latest_note = saved_notes[-1].content
            lines.append(f"- {_count_label(len(saved_notes), 'saved note')}: {latest_note}")
        unfinished = self.unfinished_tasks.open()
        if unfinished:
            latest = unfinished[-1].title
            lines.append(f"- {_count_label(len(unfinished), 'unfinished followup')}: {latest}")
        routine_label = self.proactive.latest_accepted_routine_label()
        if routine_label is not None:
            lines.append(f"- 1 saved routine: {routine_label}")
        if not lines:
            return "I am not keeping track of anything active right now."
        return "I am keeping track of:\n" + "\n".join(lines)

    def _quiet_mode_line(self, now: datetime, label: str) -> str | None:
        quiet_until = self.proactive.active_quiet_until(now)
        if quiet_until is None:
            return None
        quiet_until = quiet_until.astimezone(now.tzinfo)
        return f"- {label} until {quiet_until.strftime('%I:%M %p')}"

    def _first_attention_item(self) -> str | None:
        due_reminder = next(iter(self._actionable_due_reminders(self._current_time())), None)
        if due_reminder is not None:
            return due_reminder.message
        unfinished = self.unfinished_tasks.open()
        if unfinished:
            return unfinished[-1].title
        note = self._actionable_time_sensitive_note()
        if note is not None and not self.proactive.is_delivered(f"note:{note.id}"):
            return note.content
        latest_upgrade = self.improvement_queue.latest()
        if latest_upgrade is not None:
            suggestion = latest_upgrade.get("suggestion", "").strip()
            if suggestion:
                return suggestion
        return None

    def _first_attention_reason(self) -> str | None:
        due_reminder = next(iter(self._actionable_due_reminders(self._current_time())), None)
        if due_reminder is not None:
            return f"Because it is due now: {due_reminder.message}"
        unfinished = self.unfinished_tasks.open()
        if unfinished:
            return f"Because it is still open: {unfinished[-1].title}"
        note = self._actionable_time_sensitive_note()
        if note is not None and not self.proactive.is_delivered(f"note:{note.id}"):
            return f"Because it is time-sensitive: {note.content}"
        latest_upgrade = self.improvement_queue.latest()
        if latest_upgrade is not None:
            suggestion = latest_upgrade.get("suggestion", "").strip()
            if suggestion:
                return f"Because it is an opportunity: {suggestion}"
        return None

    def _presence_check_request(self, text: str) -> str | None:
        if not PRESENCE_CHECK.matches(text):
            return None
        item = self._first_attention_item()
        if item is not None:
            return f"I am here. First: {item}"
        return "I am here. Say what needs my attention, what are you doing now, or what can I say to you."

    def _return_check_request(self, text: str) -> str | None:
        if not RETURN_CHECK.matches(text):
            return None
        item = self._first_attention_item()
        if item is None:
            return "Welcome back. Nothing needs your attention right now."
        return f"Welcome back. First: {item}"

    def _catch_up_request(self, text: str) -> str | None:
        if not CATCH_UP.matches(text):
            return None
        lines = self._attention_lines(include_quiet=False)
        if not lines:
            return "You did not miss anything that needs your attention."
        return "While you were away:\n" + "\n".join(lines)

    def _voice_readiness_request(self, text: str) -> str | None:
        if not VOICE_READINESS.matches(text):
            return None
        if self.voice_status_provider is None:
            return "Voice readiness is not connected to this conversation yet."
        status = self.voice_status_provider().strip()
        if not status:
            return "Voice readiness is not connected to this conversation yet."
        return status

    def _voice_help_request(self, text: str) -> str | None:
        if not VOICE_HELP.matches(text):
            return None
        if self._first_attention_item() is not None:
            return (
                "You can say: what's first, why that first, that's handled, snooze that, dismiss that, "
                "what are you doing now, be active and speak up, stop speaking up, or be quiet for an hour."
            )
        return (
            "You can say things like: start my day, what needs my attention, snooze that, dismiss that, "
            "that's handled, undo that, what are you doing now, be quiet for an hour, "
            "be active and speak up, stop speaking up, are you in quiet mode, you can speak up again, "
            "or wrap up my day."
        )

    def _actionable_due_reminders(self, now: datetime) -> list[ReminderRecord]:
        return [
            reminder
            for reminder in self.reminders.due(now)
            if not self.proactive.is_delivered(f"reminder:{reminder.id}")
        ]

    def _actionable_time_sensitive_note(self):
        for note in reversed(self.notes.list_recent(limit=20)):
            if is_time_sensitive_note(note.content):
                return note
        return None

    def _find_note(self, note_id: str):
        for note in self.notes.list_recent(limit=20):
            if note.id == note_id:
                return note
        return None

    def _attention_lines(self, include_quiet: bool = True) -> list[str]:
        lines: list[str] = []
        now = self._current_time()
        if include_quiet:
            quiet_line = self._quiet_mode_line(now, "Quiet mode: staying quiet")
            if quiet_line is not None:
                lines.append(quiet_line)
        due_reminders = self._actionable_due_reminders(now)
        if due_reminders:
            lines.append(f"- Due reminder: {due_reminders[0].message}")
        unfinished = self.unfinished_tasks.open()
        if unfinished:
            lines.append(f"- Unfinished followup: {unfinished[-1].title}")
        for note in reversed(self.notes.list_recent(limit=20)):
            if self.proactive.is_delivered(f"note:{note.id}"):
                continue
            if is_time_sensitive_note(note.content):
                lines.append(f"- Heads up: {note.content}")
                break
        latest_upgrade = self.improvement_queue.latest()
        if latest_upgrade is not None:
            suggestion = latest_upgrade.get("suggestion", "").strip()
            if suggestion:
                lines.append(f"- Opportunity: {suggestion}")
        return lines


def _count_label(count: int, singular: str) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {singular}s"


def _notice_message_from_outcome(outcome: str) -> str:
    match = re.match(r"^[a-z_]+:\s*(?P<message>.+)$", outcome.strip())
    return match.group("message") if match else outcome.strip()


def _notice_reason_from_outcome(outcome: str) -> str:
    match = re.match(r"^(?P<reason>[a-z_]+):\s*(?P<message>.+)$", outcome.strip())
    if not match:
        return outcome.strip()
    reason = match.group("reason")
    message = match.group("message").strip()
    if reason == "due_reminder":
        reminder = re.sub(r"^Reminder:\s*", "", message).strip()
        return f"a reminder is due: {reminder}"
    if reason == "unfinished_task":
        task = re.sub(r"^Unfinished:\s*", "", message).strip()
        return f"something is still unfinished: {task}"
    if reason == "saved_note_opportunity":
        note = re.sub(r"^Heads up:\s*", "", message).strip()
        return f"a saved note looks time-sensitive: {note}"
    if reason == "upgrade_opportunity":
        opportunity = re.sub(r"^Opportunity:\s*", "", message).strip()
        return f"I found an opportunity: {opportunity}"
    if reason == "self_repair_started":
        repair = re.sub(r"^Repair started:\s*", "", message).strip()
        return f"a repair started: {repair}"
    if reason == "self_repair_finished":
        repair = re.sub(r"^Repair finished:\s*", "", message).strip()
        return f"a repair finished: {repair}"
    if reason == "repeated_routine":
        routine = re.sub(r"^Routine:\s*", "", message).strip()
        return f"I noticed a routine: {routine}"
    return message


def _parse_stored_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
