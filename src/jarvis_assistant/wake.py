from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from difflib import SequenceMatcher

from .audio import RecordingResult, record_fixed_wav_with_level
from .speech import WhisperTranscriber


class WakePhraseDetector:
    class CommandGate:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._active = False

        def try_begin(self) -> bool:
            with self._lock:
                if self._active:
                    return False
                self._active = True
                return True

        def finish(self) -> None:
            with self._lock:
                self._active = False

    def __init__(
        self,
        wake_phrase: str,
        wake_phrase_variants: list[str] | None,
        wake_sensitivity: float,
        on_detected: Callable[[], None],
        on_status: Callable[[str], None],
        check_seconds: float,
        model_name: str,
        device: str,
        compute_type: str,
        microphone_device_index: int | None = None,
        beam_size: int = 1,
        on_audio_level: Callable[[RecordingResult], None] | None = None,
        on_transcription: Callable[[str, bool, str], None] | None = None,
    ) -> None:
        self.wake_phrases = self._phrase_variants(wake_phrase, wake_phrase_variants or [])
        self.wake_sensitivity = max(0.0, min(1.0, wake_sensitivity))
        self.on_detected = on_detected
        self.on_status = on_status
        self.check_seconds = check_seconds
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = max(1, int(beam_size))
        self.microphone_device_index = microphone_device_index
        self.on_audio_level = on_audio_level
        self.on_transcription = on_transcription
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._transcriber: WhisperTranscriber | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def _run(self) -> None:
        self._transcriber = None
        self.on_status("Listening")
        try:
            while not self._stop.is_set():
                try:
                    result = record_fixed_wav_with_level(self.check_seconds, device_index=self.microphone_device_index)
                    if self.on_audio_level:
                        self.on_audio_level(result)
                    if result.near_silence:
                        self.on_status("Listening")
                        continue
                    if self._transcriber is None:
                        self._transcriber = WhisperTranscriber(
                            self.model_name,
                            self.device,
                            self.compute_type,
                            beam_size=self.beam_size,
                        )
                    text = self._transcriber.transcribe(result.path)
                    matched, matched_phrase = self.matches(text)
                    if self.on_transcription:
                        self.on_transcription(text, matched, matched_phrase)
                    if matched:
                        self.on_status("Heard wake phrase")
                        self.on_detected()
                        time.sleep(1.0)
                    else:
                        self.on_status("Listening")
                except Exception as exc:
                    self.on_status(f"Error: {exc}")
                    return
        finally:
            if self._transcriber is not None:
                self._transcriber.close()
                self._transcriber = None

    def matches(self, text: str) -> tuple[bool, str]:
        normalized = self._normalize(text)
        if not normalized:
            return False, ""
        for phrase in self.wake_phrases:
            if phrase and phrase in normalized:
                return True, phrase
        threshold = self._similarity_threshold(self.wake_sensitivity)
        words = normalized.split()
        single_word_candidates = words
        two_word_candidates = [" ".join(words[index : index + 2]) for index in range(max(0, len(words) - 1))]
        for phrase in self.wake_phrases:
            phrase_word_count = len(phrase.split())
            phrase_candidates = []
            if len(words) >= phrase_word_count:
                phrase_candidates.append(normalized)
            if phrase_word_count > 1:
                phrase_candidates.extend(two_word_candidates)
            else:
                phrase_candidates.extend(single_word_candidates)
            if phrase.startswith("hey "):
                phrase_candidates = [candidate for candidate in phrase_candidates if candidate.startswith("hey ")]
            if any(SequenceMatcher(None, phrase, candidate).ratio() >= threshold for candidate in phrase_candidates):
                return True, phrase
        return False, ""

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()

    @classmethod
    def _phrase_variants(cls, wake_phrase: str, variants: list[str]) -> list[str]:
        values = [cls._normalize(wake_phrase)]
        values.extend(cls._normalize(value) for value in variants)
        defaults = ["hey damien", "hey damian", "hey daemon"]
        values.extend(defaults)
        deduped: list[str] = []
        for value in values:
            if value and " " in value and value not in deduped:
                deduped.append(value)
        return deduped

    @staticmethod
    def _similarity_threshold(sensitivity: float) -> float:
        return 0.90 - (max(0.0, min(1.0, sensitivity)) * 0.30)
