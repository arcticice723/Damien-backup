from __future__ import annotations

from tkinter import ttk
from typing import Any


CHAT_STATUS_CARDS = [
    ("LOCAL ENGINE", "local_engine_summary", "accent"),
    ("WAKE", "wake_summary", "blue"),
    ("VOICE", "voice_summary", "warning"),
    ("PRIVACY", "privacy_summary", "accent_dark"),
]


def chat_status_cards() -> list[tuple[str, str, str]]:
    return list(CHAT_STATUS_CARDS)


class DamienChatTabBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, parent: ttk.Frame) -> None:
        app = self.app
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, minsize=260)
        parent.rowconfigure(0, weight=1)
        conversation_frame = ttk.Frame(parent, style="Panel.TFrame")
        conversation_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        conversation_frame.columnconfigure(0, weight=1)
        conversation_frame.rowconfigure(1, weight=1)
        ttk.Label(conversation_frame, text="Conversation", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        app.history_view = app._text_surface(conversation_frame)
        app.history_view.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        app.history_view.tag_configure("speaker", spacing1=14, spacing3=5, font=("Segoe UI", 10, "bold"))
        app.history_view.tag_configure(
            "assistant_speaker", foreground=app.colors["accent"], lmargin1=10, rmargin=34
        )
        app.history_view.tag_configure(
            "user_speaker", foreground=app.colors["blue"], lmargin1=34, rmargin=10, justify="right"
        )
        app.history_view.tag_configure(
            "message",
            spacing3=16,
            lmargin1=18,
            lmargin2=18,
            rmargin=34,
            foreground=app.colors["message"],
            background=app.colors["panel_alt"],
        )
        app.history_view.tag_configure(
            "user_message",
            spacing3=16,
            lmargin1=42,
            lmargin2=42,
            rmargin=12,
            foreground=app.colors["text"],
            background=app.colors["panel_deep"],
            justify="right",
        )

        command_frame = ttk.Frame(parent, style="Panel.TFrame", padding=(0, 2))
        command_frame.grid(row=0, column=1, sticky="nsew")
        command_frame.columnconfigure(0, weight=1)
        command_frame.rowconfigure(9, weight=1)
        ttk.Label(command_frame, text="Systems", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        for row, (title, variable_name, color_key) in enumerate(chat_status_cards(), start=1):
            app._status_card(command_frame, title, getattr(app, variable_name), app.colors[color_key]).grid(
                row=row,
                column=0,
                sticky="ew",
                pady=(0, 8) if row == 1 else 8,
            )
        ttk.Separator(command_frame).grid(row=5, column=0, sticky="ew", pady=12)
        ttk.Button(command_frame, text="Test Microphone", command=app._test_microphone).grid(row=6, column=0, sticky="ew", pady=4)
        ttk.Button(command_frame, text="Test Voice", command=app._test_voice).grid(row=7, column=0, sticky="ew", pady=4)
        ttk.Button(command_frame, text="Voice Diagnostics", command=app._run_voice_diagnostics).grid(row=8, column=0, sticky="ew", pady=4)
        ttk.Label(command_frame, textvariable=app.microphone_volume, style="PanelMuted.TLabel", wraplength=250).grid(
            row=9, column=0, sticky="sew", pady=(12, 0)
        )
        ttk.Button(command_frame, text="Settings", command=app._open_settings_tab).grid(row=10, column=0, sticky="ew", pady=(12, 4))

        input_bar = ttk.Frame(parent, style="Panel.TFrame")
        input_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        input_bar.columnconfigure(0, weight=1)
        app.input_text = ttk.Entry(input_bar)
        app.input_text.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        app.input_text.bind("<Return>", lambda _event: app._send_typed())
        ttk.Button(input_bar, text="Send", command=app._send_typed, style="Accent.TButton").grid(row=0, column=1, padx=(0, 8))
        app.ptt_button = ttk.Button(input_bar, text="Hold to Talk")
        app.ptt_button.grid(row=0, column=2, padx=(0, 8))
        app.ptt_button.bind("<ButtonPress-1>", lambda _event: app._start_recording())
        app.ptt_button.bind("<ButtonRelease-1>", lambda _event: app._stop_recording())
        ttk.Checkbutton(input_bar, text="Mic enabled", variable=app.mic_enabled, command=app._toggle_mic).grid(
            row=0, column=3
        )
        if app.debug_streaming_enabled:
            debug_row = ttk.Frame(parent)
            debug_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            ttk.Button(debug_row, text="Debug Streaming Test", command=app._debug_streaming_test).grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(debug_row, textvariable=app.debug_streaming_status, style="Muted.TLabel").grid(
                row=0, column=1, sticky="w", padx=(10, 0)
            )
