from __future__ import annotations

import re

from ..tools import PlannedTool, ToolRegistry


class MultitaskPlanner:
    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    def plan(self, text: str) -> list[PlannedTool]:
        parts = _split_multitask_text(text)
        if len(parts) < 2:
            return []
        plans: list[PlannedTool] = []
        for part in parts:
            if _is_lobby_followup(part) and any(plan.name == "open_approved_app" for plan in plans):
                continue
            planned = self.tools.plan(_normalize_multitask_part(part))
            if planned is None or planned.risk.value != "low":
                return []
            plans.append(planned)
        return plans


def _split_multitask_text(text: str) -> list[str]:
    chunks = [
        chunk.strip(" .,")
        for chunk in re.split(r"\s*(?:,|\bthen\b|\balso\b|\band\b)\s*", text, flags=re.IGNORECASE)
    ]
    chunks = _join_split_call_targets([chunk for chunk in chunks if chunk])
    if len(chunks) < 2:
        return []
    action_pattern = re.compile(
        r"^\s*(?:open|launch|start|close|quit|stop|call|answer|accept|read|take|what|show|list|copy|press|click|pause|resume|play|skip|previous|next)\b",
        re.IGNORECASE,
    )
    return chunks if all(action_pattern.search(chunk) for chunk in chunks) else []


def _join_split_call_targets(chunks: list[str]) -> list[str]:
    joined: list[str] = []
    index = 0
    while index < len(chunks):
        chunk = chunks[index]
        if re.match(r"^\s*(?:call|voice\s+call)\s*$", chunk, flags=re.IGNORECASE) and index + 1 < len(chunks):
            joined.append(f"{chunk} {chunks[index + 1]}")
            index += 2
            continue
        joined.append(chunk)
        index += 1
    return joined


def _normalize_multitask_part(text: str) -> str:
    value = text.strip()
    if re.match(r"^\s*call\s+(?:the\s+)?group\s+chat\s*$", value, flags=re.IGNORECASE):
        return "call the group chat on Discord"
    return value


def _is_lobby_followup(text: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:take|get|bring)\s+me\s+to\s+(?:the\s+)?lobby\s*$|^\s*(?:go|continue)\s+to\s+(?:the\s+)?lobby\s*$",
            text,
            flags=re.IGNORECASE,
        )
    )
