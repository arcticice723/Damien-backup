from __future__ import annotations

from typing import Any

from .app_settings_choices import (
    microphone_options,
    output_device_choice,
    selected_microphone,
    voice_choice_update,
)
from .app_helpers import sensitivity_value, tts_engine_label, tts_engine_value
from .audio import list_input_device_info
from .config import load_settings, update_settings
from .speech import (
    TextToSpeech,
    best_available_voice_name,
    list_piper_voices,
    list_speech_output_devices,
    list_speech_voices,
)


def voice_profile_settings_update(voice_name: str, piper_voice_name: str, rate: str, volume: float) -> dict[str, object]:
    return {
        "tts_voice_name": voice_name,
        "piper_voice_name": piper_voice_name,
        "tts_rate": int(rate or TextToSpeech.DEFAULT_RATE),
        "tts_volume": max(0.0, min(1.0, float(volume))),
    }


def voice_volume_settings_update(percent: float) -> dict[str, object]:
    return {"tts_volume": max(0.0, min(1.0, float(percent) / 100.0))}


def voice_volume_percent_text(volume: float) -> str:
    return f"{int(round(max(0.0, min(1.0, float(volume))) * 100))}%"


class VoiceSettingsController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def refresh_microphone_devices(self) -> None:
        app = self.app
        app.microphone_devices = list_input_device_info()
        options = microphone_options(app.microphone_devices, app.settings.microphone_device_index)
        app.microphone_labels = options.label_to_index
        app.microphone_box.configure(values=options.labels)
        app.microphone_choice.set(options.selected_label)

    def save_selected_microphone(self) -> None:
        app = self.app
        label = app.microphone_choice.get()
        device_index, device_name = selected_microphone(label, app.microphone_labels, app.microphone_devices)
        try:
            app.recorder.set_device(device_index)
            update_settings({"microphone_device_index": device_index, "microphone_device_name": device_name})
            app.settings = load_settings()
            if app.transcriber is not None:
                app.transcriber.close()
            app.transcriber = None
            app._log_voice(f"microphone_selected: index={device_index}; name={device_name!r}")
            app.mic_status.set(f"Microphone: selected {device_name}")
            if app.wake_detector and app.wake_detector.is_running():
                app._pause_wake_detector("microphone changed")
                app._resume_wake_detector("microphone changed")
        except Exception as exc:
            app.events.put(("speech_error", str(exc)))

    def refresh_output_devices(self) -> None:
        app = self.app
        devices, selected_output = output_device_choice(list_speech_output_devices(), app.settings.output_device_name)
        app.output_box.configure(values=devices)
        app.output_choice.set(selected_output)

    def refresh_voice_choices(self) -> None:
        app = self.app
        choices = voice_choice_update(list_speech_voices(), list_piper_voices(), app.settings)
        app.voice_box.configure(values=choices.voice_values)
        app.piper_voice_box.configure(values=choices.piper_voice_values)
        app.piper_voice_choice.set(choices.piper_voice_choice)
        app.voice_choice.set(choices.voice_choice)
        if choices.settings_updates:
            update_settings(choices.settings_updates)
            app.settings = load_settings()
        app.tts_engine_choice.set(tts_engine_label(app.settings.tts_engine))
        app.voice_rate_choice.set(str(app.settings.tts_rate))
        app.voice_volume_choice.set(round(app.settings.tts_volume * 100))
        app.voice_volume_display.set(voice_volume_percent_text(app.settings.tts_volume))

    def save_selected_tts_engine(self) -> None:
        app = self.app
        engine = tts_engine_value(app.tts_engine_choice.get())
        update_settings({"tts_engine": engine})
        app.settings = load_settings()
        app.tts = None
        label = tts_engine_label(engine)
        app.tts_status.set(f"Voice: {label}")
        app.voice_summary.set(f"Voice engine: {label}")
        app._log_voice(f"tts_engine_selected: {engine!r}")

    def save_selected_output_device(self) -> None:
        app = self.app
        output_device = app.output_choice.get() or TextToSpeech.DEFAULT_OUTPUT
        update_settings({"output_device_name": output_device})
        app.settings = load_settings()
        app.tts = None
        app.tts_status.set(f"Voice: output set to {output_device}")
        app.voice_summary.set(f"Output: {output_device}")
        app._log_voice(f"tts_output_selected: {output_device!r}")

    def save_selected_voice_profile(self) -> None:
        app = self.app
        voice_name = app.voice_choice.get() or TextToSpeech.DEFAULT_VOICE
        piper_voice_name = app.piper_voice_choice.get() or TextToSpeech.DEFAULT_PIPER_VOICE
        rate = app.voice_rate_choice.get() or str(TextToSpeech.DEFAULT_RATE)
        update_settings(voice_profile_settings_update(voice_name, piper_voice_name, rate, app.settings.tts_volume))
        app.settings = load_settings()
        app.tts = None
        engine_label = tts_engine_label(app.settings.tts_engine)
        active_voice = piper_voice_name if app.settings.tts_engine == TextToSpeech.ENGINE_PIPER else voice_name
        app.tts_status.set(f"Voice: {engine_label} - {active_voice} at {int(rate)}")
        app.voice_summary.set(f"{engine_label}: {active_voice}")
        app._log_voice(
            f"tts_profile_selected: engine={app.settings.tts_engine!r}; sapi_voice={voice_name!r}; "
            f"piper_voice={piper_voice_name!r}; rate={int(rate)}"
        )

    def save_selected_voice_volume(self) -> None:
        app = self.app
        update = voice_volume_settings_update(app.voice_volume_choice.get())
        update_settings(update)
        app.settings = load_settings()
        app.tts = None
        text = f"Voice volume: {voice_volume_percent_text(app.settings.tts_volume)}"
        app.voice_volume_choice.set(round(app.settings.tts_volume * 100))
        app.voice_volume_display.set(voice_volume_percent_text(app.settings.tts_volume))
        app.tts_status.set(text)
        app.voice_summary.set(text)
        app._log_voice(f"tts_volume_selected: {app.settings.tts_volume:.2f}")

    def use_best_voice(self) -> None:
        app = self.app
        piper_voices = list_piper_voices()
        best_voice = (
            TextToSpeech.DEFAULT_PIPER_VOICE
            if TextToSpeech.DEFAULT_PIPER_VOICE in piper_voices
            else (piper_voices[0] if piper_voices else TextToSpeech.DEFAULT_PIPER_VOICE)
        )
        app.tts_engine_choice.set(tts_engine_label(TextToSpeech.ENGINE_PIPER))
        app.piper_voice_choice.set(best_voice)
        app.voice_rate_choice.set(str(TextToSpeech.DEFAULT_RATE))
        update_settings({"tts_engine": TextToSpeech.ENGINE_PIPER})
        self.save_selected_voice_profile()

    def use_best_windows_voice(self) -> None:
        app = self.app
        best_voice = best_available_voice_name(list_speech_voices())
        app.tts_engine_choice.set(tts_engine_label(TextToSpeech.ENGINE_SAPI))
        app.voice_choice.set(best_voice)
        app.voice_rate_choice.set(str(TextToSpeech.DEFAULT_RATE))
        update_settings({"tts_engine": TextToSpeech.ENGINE_SAPI})
        self.save_selected_voice_profile()

    def save_wake_sensitivity(self) -> None:
        app = self.app
        value = sensitivity_value(app.wake_sensitivity_choice.get())
        update_settings({"wake_sensitivity": value})
        app.settings = load_settings()
        app._log_voice(f"wake_sensitivity_updated: {value}")
        if app.wake_detector and app.wake_detector.is_running():
            app._pause_wake_detector("wake sensitivity changed")
            app._resume_wake_detector("wake sensitivity changed")
        app.wake_summary.set(f"Wake sensitivity: {app.wake_sensitivity_choice.get()}")

    def save_speech_help(self) -> None:
        app = self.app
        vocabulary = list(dict.fromkeys(
            term.strip() for term in app.speech_vocabulary_choice.get().split(",") if term.strip()
        ))[:40]
        corrections: dict[str, str] = {}
        for pair in app.speech_corrections_choice.get().split(";"):
            if "=" not in pair:
                continue
            source, target = (part.strip() for part in pair.split("=", 1))
            if source and target:
                corrections[source] = target
        update_settings({"speech_vocabulary": vocabulary, "speech_corrections": corrections})
        app.settings = load_settings()
        if app.transcriber is not None:
            app.transcriber.close()
        app.transcriber = None
        app.speech_vocabulary_choice.set(", ".join(app.settings.speech_vocabulary))
        app.speech_corrections_choice.set("; ".join(
            f"{source}={target}" for source, target in app.settings.speech_corrections.items()
        ))
        app.stt_settings_status.set("Saved. Applies to the next transcription.")
        app._log_voice(f"speech_help_updated: terms={len(vocabulary)}; corrections={len(corrections)}")
