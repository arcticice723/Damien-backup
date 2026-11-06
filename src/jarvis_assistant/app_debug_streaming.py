from __future__ import annotations

import threading
import time
from typing import Any


def debug_streaming_scenarios() -> list[tuple[str, list[str]]]:
    return [
        ("debug delta stream", ["Another", " test", "!"]),
        ("debug full partial stream", ["Another", "Another test", "Another test!"]),
    ]


class DebugStreamingController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def start_test(self) -> None:
        threading.Thread(target=self.app._debug_streaming_worker, daemon=True).start()

    def run_worker(self) -> None:
        app = self.app
        for label, chunks in debug_streaming_scenarios():
            app.events.put(("debug_start_stream", label))
            for chunk in chunks:
                time.sleep(0.25)
                app.events.put(("stream_text", chunk))
            time.sleep(0.25)
            app.events.put(("done", None))
            time.sleep(0.6)

    def set_status(self) -> None:
        app = self.app
        if app.debug_streaming_enabled:
            app.debug_streaming_status.set(
                f"Damien blocks this response: {app.debug_assistant_block_count}"
            )

    def log(self, message: str) -> None:
        self.app._log_connection(f"stream: {message}")
