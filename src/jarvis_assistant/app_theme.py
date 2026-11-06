from __future__ import annotations

from .mascot_ui import accent_hex, hybrid_dark_theme


def theme_colors(settings: object) -> dict[str, str]:
    if getattr(settings, "theme_mode") != "dark":
        return {
            "bg": "#eef3f7",
            "panel": "#ffffff",
            "panel_alt": "#f7fafc",
            "panel_deep": "#f1f5f9",
            "line": "#d5dee7",
            "text": "#17202a",
            "muted": "#52616f",
            "accent": accent_hex(getattr(settings, "accent_color"), getattr(settings, "custom_accent_color")),
            "accent_dark": "#1f6f5a",
            "warning": "#9b6a2f",
            "danger": "#8c2f39",
            "blue": "#2d6f9f",
            "input_bg": "#ffffff",
            "input_text": "#17202a",
            "surface_bg": "#f7fafc",
            "surface_text": "#17202a",
            "speaker": "#0f3f5f",
            "message": "#17202a",
        }
    accent = accent_hex(getattr(settings, "accent_color"), getattr(settings, "custom_accent_color"))
    return hybrid_dark_theme(accent=accent, style=getattr(settings, "ui_style"), reduce_glow=getattr(settings, "reduce_glow"))
