from __future__ import annotations

import threading
from collections.abc import Callable


class ProactiveLoop:
    def __init__(
        self,
        check: Callable[[], list[str]],
        emit: Callable[[str, str], None],
        interval_seconds: float,
        should_stop: Callable[[], bool],
        on_error: Callable[[Exception], None] | None = None,
        sleep: Callable[[float], None] | None = None,
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        self.check = check
        self.emit = emit
        self.interval_seconds = interval_seconds
        self.should_stop = should_stop
        self.on_error = on_error
        self.sleep = sleep
        self.wait = wait
        self.stop_requested = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self.run_forever, daemon=True).start()

    def run_forever(self) -> None:
        while not self._should_stop():
            self.run_once()

    def stop(self) -> None:
        self.stop_requested.set()

    def run_once(self) -> None:
        try:
            for message in self.check():
                self.emit("proactive_notice", message)
        except Exception as exc:
            if self.on_error is not None:
                self.on_error(exc)
        if not self._should_stop():
            self._wait_interval()

    def _should_stop(self) -> bool:
        return self.stop_requested.is_set() or self.should_stop()

    def _wait_interval(self) -> None:
        if self.wait is not None:
            self.wait(self.interval_seconds)
        elif self.sleep is not None:
            self.sleep(self.interval_seconds)
        else:
            self.stop_requested.wait(self.interval_seconds)
