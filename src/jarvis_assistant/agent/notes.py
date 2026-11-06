from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .spoken_text import strip_wake_prefix


@dataclass(frozen=True)
class NoteRecord:
    id: str
    created_at: str
    content: str
    source: str = "user"


class NoteStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def add(self, content: str, source: str = "user") -> NoteRecord:
        value = content.strip()
        if not value:
            raise ValueError("note content is required")
        record = NoteRecord(
            id=uuid.uuid4().hex[:12],
            created_at=datetime.now(timezone.utc).isoformat(),
            content=value,
            source=source,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.__dict__, ensure_ascii=True) + "\n")
        return record

    def list_recent(self, limit: int = 10) -> list[NoteRecord]:
        records = self._read_all()
        return records[-limit:]

    def search(self, query: str, limit: int = 10) -> list[NoteRecord]:
        terms = [_term_variants(term.casefold()) for term in query.split() if term.strip()]
        if not terms:
            return []
        matches = [
            record
            for record in self._read_all()
            if all(any(term in record.content.casefold() for term in variants) for variants in terms)
        ]
        return matches[:limit]

    def _read_all(self) -> list[NoteRecord]:
        if not self.path.exists():
            return []
        records: list[NoteRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            records.append(
                NoteRecord(
                    id=str(payload.get("id", "")),
                    created_at=str(payload.get("created_at", "")),
                    content=str(payload.get("content", "")),
                    source=str(payload.get("source", "user")),
                )
            )
        return records


class NoteIntentHandler:
    def __init__(self, notes: NoteStore) -> None:
        self.notes = notes

    def handle(self, text: str) -> str | None:
        text = strip_wake_prefix(text)
        text = re.sub(r"^\s*(?:would\s+you\s+)?mind\s+remembering\b", "remember", text, flags=re.IGNORECASE)
        text = re.sub(r"^\s*(?:would\s+you\s+)?mind\s+keeping\s+in\s+mind\b", "keep in mind", text, flags=re.IGNORECASE)
        save = re.match(
            r"^\s*(?:(?:remember|save)\s+(?:as\s+)?(?:a\s+)?note(?:\s+that|:)?|(?:make|take)\s+(?:a\s+)?note(?:\s+that|:)?|remember(?:\s+that)?|keep\s+in\s+mind(?:\s+that)?)\s+(?P<value>.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if save:
            record = self.notes.add(save.group("value"))
            return f"Saved note: {record.content}"
        direct_save = re.match(r"^\s*save\s+(?:the\s+)?(?P<value>.+?)\s*[.!?]?\s*$", text, flags=re.IGNORECASE)
        if direct_save:
            value = direct_save.group("value").strip()
            if not _looks_like_non_note_save_target(value):
                record = self.notes.add(value)
                return f"Saved note: {record.content}"
        recall = re.match(
            r"^\s*what\s+did\s+i\s+say\s+about\s+(?P<query>.+?)\s*\??\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if recall:
            matches = self.notes.search(recall.group("query"))
            if not matches:
                return "I do not have a note about that yet."
            return "You said:\n" + "\n".join(f"- {record.content}" for record in matches)
        remember_recall = re.match(
            r"^\s*what\s+do\s+you\s+remember\s+about\s+(?P<query>.+?)\s*\??\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if remember_recall:
            matches = self.notes.search(remember_recall.group("query"))
            if not matches:
                return "I do not remember anything about that yet."
            return "I remember:\n" + "\n".join(f"- {record.content}" for record in matches)
        if re.match(
            r"^\s*(?:what\s+do\s+you\s+remember\s+(?:for|about)\s+me|what\s+did\s+you\s+save\s+for\s+me|what\s+have\s+you\s+got\s+saved\s+for\s+me)\s*\??\s*$",
            text,
            flags=re.IGNORECASE,
        ):
            notes = self.notes.list_recent()
            if not notes:
                return "I do not remember anything for you yet."
            return "I remember:\n" + "\n".join(f"- {record.content}" for record in notes)
        location_recall = re.match(
            r"^\s*(?:(?:do\s+you\s+)?remember\s+where\s+(?:my\s+|the\s+)?(?P<remember_query>.+?)\s+(?:is|are)|where\s+did\s+i\s+(?:put|leave|place)\s+(?:my\s+|the\s+)?(?P<placed_query>.+?)|where\s+(?:is|are)\s+(?:my\s+|the\s+)?(?P<query>.+?))\s*\??\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if location_recall:
            query = location_recall.group("remember_query") or location_recall.group("placed_query") or location_recall.group("query")
            matches = self.notes.search(query)
            if not matches:
                return "I do not remember where that is yet."
            return "I remember:\n" + "\n".join(f"- {record.content}" for record in matches)
        search = re.match(
            r"^\s*(?:search|find|look\s+up)\s+(?:my\s+)?notes?\s+(?:for|about)\s+(?P<query>.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if search:
            matches = self.notes.search(search.group("query"))
            if not matches:
                return "I did not find matching notes."
            return "Matching notes:\n" + "\n".join(f"- {record.content}" for record in matches)
        if re.search(r"\b(show|list|read)\s+(?:my\s+)?notes?\b", text, flags=re.IGNORECASE):
            notes = self.notes.list_recent()
            if not notes:
                return "No local notes yet."
            return "Recent notes:\n" + "\n".join(f"- {record.content}" for record in notes)
        return None


def _term_variants(term: str) -> set[str]:
    variants = {term}
    if term.endswith("ies") and len(term) > 3:
        variants.add(f"{term[:-3]}y")
    elif term.endswith("s") and len(term) > 3:
        variants.add(term[:-1])
    else:
        variants.add(f"{term}s")
    return variants


def _looks_like_non_note_save_target(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip(" .").casefold()
    if normalized in {"settings", "setting", "config", "configuration", "file", "document", "profile"}:
        return True
    return bool(
        re.search(
            r"\b(?:to|on)\s+(?:the\s+)?clipboard\b|\bas\s+(?:a\s+)?(?:file|document)\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )
