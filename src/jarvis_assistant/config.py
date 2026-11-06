from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .local_models import DEFAULT_OLLAMA_MODEL
from .runtime import APP_ROOT

PROJECT_ROOT = APP_ROOT


@dataclass(frozen=True)
class Settings:
    assistant_name: str
    ollama_base_url: str
    remote_brain_enabled: bool
    remote_brain_base_url: str
    model: str
    thinking_mode: str
    temperature: float
    num_ctx: int
    enable_tools: bool
    free_only_mode: bool
    enable_cloud_provider: bool
    cloud_provider: str
    cloud_model: str
    automation_risk_mode: str
    voice_persona_style: str
    theme_mode: str
    ui_style: str
    accent_color: str
    custom_accent_color: str
    mascot_size: str
    mascot_opacity: float
    compact_mode: bool
    reduce_glow: bool
    tool_audit_log_enabled: bool
    enable_retrieval: bool
    enable_long_term_memory: bool
    save_raw_audio: bool
    microphone_device_index: int | None
    microphone_device_name: str
    output_device_name: str
    tts_engine: str
    tts_voice_name: str
    piper_voice_name: str
    tts_rate: int
    tts_volume: float
    remote_control_enabled: bool
    remote_control_host: str
    remote_control_port: int
    remote_control_pin: str
    discord_bot_enabled: bool
    discord_bot_token: str
    discord_bot_allowed_channel_ids: list[int]
    start_minimized_to_tray: bool
    mascot_widget_enabled: bool
    mascot_widget_x: int | None
    mascot_widget_y: int | None
    screen_access_enabled: bool
    screen_capture_dir: Path
    wake_phrase: str
    wake_phrase_variants: list[str]
    wake_sensitivity: float
    wake_phrase_enabled: bool
    wake_acknowledgement_sound_enabled: bool
    wake_acknowledgement_mode: str
    wake_listening_cue: str
    wake_thinking_cue: str
    wake_check_seconds: float
    wake_command_seconds: float
    launch_at_sign_in: bool
    wake_whisper_model: str
    wake_whisper_device: str
    wake_whisper_compute_type: str
    wake_whisper_beam_size: int
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    whisper_beam_size: int
    speech_vocabulary: list[str]
    speech_corrections: dict[str, str]
    crunchyroll_profile_name: str
    crunchyroll_browser_automation_enabled: bool
    crunchyroll_browser_port: int
    proactive_enabled: bool
    proactive_voice_enabled: bool
    reminder_check_seconds: int
    approved_documents_dir: Path
    approved_apps_path: Path
    history_path: Path
    memory_path: Path
    audit_log_path: Path


def load_settings(path: Path | None = None) -> Settings:
    settings_path = path or PROJECT_ROOT / "config" / "settings.json"
    if not settings_path.exists():
        _write_default_settings(settings_path)
    payload = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    return Settings(
        assistant_name=payload.get("assistant_name", "Damien"),
        ollama_base_url=payload.get("ollama_base_url", "http://127.0.0.1:11434"),
        remote_brain_enabled=bool(payload.get("remote_brain_enabled", False)),
        remote_brain_base_url=str(payload.get("remote_brain_base_url", "")).strip().rstrip("/"),
        model=payload.get("model", DEFAULT_OLLAMA_MODEL),
        thinking_mode=payload.get("thinking_mode", "auto"),
        temperature=float(payload.get("temperature", 0.25)),
        num_ctx=int(payload.get("num_ctx", 2048)),
        enable_tools=bool(payload.get("enable_tools", True)),
        free_only_mode=bool(payload.get("free_only_mode", True)),
        enable_cloud_provider=bool(payload.get("enable_cloud_provider", False)),
        cloud_provider=payload.get("cloud_provider", "openai"),
        cloud_model=payload.get("cloud_model", "gpt-4.1-mini"),
        automation_risk_mode=payload.get("automation_risk_mode", "low_risk_auto"),
        voice_persona_style=payload.get("voice_persona_style", "cinematic"),
        theme_mode=payload.get("theme_mode", "dark"),
        ui_style=payload.get("ui_style", "hybrid"),
        accent_color=payload.get("accent_color", "cyan"),
        custom_accent_color=payload.get("custom_accent_color", ""),
        mascot_size=payload.get("mascot_size", "normal"),
        mascot_opacity=max(0.55, min(1.0, float(payload.get("mascot_opacity", 0.94)))),
        compact_mode=bool(payload.get("compact_mode", False)),
        reduce_glow=bool(payload.get("reduce_glow", False)),
        tool_audit_log_enabled=bool(payload.get("tool_audit_log_enabled", True)),
        enable_retrieval=bool(payload.get("enable_retrieval", True)),
        enable_long_term_memory=bool(payload.get("enable_long_term_memory", False)),
        save_raw_audio=bool(payload.get("save_raw_audio", False)),
        microphone_device_index=_optional_int(payload.get("microphone_device_index")),
        microphone_device_name=payload.get("microphone_device_name", ""),
        output_device_name=payload.get("output_device_name", "System default output"),
        tts_engine=payload.get("tts_engine", "piper"),
        tts_voice_name=payload.get("tts_voice_name", "auto"),
        piper_voice_name=payload.get("piper_voice_name", "en_US-ryan-high"),
        tts_rate=int(payload.get("tts_rate", 155)),
        tts_volume=float(payload.get("tts_volume", 1.0)),
        remote_control_enabled=bool(payload.get("remote_control_enabled", True)),
        remote_control_host=payload.get("remote_control_host", "0.0.0.0"),
        remote_control_port=int(payload.get("remote_control_port", 8765)),
        remote_control_pin=payload.get("remote_control_pin", "auto"),
        discord_bot_enabled=bool(payload.get("discord_bot_enabled", False)),
        discord_bot_token=payload.get("discord_bot_token", ""),
        discord_bot_allowed_channel_ids=_int_list(payload.get("discord_bot_allowed_channel_ids", [])),
        start_minimized_to_tray=bool(payload.get("start_minimized_to_tray", True)),
        mascot_widget_enabled=bool(payload.get("mascot_widget_enabled", True)),
        mascot_widget_x=_optional_int(payload.get("mascot_widget_x")),
        mascot_widget_y=_optional_int(payload.get("mascot_widget_y")),
        screen_access_enabled=bool(payload.get("screen_access_enabled", True)),
        screen_capture_dir=PROJECT_ROOT / payload.get("screen_capture_dir", "screenshots"),
        wake_phrase=payload.get("wake_phrase", "hey damien"),
        wake_phrase_variants=_wake_variants(payload),
        wake_sensitivity=float(payload.get("wake_sensitivity", 0.72)),
        wake_phrase_enabled=bool(payload.get("wake_phrase_enabled", True)),
        wake_acknowledgement_sound_enabled=bool(payload.get("wake_acknowledgement_sound_enabled", False)),
        wake_acknowledgement_mode=payload.get("wake_acknowledgement_mode", "voice"),
        wake_listening_cue=payload.get("wake_listening_cue", "yes?"),
        wake_thinking_cue=payload.get("wake_thinking_cue", "hmmm..."),
        wake_check_seconds=float(payload.get("wake_check_seconds", 2.5)),
        wake_command_seconds=float(payload.get("wake_command_seconds", 5.0)),
        launch_at_sign_in=bool(payload.get("launch_at_sign_in", False)),
        wake_whisper_model=payload.get("wake_whisper_model", "tiny"),
        wake_whisper_device=payload.get("wake_whisper_device", "cpu"),
        wake_whisper_compute_type=payload.get("wake_whisper_compute_type", "int8"),
        wake_whisper_beam_size=max(1, int(payload.get("wake_whisper_beam_size", 1))),
        whisper_model=payload.get("whisper_model", "small"),
        whisper_device=payload.get("whisper_device", "cpu"),
        whisper_compute_type=payload.get("whisper_compute_type", "int8"),
        whisper_beam_size=max(1, int(payload.get("whisper_beam_size", 5))),
        speech_vocabulary=_string_list(payload.get("speech_vocabulary", [])),
        speech_corrections=_string_map(payload.get("speech_corrections", {})),
        crunchyroll_profile_name=payload.get("crunchyroll_profile_name", ""),
        crunchyroll_browser_automation_enabled=bool(payload.get("crunchyroll_browser_automation_enabled", True)),
        crunchyroll_browser_port=int(payload.get("crunchyroll_browser_port", 9223)),
        proactive_enabled=bool(payload.get("proactive_enabled", True)),
        proactive_voice_enabled=bool(payload.get("proactive_voice_enabled", True)),
        reminder_check_seconds=max(5, int(payload.get("reminder_check_seconds", 30))),
        approved_documents_dir=PROJECT_ROOT / payload.get("approved_documents_dir", "approved_documents"),
        approved_apps_path=PROJECT_ROOT / "config" / "approved_apps.json",
        history_path=PROJECT_ROOT / "history" / "conversation.jsonl",
        memory_path=PROJECT_ROOT / "memory" / "long_term_memory.jsonl",
        audit_log_path=PROJECT_ROOT / "logs" / "audit.jsonl",
    )


def update_settings(values: dict, path: Path | None = None) -> None:
    settings_path = path or PROJECT_ROOT / "config" / "settings.json"
    if not settings_path.exists():
        _write_default_settings(settings_path)
    payload = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    payload.update(values)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _int_list(value: object) -> list[int]:
    if not value:
        return []
    if not isinstance(value, list):
        return [int(value)]
    return [int(item) for item in value if item != ""]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))[:40]


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(source).strip(): str(target).strip()
        for source, target in value.items()
        if str(source).strip() and str(target).strip()
    }


def _write_default_settings(settings_path: Path) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(_default_settings(), indent=2) + "\n", encoding="utf-8")


def _default_settings() -> dict[str, object]:
    return {
        "assistant_name": "Damien",
        "ollama_base_url": "http://127.0.0.1:11434",
        "remote_brain_enabled": False,
        "remote_brain_base_url": "",
        "model": DEFAULT_OLLAMA_MODEL,
        "thinking_mode": "auto",
        "temperature": 0.25,
        "num_ctx": 2048,
        "enable_tools": True,
        "free_only_mode": True,
        "enable_cloud_provider": False,
        "cloud_provider": "openai",
        "cloud_model": "gpt-4.1-mini",
        "automation_risk_mode": "low_risk_auto",
        "voice_persona_style": "cinematic",
        "theme_mode": "dark",
        "ui_style": "hybrid",
        "accent_color": "cyan",
        "custom_accent_color": "",
        "mascot_size": "normal",
        "mascot_opacity": 0.94,
        "compact_mode": False,
        "reduce_glow": False,
        "tool_audit_log_enabled": True,
        "enable_retrieval": True,
        "enable_long_term_memory": False,
        "save_raw_audio": False,
        "microphone_device_index": None,
        "microphone_device_name": "System default microphone",
        "output_device_name": "System default output",
        "tts_engine": "piper",
        "tts_voice_name": "auto",
        "piper_voice_name": "en_US-ryan-high",
        "tts_rate": 155,
        "tts_volume": 1.0,
        "remote_control_enabled": True,
        "remote_control_host": "0.0.0.0",
        "remote_control_port": 8765,
        "remote_control_pin": "auto",
        "discord_bot_enabled": False,
        "discord_bot_token": "",
        "discord_bot_allowed_channel_ids": [],
        "start_minimized_to_tray": True,
        "mascot_widget_enabled": True,
        "mascot_widget_x": None,
        "mascot_widget_y": None,
        "screen_access_enabled": True,
        "screen_capture_dir": "screenshots",
        "wake_phrase": "hey damien",
        "wake_phrase_variants": ["hey damien", "hey damian", "damien", "hey daemon"],
        "wake_sensitivity": 0.72,
        "wake_phrase_enabled": True,
        "wake_acknowledgement_sound_enabled": False,
        "wake_acknowledgement_mode": "voice",
        "wake_listening_cue": "yes?",
        "wake_thinking_cue": "hmmm...",
        "wake_check_seconds": 2.5,
        "wake_command_seconds": 5.0,
        "launch_at_sign_in": False,
        "wake_whisper_model": "tiny",
        "wake_whisper_device": "cpu",
        "wake_whisper_compute_type": "int8",
        "wake_whisper_beam_size": 1,
        "whisper_model": "small",
        "whisper_device": "cpu",
        "whisper_compute_type": "int8",
        "whisper_beam_size": 5,
        "speech_vocabulary": [],
        "speech_corrections": {},
        "crunchyroll_profile_name": "",
        "crunchyroll_browser_automation_enabled": True,
        "crunchyroll_browser_port": 9223,
        "proactive_enabled": True,
        "proactive_voice_enabled": True,
        "reminder_check_seconds": 30,
        "approved_documents_dir": "approved_documents",
    }


def _wake_variants(payload: dict) -> list[str]:
    variants = payload.get("wake_phrase_variants", [])
    if not isinstance(variants, list):
        variants = []
    values = [str(value).strip().lower() for value in variants if str(value).strip()]
    defaults = ["hey damien", "hey damian", "damien", "hey daemon"]
    for value in defaults:
        if value not in values:
            values.append(value)
    return values
