from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from .app_settings_choices import appearance_option_values, settings_section_titles, voice_option_values
from .app_services import ollama_runtime_base_url
from .app_status import cloud_status_text, model_profile_summary
from .system_metrics import get_installed_ollama_models


LOCAL_AI_PANEL_FIELDS = ["Ollama model", "Thinking mode", "Remote brain", "Brain server URL"]
APPEARANCE_PANEL_FIELDS = [
    "UI style",
    "Accent color",
    "Custom accent",
    "Mascot size",
    "Mascot opacity",
    "Compact mode",
    "Reduce glow",
]
VOICE_PANEL_FIELDS = [
    "Microphone",
    "Voice output",
    "Voice engine",
    "Piper voice",
    "Windows voice",
    "Voice speed",
    "Voice volume",
    "Wake sensitivity",
]
VOICE_STATUS_DEFAULTS = {
    "mic_status": "Microphone: checking...",
    "wake_dependency_status": "Wake phrase: checking...",
    "tts_status": "Voice: checking...",
}
AUTOMATION_PANEL_ITEMS = [
    "Start in background tray mode",
    "Show desktop mascot widget",
    'Enable wake phrase "Hey Damien"',
    "Active companion checks",
    "Speak proactive notices aloud",
    "Launch Damien at Windows sign-in",
    "Dark mode",
]
AUTOMATION_STATUS_DEFAULTS = {"remote_status": "Remote: starting..."}
DIAGNOSTICS_PANEL_BUTTONS = ["Test Microphone", "Test Voice", "Calibrate Wake Phrase", "Voice Diagnostics"]
DIAGNOSTICS_STATUS_DEFAULTS = {"wake_status": "Disabled"}


def settings_section_layout() -> list[tuple[str, int, int, dict[str, object]]]:
    sections = settings_section_titles()
    return [
        (sections[0], 0, 0, {"padx": (0, 10), "pady": (0, 10)}),
        (sections[1], 0, 1, {"padx": (10, 0), "pady": (0, 10)}),
        (sections[2], 1, 0, {"padx": (0, 10), "pady": (10, 10)}),
        (sections[3], 1, 1, {"padx": (10, 0), "pady": (10, 10)}),
        (sections[4], 2, 0, {"columnspan": 2, "pady": (10, 10)}),
        (sections[5], 3, 0, {"columnspan": 2, "pady": (10, 0)}),
    ]


def local_ai_panel_fields() -> list[str]:
    return list(LOCAL_AI_PANEL_FIELDS)


def appearance_panel_fields() -> list[str]:
    return list(APPEARANCE_PANEL_FIELDS)


def voice_panel_fields() -> list[str]:
    return list(VOICE_PANEL_FIELDS)


def voice_status_defaults() -> dict[str, str]:
    return dict(VOICE_STATUS_DEFAULTS)


def automation_panel_items() -> list[str]:
    return list(AUTOMATION_PANEL_ITEMS)


def automation_status_defaults() -> dict[str, str]:
    return dict(AUTOMATION_STATUS_DEFAULTS)


def diagnostics_panel_buttons() -> list[str]:
    return list(DIAGNOSTICS_PANEL_BUTTONS)


def diagnostics_status_defaults() -> dict[str, str]:
    return dict(DIAGNOSTICS_STATUS_DEFAULTS)


def audit_status_text(settings: Any) -> str:
    return f"Audit log: {settings.audit_log_path}"


def local_model_choices(settings: Any, models: list[str]) -> list[str]:
    choices = list(models)
    selected_model = getattr(settings, "model", "")
    if selected_model and selected_model not in choices:
        choices.insert(0, selected_model)
    return choices


class DamienSettingsTabBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, parent: ttk.Frame) -> None:
        app = self.app
        content = app._scrollable_frame(parent)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        section_frames = [
            app._section(content, title, row, column, **grid_options)
            for title, row, column, grid_options in settings_section_layout()
        ]
        core, voice, automation, diagnostics, appearance, logs = section_frames

        LocalAISettingsPanelBuilder(app).build(core)
        VoiceSettingsPanelBuilder(app).build(voice)
        AutomationSettingsPanelBuilder(app).build(automation)
        DiagnosticsSettingsPanelBuilder(app).build(diagnostics)
        AppearanceSettingsPanelBuilder(app).build(appearance)
        AuditSettingsPanelBuilder(app).build(logs)

        app._refresh_microphone_devices()
        app._refresh_output_devices()
        app._refresh_voice_choices()
        app._refresh_speech_status_async()


class LocalAISettingsPanelBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, core: ttk.Frame) -> None:
        app = self.app
        fields = local_ai_panel_fields()
        ttk.Label(core, text=fields[0], style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        models = local_model_choices(app.settings, get_installed_ollama_models(ollama_runtime_base_url(app.settings)))
        app.model_choice = tk.StringVar(value=app.settings.model)
        model_box = ttk.Combobox(core, textvariable=app.model_choice, values=models, state="normal")
        model_box.grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(core, text="Use Model", command=app._use_selected_model).grid(row=0, column=2, padx=(8, 0))
        app.model_profile_summary = tk.StringVar(value=model_profile_summary(models))
        ttk.Label(core, textvariable=app.model_profile_summary, style="PanelMuted.TLabel", wraplength=420).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 8)
        )
        ttk.Label(core, text=fields[1], style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
        app.thinking_choice = tk.StringVar(value=app.settings.thinking_mode)
        ttk.Combobox(core, textvariable=app.thinking_choice, values=["auto", "off", "on"], state="readonly").grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=6
        )
        ttk.Checkbutton(core, text=fields[2], variable=app.remote_brain_enabled).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=6
        )
        ttk.Label(core, text=fields[3], style="Panel.TLabel").grid(row=4, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Entry(core, textvariable=app.remote_brain_base_url).grid(row=4, column=1, columnspan=2, sticky="ew", pady=6)
        app.gpu_status = tk.StringVar(value="GPU: checking...")
        ttk.Label(core, textvariable=app.gpu_status, style="PanelMuted.TLabel", wraplength=420).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )


class VoiceSettingsPanelBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, voice: ttk.Frame) -> None:
        app = self.app
        options = voice_option_values()
        defaults = voice_status_defaults()
        ttk.Label(voice, text="Microphone", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        app.microphone_box = ttk.Combobox(voice, textvariable=app.microphone_choice, state="readonly")
        app.microphone_box.grid(row=0, column=1, sticky="ew", pady=6)
        app.microphone_box.bind("<<ComboboxSelected>>", lambda _event: app._save_selected_microphone())
        ttk.Button(voice, text="Refresh", command=app._refresh_microphone_devices).grid(
            row=0, column=2, padx=(8, 0)
        )
        app.mic_status = tk.StringVar(value=defaults["mic_status"])
        app.wake_dependency_status = tk.StringVar(value=defaults["wake_dependency_status"])
        app.tts_status = tk.StringVar(value=defaults["tts_status"])
        ttk.Label(voice, text="Voice output", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        app.output_box = ttk.Combobox(voice, textvariable=app.output_choice, state="readonly")
        app.output_box.grid(row=1, column=1, sticky="ew", pady=6)
        app.output_box.bind("<<ComboboxSelected>>", lambda _event: app._save_selected_output_device())
        ttk.Button(voice, text="Refresh", command=app._refresh_output_devices).grid(row=1, column=2, padx=(8, 0))
        ttk.Label(voice, text="Voice engine", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
        app.tts_engine_box = ttk.Combobox(
            voice,
            textvariable=app.tts_engine_choice,
            values=options["tts_engines"],
            state="readonly",
        )
        app.tts_engine_box.grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)
        app.tts_engine_box.bind("<<ComboboxSelected>>", lambda _event: app._save_selected_tts_engine())
        ttk.Label(voice, text="Piper voice", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=6, padx=(0, 10))
        app.piper_voice_box = ttk.Combobox(voice, textvariable=app.piper_voice_choice, state="readonly")
        app.piper_voice_box.grid(row=3, column=1, sticky="ew", pady=6)
        app.piper_voice_box.bind("<<ComboboxSelected>>", lambda _event: app._save_selected_voice_profile())
        ttk.Button(voice, text="Neural", command=app._use_best_voice).grid(row=3, column=2, padx=(8, 0))
        ttk.Label(voice, text="Windows voice", style="Panel.TLabel").grid(row=4, column=0, sticky="w", pady=6, padx=(0, 10))
        app.voice_box = ttk.Combobox(voice, textvariable=app.voice_choice, state="readonly")
        app.voice_box.grid(row=4, column=1, sticky="ew", pady=6)
        app.voice_box.bind("<<ComboboxSelected>>", lambda _event: app._save_selected_voice_profile())
        ttk.Button(voice, text="Best", command=app._use_best_windows_voice).grid(row=4, column=2, padx=(8, 0))
        ttk.Label(voice, text="Voice speed", style="Panel.TLabel").grid(row=5, column=0, sticky="w", pady=6, padx=(0, 10))
        rate_box = ttk.Combobox(
            voice,
            textvariable=app.voice_rate_choice,
            values=options["voice_rates"],
            state="readonly",
        )
        rate_box.grid(row=5, column=1, columnspan=2, sticky="ew", pady=6)
        rate_box.bind("<<ComboboxSelected>>", lambda _event: app._save_selected_voice_profile())
        ttk.Label(voice, text="Voice volume", style="Panel.TLabel").grid(row=6, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Scale(
            voice,
            variable=app.voice_volume_choice,
            from_=0,
            to=100,
            orient="horizontal",
            command=lambda _value: app._save_selected_voice_volume(),
        ).grid(row=6, column=1, sticky="ew", pady=6)
        ttk.Label(voice, textvariable=app.voice_volume_display, style="Panel.TLabel", width=5).grid(
            row=6, column=2, sticky="e", pady=6
        )
        ttk.Label(voice, text="Wake sensitivity", style="Panel.TLabel").grid(row=7, column=0, sticky="w", pady=6, padx=(0, 10))
        sensitivity_box = ttk.Combobox(
            voice,
            textvariable=app.wake_sensitivity_choice,
            values=options["wake_sensitivity"],
            state="readonly",
        )
        sensitivity_box.grid(row=7, column=1, columnspan=2, sticky="ew", pady=6)
        sensitivity_box.bind("<<ComboboxSelected>>", lambda _event: app._save_wake_sensitivity())
        ttk.Label(voice, textvariable=app.mic_status, style="PanelMuted.TLabel").grid(row=8, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Label(voice, textvariable=app.wake_dependency_status, style="PanelMuted.TLabel").grid(row=9, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Label(voice, textvariable=app.tts_status, style="PanelMuted.TLabel").grid(row=10, column=0, columnspan=3, sticky="w", pady=3)
        ttk.Label(voice, text="Names and terms", style="Panel.TLabel").grid(row=11, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Entry(voice, textvariable=app.speech_vocabulary_choice).grid(row=11, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Label(voice, text="Fix misheard words", style="Panel.TLabel").grid(row=12, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Entry(voice, textvariable=app.speech_corrections_choice).grid(row=12, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Button(voice, text="Save speech help", command=app._save_speech_help).grid(row=13, column=1, sticky="w", pady=(2, 6))
        ttk.Label(voice, textvariable=app.stt_settings_status, style="PanelMuted.TLabel", wraplength=420).grid(
            row=13, column=2, sticky="e", pady=(2, 6)
        )


class AutomationSettingsPanelBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, automation: ttk.Frame) -> None:
        app = self.app
        defaults = automation_status_defaults()
        items = automation_panel_items()
        app.start_minimized_to_tray = tk.BooleanVar(value=app.settings.start_minimized_to_tray)
        app.remote_pin_display = tk.StringVar(value="Phone access is protected. Set a fixed password below.")
        ttk.Label(automation, textvariable=app.remote_pin_display, style="Panel.TLabel", wraplength=420).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Checkbutton(
            automation,
            text=items[0],
            variable=app.start_minimized_to_tray,
            command=app._toggle_start_minimized_to_tray,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(
            automation,
            text=items[1],
            variable=app.mascot_widget_enabled,
            command=app._toggle_mascot_widget,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(
            automation,
            text=items[2],
            variable=app.wake_enabled,
            command=app._toggle_wake_phrase,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(
            automation,
            text=items[3],
            variable=app.proactive_enabled,
            command=app._toggle_proactive_checks,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(
            automation,
            text=items[4],
            variable=app.proactive_voice_enabled,
            command=app._toggle_proactive_voice,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(
            automation,
            text=items[5],
            variable=app.launch_at_sign_in,
            command=app._toggle_launch_at_sign_in,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(
            automation,
            text=items[6],
            variable=app.dark_mode,
            command=app._toggle_dark_mode,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=6)
        app.cloud_status = tk.StringVar(value=cloud_status_text(app.settings))
        ttk.Label(automation, textvariable=app.cloud_status, style="PanelMuted.TLabel", wraplength=420).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        app.remote_status = tk.StringVar(value=defaults["remote_status"])
        ttk.Label(automation, textvariable=app.remote_status, style="PanelMuted.TLabel", wraplength=420).grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )
        ttk.Label(automation, text="Phone password (12+ characters)", style="Panel.TLabel").grid(
            row=10, column=0, sticky="w", pady=(10, 6), padx=(0, 10)
        )
        ttk.Entry(automation, textvariable=app.remote_password_choice, show="•").grid(
            row=10, column=1, sticky="ew", pady=(10, 6)
        )
        ttk.Button(automation, text="Set fixed password", command=app._save_remote_password).grid(
            row=11, column=1, sticky="e", pady=(2, 6)
        )


class DiagnosticsSettingsPanelBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, diagnostics: ttk.Frame) -> None:
        app = self.app
        buttons = diagnostics_panel_buttons()
        defaults = diagnostics_status_defaults()
        ttk.Button(diagnostics, text=buttons[0], command=app._test_microphone).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(diagnostics, text=buttons[1], command=app._test_voice).grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        ttk.Button(diagnostics, text=buttons[2], command=app._test_wake_phrase).grid(
            row=1, column=0, sticky="ew", pady=4
        )
        ttk.Button(diagnostics, text=buttons[3], command=app._run_voice_diagnostics).grid(
            row=1, column=1, sticky="ew", pady=4, padx=(8, 0)
        )
        ttk.Label(diagnostics, textvariable=app.active_stt_device, style="PanelMuted.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(10, 2)
        )
        ttk.Label(diagnostics, textvariable=app.microphone_volume, style="PanelMuted.TLabel", wraplength=420).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=2
        )
        app.wake_status = tk.StringVar(value=defaults["wake_status"])
        ttk.Label(diagnostics, textvariable=app.wake_status, style="PanelMuted.TLabel").grid(row=4, column=0, columnspan=2, sticky="w", pady=2)


class AppearanceSettingsPanelBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, appearance: ttk.Frame) -> None:
        app = self.app
        options = appearance_option_values()
        ttk.Label(appearance, text="UI style", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Combobox(
            appearance,
            textvariable=app.ui_style_choice,
            values=options["ui_styles"],
            state="readonly",
        ).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(appearance, text="Accent color", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Combobox(
            appearance,
            textvariable=app.accent_color_choice,
            values=options["accent_colors"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(appearance, text="Custom accent", style="Panel.TLabel").grid(row=1, column=2, sticky="w", pady=6, padx=(18, 10))
        ttk.Entry(appearance, textvariable=app.custom_accent_choice, width=12).grid(row=1, column=3, sticky="ew", pady=6)
        ttk.Label(appearance, text="Mascot size", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=6, padx=(0, 10))
        ttk.Combobox(
            appearance,
            textvariable=app.mascot_size_choice,
            values=options["mascot_sizes"],
            state="readonly",
        ).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(appearance, text="Mascot opacity", style="Panel.TLabel").grid(row=2, column=2, sticky="w", pady=6, padx=(18, 10))
        ttk.Combobox(
            appearance,
            textvariable=app.mascot_opacity_choice,
            values=options["mascot_opacity"],
            state="readonly",
        ).grid(row=2, column=3, sticky="ew", pady=6)
        ttk.Checkbutton(appearance, text="Compact mode", variable=app.compact_mode).grid(
            row=3, column=0, sticky="w", pady=8
        )
        ttk.Checkbutton(appearance, text="Reduce glow", variable=app.reduce_glow).grid(
            row=3, column=1, sticky="w", pady=8
        )
        ttk.Button(appearance, text="Apply Appearance", command=app._save_appearance_settings, style="Accent.TButton").grid(
            row=3, column=2, sticky="ew", padx=(18, 8), pady=8
        )
        ttk.Button(appearance, text="Reset Appearance", command=app._reset_appearance_settings).grid(
            row=3, column=3, sticky="ew", pady=8
        )


class AuditSettingsPanelBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, logs: ttk.Frame) -> None:
        app = self.app
        app.audit_status = tk.StringVar(value=audit_status_text(app.settings))
        ttk.Label(logs, textvariable=app.audit_status, style="PanelMuted.TLabel", wraplength=900).grid(
            row=0, column=0, sticky="w", pady=2
        )
