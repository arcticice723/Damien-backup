from __future__ import annotations

import tkinter as tk
from typing import Any

from PIL import Image, ImageTk

from .app_helpers import draw_canvas_shape as _draw_canvas_shape
from .app_helpers import short_status_text as _short_status_text
from .config import load_settings, update_settings
from .mascot_ui import (
    FLOATING_MASCOT_SHOW_LABELS,
    MASCOT_ASSET_RELATIVE_PATH,
    MASCOT_CANVAS_SIZE,
    TRANSPARENT_MASCOT_BG,
    header_emblem_shapes,
    mascot_dimensions,
    mascot_start_position,
    mascot_widget_status,
    render_mascot_asset_image,
    smooth_mascot_image,
)
from .runtime import APP_ROOT


def assistant_motion_state(*, streaming_active: bool, wake_running: bool, mic_enabled: bool) -> str:
    if streaming_active:
        return "thinking"
    if wake_running:
        return "listening"
    if mic_enabled:
        return "idle"
    return "muted"


class MascotController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def sync_widget(self) -> None:
        app = self.app
        if app.mascot_widget_enabled.get():
            self.show_widget()
        else:
            self.hide_widget()

    def recreate_widget(self) -> None:
        app = self.app
        if app.mascot_window is None or not app.mascot_window.winfo_exists():
            return
        self.hide_widget()
        self.show_widget()

    def show_widget(self) -> None:
        app = self.app
        if app.mascot_window is not None and app.mascot_window.winfo_exists():
            app.mascot_window.deiconify()
            self.refresh_widget()
            return
        widget = tk.Toplevel(app)
        app.mascot_window = widget
        widget.title("Damien Widget")
        widget.overrideredirect(True)
        widget.attributes("-topmost", True)
        try:
            widget.attributes("-alpha", app.settings.mascot_opacity)
        except tk.TclError:
            pass
        widget.configure(bg=TRANSPARENT_MASCOT_BG)
        try:
            widget.attributes("-transparentcolor", TRANSPARENT_MASCOT_BG)
        except tk.TclError:
            pass
        width, height, app.mascot_scale = mascot_dimensions(app.settings.mascot_size)
        x, y = self.start_position(width, height, widget.winfo_screenwidth(), widget.winfo_screenheight())
        widget.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(widget, bg=TRANSPARENT_MASCOT_BG, highlightthickness=0, borderwidth=0)
        frame.pack(fill="both", expand=True)
        canvas_width = int(MASCOT_CANVAS_SIZE[0] * app.mascot_scale)
        canvas_height = int(MASCOT_CANVAS_SIZE[1] * app.mascot_scale)
        app.mascot_canvas = tk.Canvas(
            frame,
            width=canvas_width,
            height=canvas_height,
            bg=TRANSPARENT_MASCOT_BG,
            highlightthickness=0,
            borderwidth=0,
        )
        app.mascot_canvas.pack(pady=(2, 0))
        text_targets: list[tk.Misc] = []
        if FLOATING_MASCOT_SHOW_LABELS:
            status_label = tk.Label(
                frame,
                textvariable=app.mascot_status,
                fg=app.colors["cyan"],
                bg=TRANSPARENT_MASCOT_BG,
                font=("Segoe UI", 11, "bold"),
                width=18,
            )
            status_label.pack(pady=(0, 2))
            heard_label = tk.Label(
                frame,
                textvariable=app.mascot_last_heard,
                fg=app.colors["text"],
                bg=TRANSPARENT_MASCOT_BG,
                font=("Segoe UI", 10, "bold"),
                width=25,
            )
            heard_label.pack(pady=(0, 4))
            text_targets = [status_label, heard_label]

        for target in (widget, frame, app.mascot_canvas, *text_targets):
            target.bind("<ButtonPress-1>", app._start_mascot_drag)
            target.bind("<B1-Motion>", app._drag_mascot_widget)
            target.bind("<ButtonRelease-1>", app._save_mascot_position)
            target.bind("<Double-Button-1>", lambda _event: app._restore_window())
            target.bind("<Button-3>", lambda _event: app._toggle_mic_value())
        widget.protocol("WM_DELETE_WINDOW", app._hide_mascot_widget)
        self.refresh_widget()

    def motion_state(self) -> str:
        app = self.app
        wake_running = bool(app.wake_enabled.get() and app.wake_detector and app.wake_detector.is_running())
        return assistant_motion_state(
            streaming_active=app.streaming_active,
            wake_running=wake_running,
            mic_enabled=app.mic_enabled.get(),
        )

    def refresh_header_emblem_canvas(self) -> None:
        app = self.app
        canvas = app.header_emblem_canvas
        if canvas is None:
            return
        canvas.configure(bg=app.colors["panel_deep"])
        canvas.delete("all")
        for shape in header_emblem_shapes(app.colors["accent"], phase=app.header_animation_phase, state=self.motion_state()):
            _draw_canvas_shape(canvas, shape)

    def animate_header_emblem(self) -> None:
        app = self.app
        if app.quitting:
            return
        app.header_animation_phase = (app.header_animation_phase + 1) % 96
        self.refresh_header_emblem_canvas()
        app.after(110, app._animate_header_emblem)

    def send_command(self) -> None:
        app = self.app
        text = app.mascot_command.get().strip()
        if not text:
            return
        app.mascot_command.set("")
        app.mascot_last_heard.set("Sent: " + _short_status_text(text, 22))
        app._handle_user_text(text)

    def hide_widget(self) -> None:
        app = self.app
        if app.mascot_window is not None and app.mascot_window.winfo_exists():
            app.mascot_window.destroy()
        app.mascot_window = None
        app.mascot_canvas = None
        app.mascot_photo = None

    def toggle_widget(self) -> None:
        app = self.app
        enabled = app.mascot_widget_enabled.get()
        update_settings({"mascot_widget_enabled": enabled})
        app.settings = load_settings()
        self.sync_widget()
        app.status.set("Desktop mascot widget enabled." if enabled else "Desktop mascot widget hidden.")

    def start_drag(self, event: tk.Event) -> None:
        app = self.app
        app._mascot_drag_offset = (
            (int(event.x_root) - app.mascot_window.winfo_x(), int(event.y_root) - app.mascot_window.winfo_y())
            if app.mascot_window
            else (0, 0)
        )

    def drag_widget(self, event: tk.Event) -> None:
        app = self.app
        if app.mascot_window is None:
            return
        dx, dy = app._mascot_drag_offset
        app.mascot_window.geometry(f"+{int(event.x_root) - dx}+{int(event.y_root) - dy}")

    def save_position(self) -> None:
        app = self.app
        if app.mascot_window is None or not app.mascot_window.winfo_exists():
            return
        x, y = app.mascot_window.winfo_x(), app.mascot_window.winfo_y()
        if app._mascot_last_saved_position == (x, y):
            return
        app._mascot_last_saved_position = (x, y)
        update_settings({"mascot_widget_x": x, "mascot_widget_y": y})
        app.settings = load_settings()

    def start_position(self, width: int, height: int, screen_width: int, screen_height: int) -> tuple[int, int]:
        app = self.app
        x, y = mascot_start_position(
            app.settings.mascot_widget_x,
            app.settings.mascot_widget_y,
            width,
            height,
            screen_width,
            screen_height,
        )
        app._mascot_last_saved_position = (x, y)
        return x, y

    def refresh_widget(self) -> None:
        app = self.app
        if app.mascot_window is None or not app.mascot_window.winfo_exists():
            return
        mic_on = app.mic_enabled.get()
        wake_on = app.wake_enabled.get() and app.wake_detector and app.wake_detector.is_running()
        engine_on = app.ollama_connected.get()
        label, accent = mascot_widget_status(
            streaming_active=app.streaming_active,
            wake_on=bool(wake_on),
            mic_on=mic_on,
            engine_on=engine_on,
        )
        app.mascot_status.set(label)
        self.draw_mascot(accent, engine_on=engine_on, mic_on=mic_on)
        app.mascot_window.after(90, app._refresh_mascot_widget)

    def draw_mascot(self, accent: str, engine_on: bool, mic_on: bool) -> None:
        app = self.app
        canvas = app.mascot_canvas
        if canvas is None:
            return
        canvas.delete("all")
        app.mascot_animation_phase = (app.mascot_animation_phase + 1) % 96
        source = self.load_source_image()
        if source is not None:
            image = render_mascot_asset_image(
                source,
                phase=app.mascot_animation_phase,
                state=self.motion_state(),
                scale=app.mascot_scale,
            )
        else:
            image = smooth_mascot_image(
                accent,
                engine_on=engine_on,
                mic_on=mic_on,
                phase=app.mascot_animation_phase,
                state=self.motion_state(),
                scale=app.mascot_scale,
            )
        app.mascot_photo = ImageTk.PhotoImage(image)
        canvas.create_image(0, 0, image=app.mascot_photo, anchor="nw")

    def load_source_image(self) -> Image.Image | None:
        app = self.app
        if app.mascot_source_image is not None:
            return app.mascot_source_image
        asset_path = APP_ROOT / MASCOT_ASSET_RELATIVE_PATH
        try:
            app.mascot_source_image = Image.open(asset_path).convert("RGBA")
        except OSError:
            app._log_connection(f"mascot_asset_missing: {asset_path}")
            return None
        return app.mascot_source_image
