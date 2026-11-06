from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw


MASCOT_WIDGET_SIZE = (184, 226)
MASCOT_CANVAS_SIZE = MASCOT_WIDGET_SIZE
TRANSPARENT_MASCOT_BG = "#010203"
SMOOTH_RENDER_SCALE = 4
FLOATING_MASCOT_SHOW_LABELS = False
MASCOT_ASSET_RELATIVE_PATH = Path("assets") / "mascot" / "damien_butler_v2.png"

ACCENT_COLORS = {
    "cyan": "#48d1b2",
    "green": "#38d176",
    "gold": "#d9a441",
    "red": "#c94f64",
    "purple": "#a78bfa",
    "blue": "#3aa8ff",
}
ACCENT_DARK_COLORS = {
    "cyan": "#1a8d79",
    "green": "#1f8f58",
    "gold": "#9b7530",
    "red": "#8d3447",
    "purple": "#6d56bd",
    "blue": "#246da8",
}


def accent_hex(name: str, custom: str = "") -> str:
    if name == "custom" and re.fullmatch(r"#[0-9a-fA-F]{6}", custom.strip()):
        return custom.strip()
    return ACCENT_COLORS.get(name, ACCENT_COLORS["cyan"])


def darker_accent(accent: str) -> str:
    for name, value in ACCENT_COLORS.items():
        if accent.lower() == value:
            return ACCENT_DARK_COLORS[name]
    value = accent.strip().lstrip("#")
    if len(value) != 6:
        return "#1a8d79"
    red = max(0, int(value[0:2], 16) - 62)
    green = max(0, int(value[2:4], 16) - 48)
    blue = max(0, int(value[4:6], 16) - 17)
    return f"#{red:02x}{green:02x}{blue:02x}"


def mascot_dimensions(size: str) -> tuple[int, int, float]:
    scale = {"small": 0.85, "large": 1.155}.get(size, 1.0)
    return (int(MASCOT_WIDGET_SIZE[0] * scale), int(MASCOT_WIDGET_SIZE[1] * scale), scale)


def mascot_start_position(
    saved_x: int | None,
    saved_y: int | None,
    width: int,
    height: int,
    screen_width: int,
    screen_height: int,
) -> tuple[int, int]:
    default_x = max(16, screen_width - width - 36)
    default_y = max(32, screen_height - height - 96)
    x = saved_x if saved_x is not None else default_x
    y = saved_y if saved_y is not None else default_y
    x = max(0, min(int(x), max(0, screen_width - width)))
    y = max(0, min(int(y), max(0, screen_height - height)))
    return x, y


def mascot_widget_status(
    *,
    streaming_active: bool,
    wake_on: bool,
    mic_on: bool,
    engine_on: bool,
) -> tuple[str, str]:
    if streaming_active:
        label, accent = "Thinking", "#f1b84b"
    elif wake_on:
        label, accent = "Listening", "#38d176"
    elif mic_on:
        label, accent = "Mic Ready", "#4db6ff"
    else:
        label, accent = "Muted", "#d35c6a"
    if not engine_on:
        label = "Local AI..."
    return label, accent


def hybrid_dark_theme(accent: str = "#48d1b2", style: str = "hybrid", reduce_glow: bool = False) -> dict[str, str]:
    accent_dark = darker_accent(accent)
    line = "#2d3742" if reduce_glow else "#213443"
    if style == "minimal":
        line = "#2a313a"
    elif style == "chatrtx":
        line = "#26384a"
    elif style == "jarvis" and not reduce_glow:
        line = "#315667"
    return {
        "bg": "#070b10",
        "panel": "#101821",
        "panel_alt": "#0c141d",
        "panel_deep": "#091018",
        "line": line,
        "text": "#f1f7fb",
        "muted": "#9fb2c0",
        "accent": accent,
        "accent_dark": accent_dark,
        "warning": "#d9a441",
        "danger": "#c94f64",
        "blue": "#3aa8ff",
        "input_bg": "#0a121a",
        "input_text": "#f1f7fb",
        "surface_bg": "#060a0f",
        "surface_text": "#e3eef5",
        "speaker": "#7fdcff",
        "message": "#dde8ee",
        "gold": "#d9a441",
        "cyan": "#7fdcff",
    }


def alienware_motion_state(phase: int, state: str = "idle") -> dict[str, int]:
    speed = {"idle": 1, "listening": 2, "thinking": 3}.get(state, 1)
    pulse_base = {"idle": 2, "listening": 4, "thinking": 7}.get(state, 2)
    angle = (phase * speed / 12) * math.pi
    return {
        "bob": int(round(math.sin(angle) * 4)),
        "pulse": pulse_base + int(round((math.sin(angle) + 1) * 2)),
        "glow_width": {"idle": 2, "listening": 4, "thinking": 5, "muted": 2}.get(state, 2),
    }


def _shift_coords(coords: tuple[float, ...] | tuple[int, ...], dx: int = 0, dy: int = 0) -> tuple[float, ...]:
    shifted = []
    for index, coord in enumerate(coords):
        shifted.append(coord + (dx if index % 2 == 0 else dy))
    return tuple(shifted)


def _shift_shape(shape: dict[str, object], dx: int = 0, dy: int = 0) -> dict[str, object]:
    shifted = dict(shape)
    shifted["coords"] = _shift_coords(shape["coords"], dx=dx, dy=dy)  # type: ignore[arg-type]
    return shifted


def _scaled_coords(coords: object, scale: float) -> tuple[float, ...]:
    return tuple(float(coord) * scale for coord in coords)  # type: ignore[union-attr]


def _pillow_color(value: object) -> str | None:
    text = str(value)
    return text if text else None


def _draw_pillow_shape(draw: ImageDraw.ImageDraw, shape: dict[str, object], scale: float) -> None:
    kind = str(shape["kind"])
    coords = _scaled_coords(shape["coords"], scale)
    fill = _pillow_color(shape.get("fill", ""))
    outline = _pillow_color(shape.get("outline", ""))
    width = max(1, int(float(shape.get("width", 1)) * scale))
    if kind == "oval":
        draw.ellipse(coords, fill=fill, outline=outline, width=width)
    elif kind == "polygon":
        draw.polygon(coords, fill=fill, outline=outline)
    elif kind == "line":
        draw.line(coords, fill=fill, width=width, joint="curve")
    elif kind == "arc":
        start = int(shape.get("start", 0))
        extent = int(shape.get("extent", 360))
        draw.arc(coords, start=start, end=start + extent, fill=outline, width=width)


def smooth_mascot_image(
    accent: str,
    engine_on: bool,
    mic_on: bool,
    phase: int = 0,
    state: str = "idle",
    scale: float = 1.0,
) -> Image.Image:
    width = int(MASCOT_CANVAS_SIZE[0] * scale)
    height = int(MASCOT_CANVAS_SIZE[1] * scale)
    render_scale = scale * SMOOTH_RENDER_SCALE
    high_res = Image.new("RGBA", (width * SMOOTH_RENDER_SCALE, height * SMOOTH_RENDER_SCALE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(high_res)
    for shape in butler_mascot_shapes(accent, engine_on=engine_on, mic_on=mic_on, phase=phase, state=state):
        _draw_pillow_shape(draw, shape, render_scale)
    return high_res.resize((width, height), Image.Resampling.LANCZOS)


def _content_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getbbox()
    if bbox is None:
        return (0, 0, image.width, image.height)
    return bbox


def render_mascot_asset_image(
    source: Image.Image,
    phase: int = 0,
    state: str = "idle",
    scale: float = 1.0,
) -> Image.Image:
    width = int(MASCOT_CANVAS_SIZE[0] * scale)
    height = int(MASCOT_CANVAS_SIZE[1] * scale)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sprite = source.convert("RGBA").crop(_content_bbox(source.convert("RGBA")))
    if sprite.width <= 0 or sprite.height <= 0:
        return canvas

    motion = alienware_motion_state(phase, state)
    max_width = int(width * 0.92)
    max_height = int(height * 0.98)
    sprite_scale = min(max_width / sprite.width, max_height / sprite.height)
    target_size = (max(1, int(sprite.width * sprite_scale)), max(1, int(sprite.height * sprite_scale)))
    sprite = sprite.resize(target_size, Image.Resampling.LANCZOS)
    x = (width - sprite.width) // 2
    y = max(0, (height - sprite.height) // 2 + max(-3, min(3, motion["bob"] // 2)))
    canvas.alpha_composite(sprite, (x, y))
    alpha = canvas.getchannel("A")
    canvas.putalpha(alpha.point(lambda value: 255 if value >= 96 else 0))
    return canvas


def butler_mascot_shapes(
    accent: str,
    engine_on: bool,
    mic_on: bool,
    phase: int = 0,
    state: str = "idle",
) -> list[dict[str, object]]:
    engine_color = accent if engine_on else "#51616e"
    mic_color = "#7fdcff" if mic_on else "#c94f64"
    motion = alienware_motion_state(phase, state)
    body_bob = motion["bob"]
    pulse = motion["pulse"]
    glow = [
        {
            "name": "animated_glow_ring",
            "kind": "oval",
            "coords": (23 - pulse, 16 - pulse, 137 + pulse, 141 + pulse),
            "fill": "",
            "outline": accent,
            "width": motion["glow_width"],
        }
    ]
    body = [
        {"name": "companion_shadow", "kind": "oval", "coords": (34, 145, 126, 162), "fill": "#03070b", "outline": ""},
        {"name": "back_glow", "kind": "oval", "coords": (23, 16, 137, 141), "fill": "#08131b", "outline": ""},
        {"name": "coat_back", "kind": "oval", "coords": (37, 67, 123, 151), "fill": "#0b141d", "outline": "#23394a", "width": 1},
        {"name": "soft_jacket", "kind": "polygon", "coords": (47, 86, 67, 78, 80, 104, 93, 78, 113, 86, 126, 147, 34, 147), "fill": "#111d28", "outline": "#2f5063", "width": 1},
        {"name": "shirt_glow", "kind": "polygon", "coords": (68, 82, 92, 82, 101, 143, 59, 143), "fill": "#eef7fb", "outline": ""},
        {"name": "accent_cravat", "kind": "polygon", "coords": (67, 90, 79, 99, 68, 109, 62, 99, 80, 99, 98, 99, 92, 90, 81, 99, 93, 109), "fill": accent, "outline": ""},
        {"name": "face", "kind": "oval", "coords": (42, 26, 118, 98), "fill": "#e4c9ad", "outline": "#f3ddc3", "width": 1},
        {"name": "soft_hair", "kind": "polygon", "coords": (40, 43, 56, 23, 82, 18, 112, 32, 122, 54, 106, 48, 88, 39, 71, 48, 56, 43, 45, 58), "fill": "#202a34", "outline": ""},
        {"name": "hair_swoop", "kind": "arc", "coords": (49, 19, 110, 72), "start": 24, "extent": 122, "outline": "#334150", "width": 5},
        {"name": "visor", "kind": "arc", "coords": (48, 48, 112, 78), "start": 186, "extent": 168, "outline": "#17242f", "width": 7},
        {"name": "listening_eye", "kind": "oval", "coords": (60, 57, 70, 67), "fill": engine_color, "outline": ""},
        {"name": "muted_eye", "kind": "oval", "coords": (91, 57, 101, 67), "fill": mic_color, "outline": ""},
        {"name": "smile", "kind": "arc", "coords": (62, 67, 98, 89), "start": 205, "extent": 130, "outline": "#26323a", "width": 2},
        {"name": "left_sleeve", "kind": "oval", "coords": (26, 92, 58, 138), "fill": "#101a24", "outline": "#2f5063", "width": 1},
        {"name": "right_sleeve", "kind": "oval", "coords": (102, 92, 134, 138), "fill": "#101a24", "outline": "#2f5063", "width": 1},
        {"name": "left_hand", "kind": "oval", "coords": (28, 125, 48, 145), "fill": "#e4c9ad", "outline": ""},
        {"name": "right_hand", "kind": "oval", "coords": (112, 125, 132, 145), "fill": "#e4c9ad", "outline": ""},
        {"name": "status_core", "kind": "oval", "coords": (74, 119, 86, 131), "fill": "#d9a441", "outline": ""},
        {"name": "accent_trim_left", "kind": "line", "coords": (62, 88, 44, 139), "fill": accent, "width": 2},
        {"name": "accent_trim_right", "kind": "line", "coords": (98, 88, 116, 139), "fill": accent, "width": 2},
    ]
    shadow = body[0]
    floating_body = [_shift_shape(shape, dy=body_bob) for shape in body[1:]]
    return [shadow, *glow, *floating_body]


def header_emblem_shapes(accent: str, phase: int = 0, state: str = "idle") -> list[dict[str, object]]:
    motion = alienware_motion_state(phase, state)
    pulse = max(1, motion["pulse"] // 2)
    bob = max(-2, min(2, motion["bob"] // 2))
    return [
        {
            "name": "header_glow",
            "kind": "oval",
            "coords": (4 - pulse, 3 - pulse + bob, 54 + pulse, 39 + pulse + bob),
            "fill": "",
            "outline": accent,
            "width": max(1, motion["glow_width"]),
        },
        {"name": "header_head", "kind": "oval", "coords": (12, 7 + bob, 46, 35 + bob), "fill": "#101821", "outline": "#2f5063", "width": 1},
        {"name": "header_chin", "kind": "polygon", "coords": (18, 29 + bob, 29, 39 + bob, 40, 29 + bob), "fill": "#101821", "outline": "#2f5063", "width": 1},
        {"name": "header_visor", "kind": "arc", "coords": (15, 15 + bob, 43, 29 + bob), "start": 190, "extent": 160, "outline": "#17242f", "width": 4},
        {"name": "header_status_eye", "kind": "oval", "coords": (25, 19 + bob, 33, 27 + bob), "fill": accent, "outline": ""},
    ]
