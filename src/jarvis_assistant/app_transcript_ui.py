from __future__ import annotations

import tkinter as tk
from typing import Any


def transcript_speaker_prefix(speaker: str) -> str:
    return f"{speaker}:\n"


class TranscriptController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def append_line(self, speaker: str, text: str) -> None:
        app = self.app
        app.history_view.configure(state="normal")
        speaker_tags = ["speaker"]
        body_tag = "message"
        if speaker == "You":
            speaker_tags.append("user_speaker")
            body_tag = "user_message"
        elif speaker == "Damien":
            speaker_tags.append("assistant_speaker")
        app.history_view.insert(tk.END, transcript_speaker_prefix(speaker), tuple(speaker_tags))
        body_start = app.history_view.index(tk.END)
        app.history_view.insert(tk.END, f"{text}\n\n", (body_tag,))
        if speaker == "Damien":
            body_end = app.history_view.index(tk.END)
            app.history_view.mark_set("current_assistant_body_start", body_start)
            app.history_view.mark_gravity("current_assistant_body_start", tk.LEFT)
            app.history_view.mark_set("current_assistant_body_end", body_end)
            app.history_view.mark_gravity("current_assistant_body_end", tk.RIGHT)
            app.current_assistant_start = body_start
            app.current_assistant_end = body_end
            if app.streaming_active:
                app.debug_assistant_block_count += 1
                app._set_debug_streaming_status()
                app._log_stream_debug(
                    f"ui_write: method=append_message_block; speaker=Damien; "
                    f"assistant_blocks={app.debug_assistant_block_count}"
                )
        app.history_view.configure(state="disabled")
        app.history_view.see(tk.END)

    def replace_last_assistant_line(self, text: str) -> None:
        app = self.app
        if app.current_assistant_start is None or app.current_assistant_end is None:
            self.append_line("Damien", text)
            return
        app.history_view.configure(state="normal")
        app.history_view.delete("current_assistant_body_start", "current_assistant_body_end")
        app.history_view.insert("current_assistant_body_start", f"{text}\n\n", ("message",))
        body_end = app.history_view.index(f"current_assistant_body_start + {len(text) + 2} chars")
        app.history_view.mark_set("current_assistant_body_end", body_end)
        app.current_assistant_start = app.history_view.index("current_assistant_body_start")
        app.current_assistant_end = app.history_view.index("current_assistant_body_end")
        if app.streaming_active:
            app._set_debug_streaming_status()
            app._log_stream_debug(
                f"ui_write: method=update_assistant_stream_block; chars={len(text)}; "
                f"assistant_blocks={app.debug_assistant_block_count}"
            )
        app.history_view.configure(state="disabled")
        app.history_view.see(tk.END)
