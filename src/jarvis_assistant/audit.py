from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    user_request: str
    provider: str
    tools_called: list[str] = field(default_factory=list)
    cloud_data_sent: bool = False
    confirmations_requested: list[str] = field(default_factory=list)
    outcome: str = ""


class AuditLogger:
    def __init__(self, path: Path, enabled: bool = True) -> None:
        self.path = path
        self.enabled = enabled

    def log(self, event: AuditEvent) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(event)
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=True) + "\n")

