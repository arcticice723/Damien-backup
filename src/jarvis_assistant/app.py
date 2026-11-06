from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from .ai import ChatMessage
from .app_appearance_control import AppearanceController
from .app_bridge_control import AppBridgeController
from .app_mascot_control import MascotController
from .app_ollama_control import OllamaRuntimeController
from .app_voice_settings_control import VoiceSettingsController
from .app_lifecycle import AppLifecycleController
from .app_speech_interaction import SpeechInteractionController
from .app_utility_actions import UtilityActionsController
from .app_proactive_control import ProactiveController
from .app_wake_control import WakeController
from .app_speech_diagnostics_control import SpeechDiagnosticsController
from .app_conversation_context import ConversationContextBuilder
from .app_conversation_control import ConversationController
from .app_mic_privacy_control import MicPrivacyController
from .app_debug_streaming import DebugStreamingController
from .app_transcript_ui import TranscriptController
from .app_shell_ui import DamienShellBuilder
from .app_state import DamienStateInitializer
from .app_startup_sequence import DamienStartupRunner
from .app_services import DamienServiceInitializer
from .app_microphone_repair import repaired_microphone_settings
from .app_chat_ui import DamienChatTabBuilder
from .app_tab_ui import DamienBenchmarkTabBuilder, DamienMemoryTabBuilder
from .app_settings_ui import (
    DamienSettingsTabBuilder,
)
from .audio import list_input_device_info
from .config import load_settings, update_settings
from .mascot_ui import (
    MASCOT_WIDGET_SIZE,
)
from .speech import (
    TextToSpeech,
)
from .speech_controller import SpeechController


class DamienApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self._repair_microphone_settings()
        self.title("Damien")
        self.geometry("1280x820")
        self.minsize(1050, 680)
        self.configure(bg="#101418")

        DamienServiceInitializer(self).initialize()
        DamienStateInitializer(self).initialize()
        self.speech = SpeechController(
            tts_factory=self._new_tts,
            emit=lambda kind, payload: self.events.put((kind, payload)),
            log=self._log_voice,
            resume_wake=self._resume_wake_detector,
            pause_wake=self._pause_wake_detector,
        )

        DamienStartupRunner(self).run()

    def _repair_microphone_settings(self) -> None:
        devices = list_input_device_info()
        repaired = repaired_microphone_settings(
            self.settings.microphone_device_index,
            self.settings.microphone_device_name,
            devices,
        )
        if repaired is None:
            return
        update_settings(repaired)
        self.settings = load_settings()

    def _style(self) -> None:
        DamienShellBuilder(self).style()

    def _theme_colors(self) -> dict[str, str]:
        return DamienShellBuilder(self).theme_colors()

    def _status_card(self, parent: tk.Misc, title: str, variable: tk.StringVar, accent: str) -> tk.Frame:
        return DamienShellBuilder(self).status_card(parent, title, variable, accent)

    def _text_surface(self, parent: tk.Misc, font: tuple[str, int] | tuple[str, int, str] = ("Segoe UI", 10)) -> scrolledtext.ScrolledText:
        return DamienShellBuilder(self).text_surface(parent, font)

    def _scrollable_frame(self, parent: tk.Misc) -> ttk.Frame:
        return DamienShellBuilder(self).scrollable_frame(parent)

    def _build_ui(self) -> None:
        DamienShellBuilder(self).build()

    def _section(self, parent: ttk.Frame, title: str, row: int, column: int, **grid_options) -> ttk.Frame:
        return DamienShellBuilder(self).section(parent, title, row, column, **grid_options)

    def _build_chat_tab(self, parent: ttk.Frame) -> None:
        DamienChatTabBuilder(self).build(parent)

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        DamienSettingsTabBuilder(self).build(parent)

    def _build_memory_tab(self, parent: ttk.Frame) -> None:
        DamienMemoryTabBuilder(self).build(parent)

    def _build_benchmark_tab(self, parent: ttk.Frame) -> None:
        DamienBenchmarkTabBuilder(self).build(parent)

    def _refresh_microphone_devices(self) -> None:
        VoiceSettingsController(self).refresh_microphone_devices()

    def _save_selected_microphone(self) -> None:
        VoiceSettingsController(self).save_selected_microphone()

    def _refresh_output_devices(self) -> None:
        VoiceSettingsController(self).refresh_output_devices()

    def _refresh_voice_choices(self) -> None:
        VoiceSettingsController(self).refresh_voice_choices()

    def _save_selected_tts_engine(self) -> None:
        VoiceSettingsController(self).save_selected_tts_engine()

    def _save_selected_output_device(self) -> None:
        VoiceSettingsController(self).save_selected_output_device()

    def _save_selected_voice_profile(self) -> None:
        VoiceSettingsController(self).save_selected_voice_profile()

    def _save_selected_voice_volume(self) -> None:
        VoiceSettingsController(self).save_selected_voice_volume()

    def _use_best_voice(self) -> None:
        VoiceSettingsController(self).use_best_voice()

    def _use_best_windows_voice(self) -> None:
        VoiceSettingsController(self).use_best_windows_voice()

    def _save_wake_sensitivity(self) -> None:
        VoiceSettingsController(self).save_wake_sensitivity()

    def _save_speech_help(self) -> None:
        VoiceSettingsController(self).save_speech_help()

    def _send_typed(self) -> None:
        text = self.input_text.get().strip()
        if not text:
            return
        self.input_text.delete(0, tk.END)
        self._handle_user_text(text)

    def _start_recording(self) -> None:
        SpeechInteractionController(self).start_recording()

    def _stop_recording(self) -> None:
        SpeechInteractionController(self).stop_recording()

    def _transcribe_recording(self) -> None:
        SpeechInteractionController(self).transcribe_recording()

    def _handle_user_text(self, text: str) -> None:
        ConversationController(self).handle_user_text(text)

    def _handle_remote_user_text(self, request_id: str, text: str) -> None:
        ConversationController(self).handle_remote_user_text(request_id, text)

    def _start_streaming_response_block(self, text: str, save_user: bool) -> None:
        ConversationController(self).start_streaming_response_block(text, save_user)

    def _respond(self, text: str) -> None:
        ConversationController(self).respond(text)

    def _messages_with_context(self, text: str) -> list[ChatMessage]:
        return ConversationContextBuilder(self).messages_with_context(text)

    def _poll_events(self) -> None:
        self.event_dispatcher.poll_once()
        self.after(80, self._poll_events)

    def _start_streaming_speech(self) -> None:
        SpeechInteractionController(self).start_streaming_speech()

    def _queue_streaming_speech(self, text: str) -> None:
        SpeechInteractionController(self).queue_streaming_speech(text)

    def _finish_streaming_speech(self) -> None:
        SpeechInteractionController(self).finish_streaming_speech()

    def _speak(self, text: str) -> None:
        SpeechInteractionController(self).speak(text)

    def _queue_spoken_cue(self, text: str) -> None:
        SpeechInteractionController(self).queue_spoken_cue(text)

    def _speak_short_cue(self, text: str) -> None:
        SpeechInteractionController(self).speak_short_cue(text)

    def _play_wake_feedback(self, cue_text: str, tone_callback) -> None:
        SpeechInteractionController(self).play_wake_feedback(cue_text, tone_callback)

    def _stop_speaking(self) -> None:
        SpeechInteractionController(self).stop_speaking()

    def _new_tts(self) -> TextToSpeech:
        return SpeechInteractionController(self).new_tts()

    def _append_line(self, speaker: str, text: str) -> None:
        TranscriptController(self).append_line(speaker, text)

    def _replace_last_assistant_line(self, text: str) -> None:
        TranscriptController(self).replace_last_assistant_line(text)

    def _debug_streaming_test(self) -> None:
        DebugStreamingController(self).start_test()

    def _debug_streaming_worker(self) -> None:
        DebugStreamingController(self).run_worker()

    def _set_debug_streaming_status(self) -> None:
        DebugStreamingController(self).set_status()

    def _log_stream_debug(self, message: str) -> None:
        DebugStreamingController(self).log(message)

    def _start_proactive_loop(self) -> None:
        ProactiveController(self).start_loop()

    def _show_proactive_notice(self, text: str) -> None:
        ProactiveController(self).show_notice(text)

    def _toggle_proactive_checks(self) -> None:
        ProactiveController(self).toggle_proactive_checks()

    def _toggle_proactive_voice(self) -> None:
        ProactiveController(self).toggle_proactive_voice()

    def _speak_benchmark(self, text: str) -> None:
        UtilityActionsController(self).speak_benchmark(text)

    def _run_benchmark(self) -> None:
        UtilityActionsController(self).run_benchmark()

    def _benchmark_worker(self) -> None:
        UtilityActionsController(self).benchmark_worker()

    def _refresh_gpu(self) -> None:
        UtilityActionsController(self).refresh_gpu()

    def _refresh_memory(self) -> None:
        UtilityActionsController(self).refresh_memory()

    def _delete_memory(self) -> None:
        UtilityActionsController(self).delete_memory()

    def _toggle_mic(self) -> None:
        MicPrivacyController(self).toggle_mic()

    def _use_selected_model(self) -> None:
        OllamaRuntimeController(self).use_selected_model()

    def _switch_to_fallback_model(self, reason: str) -> bool:
        return OllamaRuntimeController(self).switch_to_fallback_model(reason)

    def _refresh_orchestration(self) -> None:
        OllamaRuntimeController(self).refresh_orchestration()

    def _check_ollama_async(self) -> None:
        OllamaRuntimeController(self).check_async()

    def _check_ollama_worker(self) -> None:
        OllamaRuntimeController(self).check_worker()

    def _set_ollama_status(self, status: object) -> None:
        OllamaRuntimeController(self).set_status(status)

    def _start_ollama(self) -> None:
        OllamaRuntimeController(self).start_ollama()

    def _start_ollama_worker(self) -> None:
        OllamaRuntimeController(self).start_ollama_worker()

    def _probe_after_start_attempt(self, startup_detail: str) -> None:
        OllamaRuntimeController(self).probe_after_start_attempt(startup_detail)

    def _open_settings_tab(self) -> None:
        self.notebook.select(self.settings_tab)

    def _toggle_dark_mode(self) -> None:
        AppearanceController(self).toggle_dark_mode()

    def _save_appearance_settings(self) -> None:
        AppearanceController(self).save_appearance_settings()

    def _reset_appearance_settings(self) -> None:
        AppearanceController(self).reset_appearance_settings()

    def _apply_text_surface_theme(self) -> None:
        AppearanceController(self).apply_text_surface_theme()

    def _apply_input_widget_theme(self) -> None:
        AppearanceController(self).apply_input_widget_theme()

    def _sync_mascot_widget(self) -> None:
        MascotController(self).sync_widget()

    def _recreate_mascot_widget(self) -> None:
        MascotController(self).recreate_widget()

    def _show_mascot_widget(self) -> None:
        MascotController(self).show_widget()

    def _assistant_motion_state(self) -> str:
        return MascotController(self).motion_state()

    def _refresh_header_emblem_canvas(self) -> None:
        MascotController(self).refresh_header_emblem_canvas()

    def _animate_header_emblem(self) -> None:
        MascotController(self).animate_header_emblem()

    def _send_mascot_command(self) -> None:
        MascotController(self).send_command()

    def _hide_mascot_widget(self) -> None:
        MascotController(self).hide_widget()

    def _toggle_mascot_widget(self) -> None:
        MascotController(self).toggle_widget()

    def _start_mascot_drag(self, event: tk.Event) -> None:
        MascotController(self).start_drag(event)

    def _drag_mascot_widget(self, event: tk.Event) -> None:
        MascotController(self).drag_widget(event)

    def _save_mascot_position(self, _event: tk.Event | None = None) -> None:
        MascotController(self).save_position()

    def _mascot_start_position(self, width: int, height: int, screen_width: int, screen_height: int) -> tuple[int, int]:
        return MascotController(self).start_position(width, height, screen_width, screen_height)

    def _refresh_mascot_widget(self) -> None:
        MascotController(self).refresh_widget()

    def _draw_mascot(self, accent: str, engine_on: bool, mic_on: bool) -> None:
        MascotController(self).draw_mascot(accent, engine_on, mic_on)

    def _load_mascot_source_image(self) -> object | None:
        return MascotController(self).load_source_image()

    def _log_connection(self, message: str) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as file:
                file.write(message + "\n")
        except OSError:
            pass

    def _start_tray(self) -> None:
        AppBridgeController(self).start_tray()

    def _start_remote_control(self) -> None:
        AppBridgeController(self).start_remote_control()

    def _save_remote_password(self) -> None:
        AppBridgeController(self).save_remote_password()

    def _start_discord_bridge(self) -> None:
        AppBridgeController(self).start_discord_bridge()

    def _remote_pin(self) -> str:
        return AppLifecycleController(self).remote_pin()

    def _set_remote_pin_display(self, pin: str) -> None:
        AppLifecycleController(self).set_remote_pin_display(pin)

    def _set_remote_status(self, text: str) -> None:
        AppLifecycleController(self).set_remote_status(text)

    def _remote_status_payload(self) -> dict[str, str]:
        return AppLifecycleController(self).remote_status_payload()

    def _apply_startup_visibility(self) -> None:
        AppLifecycleController(self).apply_startup_visibility()

    def _start_in_tray(self) -> None:
        AppLifecycleController(self).start_in_tray()

    def _toggle_start_minimized_to_tray(self) -> None:
        AppLifecycleController(self).toggle_start_minimized_to_tray()

    def _on_close(self) -> None:
        AppLifecycleController(self).on_close()

    def _on_unmap(self, _event: tk.Event) -> None:
        AppLifecycleController(self).on_unmap()

    def _restore_from_tray(self) -> None:
        AppLifecycleController(self).restore_from_tray()

    def _restore_window(self) -> None:
        AppLifecycleController(self).restore_window()

    def _quit_from_tray(self) -> None:
        AppLifecycleController(self).quit_from_tray()

    def _quit(self) -> None:
        AppLifecycleController(self).quit()

    def _toggle_mic_from_tray(self) -> None:
        AppLifecycleController(self).toggle_mic_from_tray()

    def _toggle_mic_value(self) -> None:
        AppLifecycleController(self).toggle_mic_value()

    def _tray_status_text(self) -> str:
        return AppLifecycleController(self).tray_status_text()

    def _sync_startup_state(self) -> None:
        AppLifecycleController(self).sync_startup_state()

    def _toggle_launch_at_sign_in(self) -> None:
        AppLifecycleController(self).toggle_launch_at_sign_in()

    def _toggle_wake_phrase(self) -> None:
        WakeController(self).toggle_wake_phrase()

    def _start_wake_detector(self) -> None:
        WakeController(self).start_detector()

    def _handle_wake_detected(self) -> None:
        WakeController(self).handle_wake_detected()

    def _record_wake_command(self) -> None:
        WakeController(self).record_wake_command()

    def _refresh_speech_status_async(self) -> None:
        SpeechDiagnosticsController(self).refresh_speech_status_async()

    def _refresh_speech_status_worker(self) -> None:
        SpeechDiagnosticsController(self).refresh_speech_status_worker()

    def _apply_speech_status(self, diagnostics: object) -> None:
        SpeechDiagnosticsController(self).apply_speech_status(diagnostics)

    def _apply_speech_error(self, message: str) -> None:
        SpeechDiagnosticsController(self).apply_speech_error(message)

    def _test_microphone(self) -> None:
        SpeechDiagnosticsController(self).test_microphone()

    def _test_microphone_worker(self) -> None:
        SpeechDiagnosticsController(self).test_microphone_worker()

    def _test_voice(self) -> None:
        SpeechDiagnosticsController(self).test_voice()

    def _test_voice_worker(self) -> None:
        SpeechDiagnosticsController(self).test_voice_worker()

    def _run_voice_diagnostics(self) -> None:
        SpeechDiagnosticsController(self).run_voice_diagnostics()

    def _voice_diagnostics_worker(self) -> None:
        SpeechDiagnosticsController(self).voice_diagnostics_worker()

    def _show_voice_diagnostics(self, text: str) -> None:
        SpeechDiagnosticsController(self).show_voice_diagnostics(text)

    def _pause_wake_detector(self, reason: str) -> None:
        WakeController(self).pause_detector(reason)

    def _resume_wake_detector(self, reason: str) -> None:
        WakeController(self).resume_detector(reason)

    def _log_voice(self, message: str) -> None:
        self._log_connection(f"voice: {message}")

    def _test_wake_phrase(self) -> None:
        SpeechDiagnosticsController(self).test_wake_phrase()

    def _test_wake_phrase_worker(self) -> None:
        SpeechDiagnosticsController(self).test_wake_phrase_worker()


def main() -> None:
    from .single_instance import SingleInstance

    instance = SingleInstance()
    if not instance.acquire():
        return
    try:
        app = DamienApp()
        instance.start_restore_listener(lambda: app.events.put(("restore_window", None)))
        app.mainloop()
    finally:
        instance.release()

