from __future__ import annotations

from .app_helpers import microphone_name_tokens
from .audio import InputDevice


def repaired_microphone_settings(
    saved_index: int | None,
    saved_name: str,
    devices: list[InputDevice],
) -> dict[str, int | str] | None:
    if saved_index is None or any(device.index == saved_index for device in devices):
        return None
    saved_tokens = microphone_name_tokens(saved_name)
    if not saved_tokens:
        return None
    scored = []
    for device in devices:
        overlap = len(saved_tokens & microphone_name_tokens(device.name))
        if overlap:
            scored.append((overlap, device.index, device.name))
    if not scored:
        return None
    _overlap, device_index, device_name = max(scored)
    return {"microphone_device_index": device_index, "microphone_device_name": device_name}
