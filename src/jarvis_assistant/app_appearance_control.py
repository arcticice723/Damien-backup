from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .app_settings_choices import appearance_reset_values, appearance_settings_update
from .config import load_settings, update_settings


def theme_mode_update(enabled: bool) -> dict[str, str]:
    return {"theme_mode": "dark" if enabled else "light"}


class AppearanceController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def toggle_dark_mode(self) -> None:
        app = self.app
        update = theme_mode_update(app.dark_mode.get())
        update_settings(update)
        app.settings = load_settings()
        self.apply_appearance_refresh()
        app.status.set(f"{update['theme_mode'].title()} mode enabled.")

    def save_appearance_settings(self) -> None:
        app = self.app
        update_settings(
            appearance_settings_update(
                ui_style=app.ui_style_choice.get(),
                accent_color=app.accent_color_choice.get(),
                custom_accent_color=app.custom_accent_choice.get(),
                mascot_size=app.mascot_size_choice.get(),
                mascot_opacity_percent=app.mascot_opacity_choice.get(),
                compact_mode=app.compact_mode.get(),
                reduce_glow=app.reduce_glow.get(),
            )
        )
        app.settings = load_settings()
        self.apply_appearance_refresh()
        app.status.set("Appearance settings applied.")

    def reset_appearance_settings(self) -> None:
        app = self.app
        values = appearance_reset_values()
        app.ui_style_choice.set(str(values["ui_style"]))
        app.accent_color_choice.set(str(values["accent_color"]))
        app.custom_accent_choice.set(str(values["custom_accent_color"]))
        app.mascot_size_choice.set(str(values["mascot_size"]))
        app.mascot_opacity_choice.set(str(values["mascot_opacity_percent"]))
        app.compact_mode.set(bool(values["compact_mode"]))
        app.reduce_glow.set(bool(values["reduce_glow"]))
        self.save_appearance_settings()

    def apply_appearance_refresh(self) -> None:
        app = self.app
        app._style()
        self.apply_text_surface_theme()
        self.apply_input_widget_theme()
        app._refresh_header_emblem_canvas()
        app._recreate_mascot_widget()

    def apply_text_surface_theme(self) -> None:
        app = self.app
        for surface in app.text_surfaces:
            surface.configure(
                bg=app.colors["surface_bg"],
                fg=app.colors["surface_text"],
                insertbackground=app.colors["surface_text"],
            )
        if hasattr(app, "history_view"):
            app.history_view.tag_configure("speaker", foreground=app.colors["speaker"])
            app.history_view.tag_configure("message", foreground=app.colors["message"])

    def apply_input_widget_theme(self) -> None:
        def visit(widget: tk.Misc) -> None:
            for child in widget.winfo_children():
                if isinstance(child, ttk.Entry):
                    child.configure(style="TEntry")
                elif isinstance(child, ttk.Combobox):
                    child.configure(style="TCombobox")
                visit(child)

        visit(self.app)
