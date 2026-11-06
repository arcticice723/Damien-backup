from __future__ import annotations

import os
import re
import threading
import gc
from pathlib import Path
from collections.abc import Mapping

from .runtime import APP_ROOT


os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


class WhisperTranscriber:
    MODEL_IDLE_UNLOAD_SECONDS = 300
    DEFAULT_INITIAL_PROMPT = (
        "The speaker is talking to Damien, a local desktop assistant. "
        "Common names and commands include Damien, Discord, Apex Legends, Marvel Rivals, "
        "Unreal Engine, Roblox Studio, Crunchyroll, iTunes, Hermes, Ollama, open, launch, "
        "continue, call, lobby, project, playlist, clipboard, notes, settings, and system status."
    )

    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        language: str = "en",
        beam_size: int = 1,
        initial_prompt: str | None = None,
        vocabulary: list[str] | None = None,
        corrections: Mapping[str, str] | None = None,
    ) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Install faster-whisper before using speech recognition.") from exc

        self.language = language or "en"
        self.beam_size = max(1, int(beam_size))
        terms = list(dict.fromkeys(str(term).strip() for term in (vocabulary or []) if str(term).strip()))[:40]
        self.initial_prompt = initial_prompt or self.DEFAULT_INITIAL_PROMPT
        if terms:
            self.initial_prompt += " User vocabulary and names: " + ", ".join(terms) + "."
        self.corrections = {
            str(source).strip(): str(target).strip()
            for source, target in (corrections or {}).items()
            if str(source).strip() and str(target).strip()
        }
        self.requested_device = device
        self.requested_compute_type = compute_type
        self.active_device = device
        self.active_compute_type = compute_type
        self.active_model = model_name
        self.status_message = f"Speech recognition loaded on {device}/{compute_type}."
        self._model_lock = threading.RLock()
        self._idle_timer: threading.Timer | None = None
        self._unload_generation = 0
        self._model_class = WhisperModel
        try:
            self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        except Exception as exc:
            if device.lower() == "cuda" and _looks_like_cuda_load_failure(exc):
                self.active_device = "cpu"
                self.active_compute_type = "int8"
                self.status_message = (
                    "CUDA speech libraries were unavailable, so Damien fell back to CPU/int8 speech recognition."
                )
                self.model = self._load_model_with_cached_fallback(WhisperModel, model_name, "cpu", "int8")
            else:
                self.model = self._load_model_with_cached_fallback(
                    WhisperModel,
                    model_name,
                    device,
                    compute_type,
                    exc,
                    try_requested=False,
                )

    def _load_model_with_cached_fallback(
        self,
        model_class: object,
        model_name: str,
        device: str,
        compute_type: str,
        original_error: Exception | None = None,
        try_requested: bool = True,
    ) -> object:
        exc = original_error
        if try_requested:
            try:
                model = model_class(model_name, device=device, compute_type=compute_type)
                self.active_model = model_name
                return model
            except Exception as load_error:
                exc = load_error
        if model_name == "base":
            raise original_error or exc or RuntimeError("Speech model failed to load.")
        model = model_class("base", device=device, compute_type=compute_type)
        self.active_model = "base"
        self.status_message = (
            f"Speech recognition could not load {model_name}, so Damien fell back to base on {device}/{compute_type}."
        )
        return model

    def transcribe(self, wav_path: Path) -> str:
        with self._model_lock:
            if self._idle_timer is not None:
                self._idle_timer.cancel()
                self._idle_timer = None
            self._ensure_model()
            segments, _info = self.model.transcribe(
                str(wav_path),
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 350},
                condition_on_previous_text=False,
                initial_prompt=self.initial_prompt,
            )
            text = clean_transcription_text(" ".join(segment.text.strip() for segment in segments), self.corrections)
            self._unload_generation += 1
            generation = self._unload_generation
            self._idle_timer = threading.Timer(
                self.MODEL_IDLE_UNLOAD_SECONDS,
                self._unload_if_idle,
                args=(generation,),
            )
            self._idle_timer.daemon = True
            self._idle_timer.start()
            return text

    def _ensure_model(self) -> None:
        if self.model is not None:
            return
        model_class = self._model_class
        try:
            self.model = model_class(self.active_model, device=self.active_device, compute_type=self.active_compute_type)
        except Exception as exc:
            if self.active_device.lower() == "cuda" and _looks_like_cuda_load_failure(exc):
                self.active_device = "cpu"
                self.active_compute_type = "int8"
                self.status_message = "CUDA speech libraries were unavailable, so Damien fell back to CPU/int8 speech recognition."
                self.model = self._load_model_with_cached_fallback(model_class, self.active_model, "cpu", "int8")
            else:
                self.model = self._load_model_with_cached_fallback(
                    model_class, self.active_model, self.active_device, self.active_compute_type, exc
                )

    def unload(self) -> None:
        with self._model_lock:
            self._unload_generation += 1
            self._idle_timer = None
            self.model = None
            gc.collect()

    def _unload_if_idle(self, generation: int) -> None:
        with self._model_lock:
            if generation != self._unload_generation:
                return
            self._idle_timer = None
            self.model = None
            gc.collect()

    def close(self) -> None:
        self._unload_generation += 1
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        self.unload()


def clean_transcription_text(text: str, corrections: Mapping[str, str] | None = None) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"^(?:thanks\s+for\s+watching|thank\s+you\s+for\s+watching)[.!?\s]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:subtitle[s]?\s+by\s+.+)[.!?\s]*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bday\s+mien\b", "Damien", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bdamian\b", "Damien", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bdaemon\b", "Damien", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bdamon\b", "Damien", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhermes\b", "Hermes", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bapex legend\b", "Apex Legends", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bmarvel rival\b", "Marvel Rivals", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\broll\s+blocks\s+studio\b", "Roblox Studio", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\brow\s+blocks\s+studio\b", "Roblox Studio", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\broblox\s+studios\b", "Roblox Studio", cleaned, flags=re.IGNORECASE)
    for source, target in sorted((corrections or {}).items(), key=lambda item: len(item[0]), reverse=True):
        pattern = rf"(?<!\w){re.escape(source.strip())}(?!\w)"
        cleaned = re.sub(pattern, lambda _match, value=target: value, cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


class TextToSpeech:
    DEFAULT_OUTPUT = "System default output"
    ENGINE_PIPER = "piper"
    ENGINE_SAPI = "sapi"
    DEFAULT_VOICE = "auto"
    DEFAULT_PIPER_VOICE = "en_US-ryan-high"
    DEFAULT_RATE = 155
    DEFAULT_VOLUME = 1.0

    def __init__(
        self,
        output_device_name: str = DEFAULT_OUTPUT,
        voice_name: str = DEFAULT_VOICE,
        rate: int = DEFAULT_RATE,
        volume: float = DEFAULT_VOLUME,
        engine: str = ENGINE_PIPER,
        piper_voice_name: str = DEFAULT_PIPER_VOICE,
    ) -> None:
        self.output_device_name = output_device_name
        self.voice_name = voice_name
        self.rate = rate
        self.volume = volume
        self.engine_name = engine or self.ENGINE_PIPER
        self.piper_voice_name = piper_voice_name or self.DEFAULT_PIPER_VOICE
        self.engine = None
        self.lock = threading.Lock()
        self._playback_stop = threading.Event()

    def speak(self, text: str, should_stop=None, timeout_seconds: float = 45.0) -> None:
        if should_stop and should_stop():
            return
        error: list[BaseException] = []

        def worker() -> None:
            comtypes_module = None
            try:
                try:
                    import comtypes

                    comtypes.CoInitialize()
                    comtypes_module = comtypes
                except Exception:
                    comtypes_module = None
                self._playback_stop.clear()
                spoken = smooth_text_for_speech(text)
                with self.lock:
                    if self.engine_name == self.ENGINE_PIPER and self._piper_voice_paths() is not None:
                        try:
                            self._speak_with_piper(spoken, should_stop=should_stop)
                        except Exception:
                            self._speak_with_sapi(spoken)
                    else:
                        self._speak_with_sapi(spoken)
            except BaseException as exc:
                error.append(exc)
            finally:
                self.engine = None
                if comtypes_module is not None:
                    try:
                        comtypes_module.CoUninitialize()
                    except Exception:
                        pass

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout_seconds)
        if thread.is_alive():
            self.stop()
            raise RuntimeError("Text-to-speech timed out.")
        if error:
            raise RuntimeError(str(error[0]))

    def stop(self) -> None:
        self._playback_stop.set()
        try:
            import sounddevice as sd

            sd.stop()
        except Exception:
            pass
        if self.engine is not None and hasattr(self.engine, "stop"):
            self.engine.stop()

    def _speak_with_piper(self, text: str, should_stop=None) -> None:
        import numpy as np
        import sounddevice as sd
        from piper.config import SynthesisConfig
        from piper.voice import PiperVoice

        paths = self._piper_voice_paths()
        if paths is None:
            raise RuntimeError(f"Piper voice not found: {self.piper_voice_name}")
        model_path, config_path = paths
        self.engine = PiperVoice.load(model_path, config_path)
        syn_config = SynthesisConfig(
            length_scale=max(0.84, min(1.16, TextToSpeech.DEFAULT_RATE / max(120, min(210, int(self.rate))))),
            volume=max(0.0, min(1.0, float(self.volume))),
        )
        chunks = []
        sample_rate = 22050
        for chunk in self.engine.synthesize(text, syn_config=syn_config):
            if self._playback_stop.is_set() or (should_stop and should_stop()):
                return
            sample_rate = chunk.sample_rate
            chunks.append(chunk.audio_float_array.astype(np.float32))
        if not chunks:
            return
        audio = np.concatenate(chunks)
        device = _sounddevice_output_device(self.output_device_name)
        with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32", device=device) as stream:
            frame_count = int(sample_rate * 0.1)
            for start in range(0, len(audio), frame_count):
                if self._playback_stop.is_set() or (should_stop and should_stop()):
                    break
                stream.write(audio[start : start + frame_count])

    def _speak_with_sapi(self, text: str) -> None:
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("Install pyttsx3 before using text-to-speech.") from exc
        self.engine = pyttsx3.init()
        self._select_output_device(self.engine)
        self._apply_voice_profile(self.engine)
        self.engine.say(text)
        self.engine.runAndWait()

    def _piper_voice_paths(self) -> tuple[Path, Path] | None:
        voice_dir = APP_ROOT / "assets" / "voices"
        model_path = voice_dir / f"{self.piper_voice_name}.onnx"
        config_path = voice_dir / f"{self.piper_voice_name}.onnx.json"
        if model_path.exists() and config_path.exists():
            return model_path, config_path
        return None

    def _select_output_device(self, engine: object) -> None:
        if not self.output_device_name or self.output_device_name == self.DEFAULT_OUTPUT:
            return
        token = _speech_output_token(self.output_device_name)
        if token is None:
            raise RuntimeError(f"Speech output device not found: {self.output_device_name}")
        try:
            engine.proxy._driver._tts.AudioOutput = token
        except AttributeError as exc:
            raise RuntimeError("Selected speech output is not supported by this TTS driver.") from exc

    def _apply_voice_profile(self, engine: object) -> None:
        voice = _select_voice(engine, self.voice_name)
        if voice is not None:
            engine.setProperty("voice", voice.id)
        engine.setProperty("rate", max(120, min(210, int(self.rate))))
        engine.setProperty("volume", max(0.0, min(1.0, float(self.volume))))


def list_speech_voices() -> list[str]:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        return [voice.name for voice in engine.getProperty("voices")]
    except Exception:
        return []


def list_piper_voices() -> list[str]:
    voice_dir = APP_ROOT / "assets" / "voices"
    if not voice_dir.exists():
        return []
    return sorted(path.name.removesuffix(".onnx") for path in voice_dir.glob("*.onnx"))


def best_available_voice_name(voices: list[str]) -> str:
    if not voices:
        return TextToSpeech.DEFAULT_VOICE
    preferred_fragments = (
        "Guy",
        "David",
        "Mark",
        "George",
        "Ryan",
        "Jenny",
        "Aria",
        "Zira",
    )
    for fragment in preferred_fragments:
        for voice in voices:
            if fragment.lower() in voice.lower():
                return voice
    return voices[0]


def smooth_text_for_speech(text: str) -> str:
    spoken = text.strip()
    spoken = re.sub(r"```.*?```", " ", spoken, flags=re.DOTALL)
    spoken = re.sub(r"`([^`]+)`", r"\1", spoken)
    spoken = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", spoken)
    spoken = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", spoken)
    spoken = re.sub(r"^\s*>\s?", "", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"(?<!\w)(?:\*\*|__)(.+?)(?:\*\*|__)(?!\w)", r"\1", spoken)
    spoken = re.sub(r"(?<!\w)(?:\*|_)(.+?)(?:\*|_)(?!\w)", r"\1", spoken)
    spoken = re.sub(r"[*_#~]{1,}", " ", spoken)
    spoken = re.sub(r"\bI am\b", "I'm", spoken)
    spoken = re.sub(r"\bI will\b", "I'll", spoken)
    spoken = re.sub(r"\bI have\b", "I've", spoken)
    spoken = re.sub(r"\bYou are\b", "You're", spoken)
    spoken = re.sub(r"\bThat is\b", "That's", spoken)
    spoken = re.sub(r"\bIt is\b", "It's", spoken)
    spoken = re.sub(r"\bDo not\b", "Don't", spoken)
    spoken = re.sub(r"\bI do not\b", "I don't", spoken)
    spoken = re.sub(r"\bYou do not\b", "You don't", spoken)
    spoken = re.sub(r"\bI would\b", "I'd", spoken)
    spoken = re.sub(r"\bI could\b", "I could", spoken)
    spoken = re.sub(r"\bHere is\b", "Here's", spoken)
    spoken = re.sub(r"\bThere is\b", "There's", spoken)
    spoken = re.sub(r"\bLet us\b", "Let's", spoken)
    spoken = re.sub(r"\bcan not\b", "can't", spoken, flags=re.IGNORECASE)
    spoken = re.sub(r"\s+", " ", spoken)
    spoken = spoken.replace(" - ", ". ")
    return spoken.strip()


def _select_voice(engine: object, voice_name: str):
    voices = engine.getProperty("voices")
    selected_name = voice_name
    if not selected_name or selected_name == TextToSpeech.DEFAULT_VOICE:
        selected_name = best_available_voice_name([voice.name for voice in voices])
    for voice in voices:
        if voice.name == selected_name:
            return voice
    return None


def list_speech_output_devices() -> list[str]:
    try:
        category = _speech_output_category()
        return [token.GetDescription() for token in category.EnumerateTokens()]
    except Exception:
        return []


def _speech_output_token(device_name: str):
    try:
        category = _speech_output_category()
        for token in category.EnumerateTokens():
            if token.GetDescription() == device_name:
                return token
    except Exception:
        return None
    return None


def _sounddevice_output_device(device_name: str):
    if not device_name or device_name == TextToSpeech.DEFAULT_OUTPUT:
        return None
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        for index, device in enumerate(devices):
            if device.get("max_output_channels", 0) > 0 and device.get("name") == device_name:
                return index
    except Exception:
        return None
    return None


def _speech_output_category():
    import comtypes.client

    category = comtypes.client.CreateObject("SAPI.SpObjectTokenCategory")
    category.SetId(r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\AudioOutput", False)
    return category


def _looks_like_cuda_load_failure(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = ("cublas", "cudnn", "cuda", "cublas64", "dll", "cannot be loaded")
    return any(marker in text for marker in markers)
