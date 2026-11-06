from __future__ import annotations


def microphone_name_tokens(name: str) -> set[str]:
    return {token for token in "".join(char.lower() if char.isalnum() else " " for char in name).split() if len(token) > 2}


def update_stream_response(current: str, chunk: str) -> str:
    if chunk.startswith(current):
        return chunk
    return current + chunk


def stream_chunk_mode(current: str, chunk: str) -> str:
    return "full_partial" if chunk.startswith(current) else "delta"


def pop_ready_speech_segments(buffer: str, force: bool = False) -> tuple[list[str], str]:
    segments: list[str] = []
    start = 0
    for index, char in enumerate(buffer):
        if char in ".!?\n":
            if char == "." and _is_numbered_list_marker(buffer, index):
                continue
            segment = buffer[start : index + 1].strip()
            if segment:
                segments.append(segment)
            start = index + 1
    remainder = buffer[start:]
    if force and remainder.strip():
        segments.append(remainder.strip())
        remainder = ""
    return segments, remainder


def short_status_text(text: str, limit: int) -> str:
    value = " ".join(text.split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def tts_engine_label(value: str) -> str:
    return "Windows SAPI" if value == "pyttsx3" else "Piper Neural"


def tts_engine_value(label: str) -> str:
    return "pyttsx3" if label == "Windows SAPI" else "piper"


def sensitivity_label(value: float) -> str:
    if value >= 0.82:
        return "High"
    if value <= 0.55:
        return "Low"
    return "Normal"


def sensitivity_value(label: str) -> float:
    if label == "High":
        return 0.88
    if label == "Low":
        return 0.50
    return 0.72


def describe_recording(result: object) -> str:
    rms = float(getattr(result, "rms"))
    peak = float(getattr(result, "peak"))
    return (
        f"device_index={getattr(result, 'device_index', None)}; name={getattr(result, 'device_name', '')!r}; "
        f"sample_rate={getattr(result, 'sample_rate', None)}; rms={rms:.5f}; "
        f"peak={peak:.5f}; volume={int(getattr(result, 'volume_percent'))}%"
    )


def recording_volume_text(result: object) -> str:
    return (
        f"Microphone volume: {int(getattr(result, 'volume_percent'))}% "
        f"(RMS {float(getattr(result, 'rms')):.5f}, peak {float(getattr(result, 'peak')):.5f}) on {getattr(result, 'device_name', '')}"
    )


def draw_canvas_shape(canvas: object, shape: dict[str, object], scale: float = 1.0) -> None:
    kind = str(shape["kind"])
    coords = tuple(float(coord) * scale for coord in shape["coords"])
    options = {key: value for key, value in shape.items() if key not in {"name", "kind", "coords"}}
    if "width" in options:
        options["width"] = max(1, int(float(options["width"]) * scale))
    if kind == "oval":
        canvas.create_oval(*coords, **options)
    elif kind == "polygon":
        canvas.create_polygon(*coords, **options)
    elif kind == "line":
        canvas.create_line(*coords, **options)
    elif kind == "arc":
        options.setdefault("style", "arc")
        canvas.create_arc(*coords, **options)


def _is_numbered_list_marker(buffer: str, dot_index: int) -> bool:
    start = dot_index - 1
    while start >= 0 and buffer[start].isdigit():
        start -= 1
    if start == dot_index - 1:
        return False
    prefix = buffer[start] if start >= 0 else ""
    suffix = buffer[dot_index + 1] if dot_index + 1 < len(buffer) else ""
    return (not prefix or prefix.isspace()) and (not suffix or suffix.isspace())
