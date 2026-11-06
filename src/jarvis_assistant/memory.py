from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class LongTermMemory:
    def __init__(self, path: Path, enabled: bool) -> None:
        self.path = path
        self.enabled = enabled

    def list_memories(self, category: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        memories = [self._normalize(json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if category is None:
            return memories
        return [memory for memory in memories if memory.get("category") == category]

    def add(self, text: str, category: str = "fact") -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "content": text,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=True) + "\n")

    def add_preference(self, text: str) -> None:
        self.add(text, category="preference")

    def add_episode_summary(self, text: str) -> None:
        self.add(text, category="episode")

    def delete_all(self) -> None:
        if self.path.exists():
            self.path.unlink()

    @staticmethod
    def _normalize(record: dict) -> dict:
        if "category" not in record:
            record["category"] = "fact"
        return record
