from __future__ import annotations

import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InputDevice:
    index: int
    name: str
    hostapi: str
    max_input_channels: int
    default_samplerate: float

    @property
    def label(self) -> str:
        rate = int(self.default_samplerate) if self.default_samplerate else 0
        rate_text = f", {rate} Hz" if rate else ""
        return f"{self.index}: {self.name} ({self.hostapi}, {self.max_input_channels} ch{rate_text})"


@dataclass(frozen=True)
class RecordingResult:
    path: Path
    device_index: int | None
    device_name: str
    sample_rate: int
    rms: float
    peak: float
    volume_percent: int

    @property
    def near_silence(self) -> bool:
        return self.rms < 0.005 and self.peak < 0.025


class SoundDeviceRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        save_raw_audio: bool = False,
        device_index: int | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.save_raw_audio = save_raw_audio
        self.device_index = device_index
        self._active_device_index: int | None = None
        self._active_sample_rate = sample_rate
        self.last_result: RecordingResult | None = None
        self._frames: list[object] = []
        self._stream = None

    def set_device(self, device_index: int | None) -> None:
        if self._stream is not None:
            raise RuntimeError("Stop the current microphone recording before changing devices.")
        self.device_index = device_index

    def start(self) -> None:
        if self._stream is not None:
            return
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("Install sounddevice before using microphone input.") from exc

        self._frames = []
        last_error: Exception | None = None
        for active_device, active_rate in candidate_input_device_settings(self.device_index, self.sample_rate):
            try:
                self._stream = sd.InputStream(
                    samplerate=active_rate,
                    channels=self.channels,
                    dtype="int16",
                    device=active_device,
                    callback=self._on_audio,
                )
                self._stream.start()
                self._active_device_index = active_device
                self._active_sample_rate = active_rate
                return
            except Exception as exc:
                last_error = exc
                if self._stream is not None:
                    try:
                        self._stream.close()
                    except Exception:
                        pass
                self._stream = None
        if last_error is not None:
            raise last_error
        raise RuntimeError("No usable microphone input device found.")

    def stop_to_wav(self) -> Path:
        self.last_result = self.stop()
        return self.last_result.path

    def stop(self) -> RecordingResult:
        if self._stream is None:
            raise RuntimeError("Recording has not started.")
        self._stream.stop()
        self._stream.close()
        self._stream = None

        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("Install numpy before using microphone input.") from exc

        samples = np.concatenate(self._frames, axis=0) if self._frames else np.empty((0, self.channels), dtype="int16")
        if self.save_raw_audio:
            path = Path("recordings") / "damien_ptt.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path = Path(tempfile.gettempdir()) / "damien_ptt.wav"
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._active_sample_rate)
            wav_file.writeframes(samples.tobytes())
        rms, peak, volume_percent = audio_levels(samples)
        active_device = self._active_device_index
        active_rate = self._active_sample_rate
        self._active_device_index = None
        self._active_sample_rate = self.sample_rate
        return RecordingResult(
            path=path,
            device_index=active_device,
            device_name=device_name(active_device),
            sample_rate=active_rate,
            rms=rms,
            peak=peak,
            volume_percent=volume_percent,
        )

    def _on_audio(self, indata: object, frames: int, time_info: object, status: object) -> None:
        del frames, time_info, status
        self._frames.append(indata.copy())


def record_fixed_wav(
    duration_seconds: float,
    sample_rate: int = 16000,
    channels: int = 1,
    device_index: int | None = None,
) -> Path:
    return record_fixed_wav_with_level(duration_seconds, sample_rate, channels, device_index).path


def record_fixed_wav_with_level(
    duration_seconds: float,
    sample_rate: int = 16000,
    channels: int = 1,
    device_index: int | None = None,
) -> RecordingResult:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError("Install sounddevice before using microphone input.") from exc
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Install numpy before using microphone input.") from exc

    samples = None
    active_device = None
    active_rate = sample_rate
    last_error: Exception | None = None
    for candidate_device, candidate_rate in candidate_input_device_settings(device_index, sample_rate):
        try:
            samples = sd.rec(
                int(duration_seconds * candidate_rate),
                samplerate=candidate_rate,
                channels=channels,
                dtype="int16",
                device=candidate_device,
            )
            sd.wait()
            active_device = candidate_device
            active_rate = candidate_rate
            break
        except Exception as exc:
            last_error = exc
            samples = None
    if samples is None and last_error is not None:
        raise last_error
    if samples is None:
        samples = np.empty((0, channels), dtype="int16")
    path = Path(tempfile.gettempdir()) / f"damien_wake_{int(time.time() * 1000)}.wav"
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(active_rate)
        wav_file.writeframes(samples.tobytes())
    rms, peak, volume_percent = audio_levels(samples)
    return RecordingResult(
        path=path,
        device_index=active_device,
        device_name=device_name(active_device),
        sample_rate=active_rate,
        rms=rms,
        peak=peak,
        volume_percent=volume_percent,
    )


def resolve_input_device_index(device_index: int | None) -> int | None:
    return resolve_input_device_settings(device_index, 16000)[0]


def resolve_input_device_settings(device_index: int | None, preferred_sample_rate: int) -> tuple[int | None, int]:
    candidates = candidate_input_device_settings(device_index, preferred_sample_rate)
    return candidates[0] if candidates else (None, preferred_sample_rate)


def candidate_input_device_settings(device_index: int | None, preferred_sample_rate: int) -> list[tuple[int | None, int]]:
    try:
        import sounddevice as sd
    except ImportError:
        return [(device_index, preferred_sample_rate)]

    candidates: list[tuple[int | None, int]] = []
    if _is_valid_input_device(sd, device_index):
        rate = _valid_input_sample_rate(sd, device_index, preferred_sample_rate)
        if rate is not None:
            candidates.append((device_index, rate))
    for fallback_device in _ranked_input_device_indexes(sd, preferred_sample_rate):
        if fallback_device == device_index:
            continue
        fallback_rate = _valid_input_sample_rate(sd, fallback_device, preferred_sample_rate)
        if fallback_rate is not None:
            candidates.append((fallback_device, fallback_rate))
    if candidates:
        return candidates
    return [(None, preferred_sample_rate)]


def list_input_device_info() -> list[InputDevice]:
    try:
        import sounddevice as sd
    except ImportError:
        return []
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    results: list[InputDevice] = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) > 0:
            hostapi_index = int(device.get("hostapi", -1))
            hostapi = "Unknown host"
            if 0 <= hostapi_index < len(hostapis):
                hostapi = str(hostapis[hostapi_index].get("name", "Unknown host"))
            results.append(
                InputDevice(
                    index=index,
                    name=str(device.get("name", "Unknown input")),
                    hostapi=hostapi,
                    max_input_channels=int(device.get("max_input_channels", 0)),
                    default_samplerate=float(device.get("default_samplerate", 0.0)),
                )
            )
    return results


def _is_valid_input_device(sd: object, device_index: int | None) -> bool:
    if device_index is None:
        try:
            sd.query_devices(kind="input")
            return True
        except Exception:
            return False
    try:
        device = sd.query_devices(device_index)
    except Exception:
        return False
    return int(device.get("max_input_channels", 0)) > 0


def _valid_input_sample_rate(sd: object, device_index: int | None, preferred_sample_rate: int) -> int | None:
    candidate_rates = [preferred_sample_rate]
    if device_index is not None:
        try:
            device = sd.query_devices(device_index)
            default_rate = int(device.get("default_samplerate") or 0)
            if default_rate:
                candidate_rates.append(default_rate)
        except Exception:
            pass
    candidate_rates.extend([48000, 44100, 32000, 22050, 16000, 8000])
    seen: set[int] = set()
    for rate in candidate_rates:
        if rate in seen:
            continue
        seen.add(rate)
        try:
            sd.check_input_settings(device=device_index, channels=1, samplerate=rate, dtype="int16")
            return rate
        except Exception:
            continue
    return None


def _ranked_input_device_indexes(sd: object, preferred_sample_rate: int) -> list[int]:
    devices = list_input_device_info()
    candidates = [
        device for device in devices if _valid_input_sample_rate(sd, device.index, preferred_sample_rate) is not None
    ]
    return [device.index for device in sorted(candidates, key=_input_device_score, reverse=True)]


def _input_device_score(device: InputDevice) -> tuple[int, int, int, int]:
    name = device.name.lower()
    score = 0
    if "microphone" in name or "mic" in name:
        score += 50
    if "headset" in name:
        score += 35
    if "input" in name:
        score += 10
    if "stereo mix" in name:
        score -= 100
    if "steam streaming" in name:
        score -= 40
    if "oculus" in name:
        score -= 10
    if "bthhfenum" in name or "hands-free" in name:
        score += 5
    host_score = 1 if "wasapi" in device.hostapi.lower() else 0
    return score, host_score, device.max_input_channels, -device.index


def list_input_devices() -> list[str]:
    return [device.label for device in list_input_device_info()]


def device_name(device_index: int | None) -> str:
    if device_index is None:
        return "System default microphone"
    for device in list_input_device_info():
        if device.index == device_index:
            return device.name
    return f"Input device {device_index}"


def audio_levels(samples: object) -> tuple[float, float, int]:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Install numpy before using microphone input.") from exc

    array = np.asarray(samples, dtype=np.float32)
    if array.size == 0:
        return 0.0, 0.0, 0
    normalized = array / 32768.0
    rms = float(np.sqrt(np.mean(np.square(normalized))))
    peak = float(np.max(np.abs(normalized)))
    volume_percent = max(0, min(100, int(round(rms * 250))))
    return rms, peak, volume_percent
