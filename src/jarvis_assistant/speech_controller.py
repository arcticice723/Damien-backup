from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterable

from .app_helpers import pop_ready_speech_segments
from .speech import smooth_text_for_speech


class SpeechController:
    def __init__(
        self,
        tts_factory: Callable[[], object],
        emit: Callable[[str, object], None],
        log: Callable[[str], None],
        resume_wake: Callable[[str], None],
        pause_wake: Callable[[str], None] | None = None,
        start_thread: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        self.tts_factory = tts_factory
        self.emit = emit
        self.log = log
        self.resume_wake = resume_wake
        self.pause_wake = pause_wake or (lambda _reason: None)
        self.start_thread = start_thread or _start_daemon_thread
        self.tts: object | None = None
        self.stream_queue: queue.Queue[str | None] | None = None
        self.stream_thread: object | None = None
        self.stream_buffer = ""
        self.stop_requested = threading.Event()

    def start_streaming(self) -> None:
        self._request_stop()
        self.pause_wake("tts stream started")
        self.stream_buffer = ""
        self.stop_requested.clear()
        self.stream_queue = queue.Queue()
        self.stream_thread = self.start_thread(self._streaming_worker)

    def queue_streaming_text(self, text: str) -> None:
        if self.stream_queue is None or self.stop_requested.is_set():
            return
        self.stream_buffer += text
        segments, self.stream_buffer = pop_ready_speech_segments(self.stream_buffer)
        for spoken in _spoken_segments(segments):
            self.stream_queue.put(spoken)

    def finish_streaming(self) -> None:
        if self.stream_queue is None:
            return
        segments, self.stream_buffer = pop_ready_speech_segments(self.stream_buffer, force=True)
        for spoken in _spoken_segments(segments):
            self.stream_queue.put(spoken)
        self.stream_queue.put(None)

    def drain_pending_segments(self) -> Iterable[str]:
        if self.stream_queue is None:
            return []
        values: list[str] = []
        while True:
            try:
                item = self.stream_queue.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                values.append(item)
        return values

    def speak(self, text: str) -> None:
        self._request_stop()
        self.pause_wake("tts started")
        self.start_thread(lambda: self._speak_worker(text))

    def speak_short_cue(self, text: str) -> None:
        value = text.strip()
        if value:
            self.start_thread(lambda: self._short_cue_worker(value))

    def stop(self) -> None:
        self._request_stop()

    def _request_stop(self) -> None:
        self.stop_requested.set()
        if self.stream_queue is not None:
            self._clear_streaming_state()
            self.stream_queue.put(None)
        if self.tts is not None:
            try:
                self.tts.stop()
                self.log("tts_interrupted")
            except Exception as exc:
                self.log(f"tts_interrupt_failed: {exc}")

    def _tts(self) -> object:
        if self.tts is None:
            self.tts = self.tts_factory()
        return self.tts

    def _drain_stream_queue(self) -> None:
        if self.stream_queue is None:
            return
        while True:
            try:
                self.stream_queue.get_nowait()
            except queue.Empty:
                return

    def _clear_streaming_state(self) -> None:
        self._drain_stream_queue()
        self.stream_buffer = ""

    def _streaming_worker(self) -> None:
        try:
            tts = self._tts()
            while not self.stop_requested.is_set():
                if self.stream_queue is None:
                    return
                try:
                    segment = self.stream_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if segment is None:
                    break
                self.log(f"tts_stream_segment_started: chars={len(segment)}")
                tts.speak(segment, should_stop=self.stop_requested.is_set)
                self.log("tts_stream_segment_finished")
            self.resume_wake("tts stream finished")
            self.emit("speech_done", None)
        except Exception as exc:
            self.log(f"tts_stream_failed: {exc}")
            self.emit("speech_error", str(exc))
        finally:
            self.stream_queue = None
            self.stream_thread = None
            self.stream_buffer = ""

    def _speak_worker(self, text: str) -> None:
        try:
            self.stop_requested.clear()
            tts = self._tts()
            self.log("tts_started")
            tts.speak(text, should_stop=self.stop_requested.is_set)
            self.log("tts_finished")
            self.resume_wake("tts finished")
            self.emit("speech_done", None)
        except Exception as exc:
            self.log(f"tts_failed: {exc}")
            self.emit("speech_error", str(exc))

    def _short_cue_worker(self, text: str) -> None:
        try:
            tts = self.tts_factory()
            self.log(f"tts_cue_started: {text!r}")
            tts.speak(text, timeout_seconds=8.0)
            self.log("tts_cue_finished")
        except Exception as exc:
            self.log(f"tts_cue_failed: {exc}")


def _spoken_segments(segments: list[str]) -> list[str]:
    return [spoken for spoken in (smooth_text_for_speech(segment) for segment in segments) if spoken]


def _start_daemon_thread(target: Callable[[], None]) -> threading.Thread:
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread
