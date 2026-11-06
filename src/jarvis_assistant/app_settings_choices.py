from __future__ import annotations

from dataclasses import dataclass

from .audio import InputDevice
from .speech import TextToSpeech, best_available_voice_name


DEFAULT_MICROPHONE_LABEL = "System default microphone"
APPEARANCE_RESET_VALUES = {
    "ui_style": "hybrid",
    "accent_color": "cyan",
    "custom_accent_color": "",
    "mascot_size": "normal",
    "mascot_opacity_percent": "94",
    "compact_mode": False,
    "reduce_glow": False,
}
SETTINGS_SECTION_TITLES = ["Local AI", "Voice", "Automation", "Diagnostics", "Appearance / QoL", "Audit"]
VOICE_OPTION_VALUES = {
    "tts_engines": ["Piper Neural", "Windows SAPI"],
    "voice_rates": ["145", "155", "165", "175", "185"],
    "wake_sensitivity": ["Low", "Normal", "High"],
}
APPEARANCE_OPTION_VALUES = {
    "ui_styles": ["hybrid", "chatrtx", "jarvis", "minimal"],
    "accent_colors": ["cyan", "green", "gold", "red", "purple", "blue", "custom"],
    "mascot_sizes": ["small", "normal", "large"],
    "mascot_opacity": ["75", "85", "94", "100"],
}


@dataclass(frozen=True)
class MicrophoneOptions:
    labels: list[str]
    label_to_index: dict[str, int | None]
    selected_label: str


@dataclass(frozen=True)
class VoiceChoiceUpdate:
    voice_values: list[str]
    piper_voice_values: list[str]
    voice_choice: str
    piper_voice_choice: str
    engine_label: str
    rate_choice: str
    settings_updates: dict[str, str]


def microphone_options(devices: list[InputDevice], selected_index: int | None) -> MicrophoneOptions:
    labels = [DEFAULT_MICROPHONE_LABEL]
    label_to_index: dict[str, int | None] = {DEFAULT_MICROPHONE_LABEL: None}
    selected_label = DEFAULT_MICROPHONE_LABEL
    for device in devices:
        labels.append(device.label)
        label_to_index[device.label] = device.index
        if device.index == selected_index:
            selected_label = device.label
    return MicrophoneOptions(labels=labels, label_to_index=label_to_index, selected_label=selected_label)


def selected_microphone(
    label: str,
    label_to_index: dict[str, int | None],
    devices: list[InputDevice],
) -> tuple[int | None, str]:
    device_index = label_to_index.get(label)
    for device in devices:
        if device.index == device_index:
            return device_index, device.name
    return device_index, DEFAULT_MICROPHONE_LABEL


def output_device_choice(output_devices: list[str], saved_output_device: str) -> tuple[list[str], str]:
    devices = [TextToSpeech.DEFAULT_OUTPUT] + output_devices
    selected = saved_output_device if saved_output_device in devices else TextToSpeech.DEFAULT_OUTPUT
    return devices, selected


def voice_choice_update(voices: list[str], piper_voices: list[str], settings: object) -> VoiceChoiceUpdate:
    voice_values = [TextToSpeech.DEFAULT_VOICE] + voices
    settings_updates: dict[str, str] = {}
    saved_piper_voice = getattr(settings, "piper_voice_name")
    saved_voice = getattr(settings, "tts_voice_name")

    if saved_piper_voice in piper_voices:
        piper_voice_choice = saved_piper_voice
    elif piper_voices:
        piper_voice_choice = piper_voices[0]
        settings_updates["piper_voice_name"] = piper_voice_choice
    else:
        piper_voice_choice = saved_piper_voice

    if saved_voice in voice_values:
        voice_choice = saved_voice
    else:
        voice_choice = best_available_voice_name(voices)
        settings_updates["tts_voice_name"] = voice_choice

    return VoiceChoiceUpdate(
        voice_values=voice_values,
        piper_voice_values=piper_voices,
        voice_choice=voice_choice,
        piper_voice_choice=piper_voice_choice,
        engine_label=getattr(settings, "tts_engine"),
        rate_choice=str(getattr(settings, "tts_rate")),
        settings_updates=settings_updates,
    )


def appearance_settings_update(
    *,
    ui_style: str,
    accent_color: str,
    custom_accent_color: str,
    mascot_size: str,
    mascot_opacity_percent: str,
    compact_mode: bool,
    reduce_glow: bool,
) -> dict[str, object]:
    opacity = int(mascot_opacity_percent or str(APPEARANCE_RESET_VALUES["mascot_opacity_percent"])) / 100
    return {
        "ui_style": ui_style or str(APPEARANCE_RESET_VALUES["ui_style"]),
        "accent_color": accent_color or str(APPEARANCE_RESET_VALUES["accent_color"]),
        "custom_accent_color": custom_accent_color.strip(),
        "mascot_size": mascot_size or str(APPEARANCE_RESET_VALUES["mascot_size"]),
        "mascot_opacity": opacity,
        "compact_mode": compact_mode,
        "reduce_glow": reduce_glow,
    }


def appearance_reset_values() -> dict[str, object]:
    return dict(APPEARANCE_RESET_VALUES)


def settings_section_titles() -> list[str]:
    return list(SETTINGS_SECTION_TITLES)


def voice_option_values() -> dict[str, list[str]]:
    return {key: list(values) for key, values in VOICE_OPTION_VALUES.items()}


def appearance_option_values() -> dict[str, list[str]]:
    return {key: list(values) for key, values in APPEARANCE_OPTION_VALUES.items()}
