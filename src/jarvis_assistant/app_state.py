from __future__ import annotations

import os
import tkinter as tk
from tkinter import scrolledtext
from typing import Any

from .app_helpers import sensitivity_label, tts_engine_label
from .runtime import APP_ROOT
from .wake import WakePhraseDetector


def mascot_opacity_percent_text(opacity: float) -> str:
    return str(int(round(opacity * 100)))


def wake_summary_text(wake_phrase_enabled: bool) -> str:
    return "Wake phrase initializing" if wake_phrase_enabled else "Wake phrase off"


def active_companion_summary_text(proactive_enabled: bool, proactive_voice_enabled: bool) -> str:
    checks = "on" if proactive_enabled else "off"
    voice = "on" if proactive_voice_enabled else "off"
    return f"Active companion checks {checks}; speak-up notices {voice}"


class DamienStateInitializer:
    def __init__(self, app: Any) -> None:
        self.app = app

    def initialize(self) -> None:
        app = self.app
        app.mic_enabled = tk.BooleanVar(value=True)
        app.ollama_connected = tk.BooleanVar(value=False)
        app.wake_enabled = tk.BooleanVar(value=app.settings.wake_phrase_enabled)
        app.launch_at_sign_in = tk.BooleanVar(value=False)
        app.dark_mode = tk.BooleanVar(value=app.settings.theme_mode == "dark")
        app.remote_brain_enabled = tk.BooleanVar(value=app.settings.remote_brain_enabled)
        app.remote_brain_base_url = tk.StringVar(value=app.settings.remote_brain_base_url)
        app.ui_style_choice = tk.StringVar(value=app.settings.ui_style)
        app.accent_color_choice = tk.StringVar(value=app.settings.accent_color)
        app.custom_accent_choice = tk.StringVar(value=app.settings.custom_accent_color)
        app.mascot_size_choice = tk.StringVar(value=app.settings.mascot_size)
        app.mascot_opacity_choice = tk.StringVar(value=mascot_opacity_percent_text(app.settings.mascot_opacity))
        app.compact_mode = tk.BooleanVar(value=app.settings.compact_mode)
        app.reduce_glow = tk.BooleanVar(value=app.settings.reduce_glow)
        app.mascot_widget_enabled = tk.BooleanVar(value=app.settings.mascot_widget_enabled)
        app.proactive_enabled = tk.BooleanVar(value=app.settings.proactive_enabled)
        app.proactive_voice_enabled = tk.BooleanVar(value=app.settings.proactive_voice_enabled)
        app.remote_password_choice = tk.StringVar(value="")
        app.current_response = ""
        app.current_user_request_text = ""
        app.log_path = APP_ROOT / "logs" / "damien.log"
        app.voice_log_path = APP_ROOT / "logs" / "damien.log"
        app.tray = None
        app.remote = None
        app.discord_bridge = None
        app.current_remote_request_id = None
        app.proactive_loop = None
        app.wake_detector = None
        app.wake_command_gate = WakePhraseDetector.CommandGate()
        app.mascot_window = None
        app.mascot_canvas = None
        app.mascot_photo = None
        app.mascot_source_image = None
        app.header_emblem_canvas = None
        app.mascot_status = tk.StringVar(value="Online")
        app.mascot_last_heard = tk.StringVar(value="Say hey Damien")
        app.mascot_command = tk.StringVar(value="")
        app.mascot_scale = 1.0
        app.mascot_animation_phase = 0
        app.header_animation_phase = 0
        app._mascot_drag_offset = (0, 0)
        app._mascot_last_saved_position = None
        app.quitting = False
        app.active_stt_device = tk.StringVar(value="STT: not initialized")
        app.microphone_choice = tk.StringVar(value="")
        app.output_choice = tk.StringVar(value=app.settings.output_device_name)
        app.tts_engine_choice = tk.StringVar(value=tts_engine_label(app.settings.tts_engine))
        app.voice_choice = tk.StringVar(value=app.settings.tts_voice_name)
        app.piper_voice_choice = tk.StringVar(value=app.settings.piper_voice_name)
        app.voice_rate_choice = tk.StringVar(value=str(app.settings.tts_rate))
        app.voice_volume_choice = tk.DoubleVar(value=round(app.settings.tts_volume * 100))
        app.voice_volume_display = tk.StringVar(value=f"{int(round(app.settings.tts_volume * 100))}%")
        app.microphone_devices = []
        app.microphone_labels = {}
        app.microphone_volume = tk.StringVar(value="Microphone volume: not tested")
        app.wake_sensitivity_choice = tk.StringVar(value=sensitivity_label(app.settings.wake_sensitivity))
        app.speech_vocabulary_choice = tk.StringVar(value=", ".join(app.settings.speech_vocabulary))
        app.speech_corrections_choice = tk.StringVar(
            value="; ".join(f"{source}={target}" for source, target in app.settings.speech_corrections.items())
        )
        app.stt_settings_status = tk.StringVar(value="Personalized local speech recognition")
        app.local_engine_summary = tk.StringVar(value="Checking local Ollama")
        app.voice_summary = tk.StringVar(value="Voice systems checking")
        app.wake_summary = tk.StringVar(value=wake_summary_text(app.settings.wake_phrase_enabled))
        app.proactive_summary = tk.StringVar(
            value=active_companion_summary_text(app.settings.proactive_enabled, app.settings.proactive_voice_enabled)
        )
        app.privacy_summary = tk.StringVar(value="Free-only local mode")
        app.current_assistant_start = None
        app.current_assistant_end = None
        app.streaming_active = False
        app.current_response_save_history = True
        app.current_response_speak = True
        app.debug_streaming_enabled = os.environ.get("DAMIEN_DEBUG_STREAMING") == "1"
        app.debug_assistant_block_count = 0
        app.debug_streaming_status = tk.StringVar(value="Streaming debug: inactive")
        app.text_surfaces: list[scrolledtext.ScrolledText] = []
