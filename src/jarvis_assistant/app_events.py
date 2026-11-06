from __future__ import annotations

import queue
from tkinter import messagebox
from typing import Any

from .app_helpers import short_status_text, stream_chunk_mode, update_stream_response
from .improvement import build_missing_capability_response, is_generic_windows_assistant_response


class DamienEventDispatcher:
    def __init__(self, app: Any) -> None:
        self.app = app

    def poll_once(self) -> None:
        try:
            while True:
                kind, payload = self.app.events.get_nowait()
                self.dispatch(kind, payload)
        except queue.Empty:
            pass

    def dispatch(self, kind: str, payload: object) -> None:
        app = self.app
        if kind == "user_text":
            if payload:
                app._handle_user_text(str(payload))
            else:
                app.status.set("No speech detected.")
                app._toggle_mic()
        elif kind == "remote_user_text":
            request_id, text = payload  # type: ignore[misc]
            app._handle_remote_user_text(str(request_id), str(text))
        elif kind == "debug_start_stream":
            app._start_streaming_response_block(str(payload), save_user=False)
        elif kind == "stream_text":
            chunk = str(payload)
            mode = stream_chunk_mode(app.current_response, chunk)
            previous_length = len(app.current_response)
            app.current_response = update_stream_response(app.current_response, chunk)
            new_text = app.current_response[previous_length:]
            app._log_stream_debug(
                f"stream_text_event: chunk={chunk!r}; mode={mode}; previous_length={previous_length}; "
                f"new_length={len(app.current_response)}; ui_method=update_assistant_stream_block; "
                f"assistant_blocks={app.debug_assistant_block_count}"
            )
            app._replace_last_assistant_line(app.current_response)
            if app.current_response_speak and new_text:
                app._queue_streaming_speech(new_text)
        elif kind == "stats":
            stats = payload
            if stats:
                app.status.set(
                    f"Response: {stats.elapsed_seconds:.1f}s, {stats.eval_count} tokens, {stats.tokens_per_second:.1f} tok/s"
                )
                app._refresh_gpu()
        elif kind == "done":
            response = app.current_response.strip()
            if response and is_generic_windows_assistant_response(response):
                response = build_missing_capability_response(
                    app.current_user_request_text,
                    app.improvement_queue,
                    "Replace generic model fallback with a Damien-specific capability or answer.",
                )
                app.current_response = response
                app._replace_last_assistant_line(response)
            if response and app.current_response_save_history:
                app.history.add_assistant(response)
            if app.current_remote_request_id and app.remote:
                app.remote.complete(app.current_remote_request_id, response or "Done.")
                app.current_remote_request_id = None
            if response and app.current_response_speak:
                app._finish_streaming_speech()
                app.status.set("Speaking response...")
                app.voice_summary.set("Speaking response")
            else:
                app._finish_streaming_speech()
                app.status.set("Ready.")
            app.streaming_active = False
            app.listen_indicator.configure(
                text="Mic ready" if app.mic_enabled.get() else "Mic muted",
                bg="#1f4f7a" if app.mic_enabled.get() else "#7a2630",
            )
        elif kind == "benchmark":
            app._speak_benchmark(str(payload))
        elif kind == "wake_status":
            app.wake_status.set(str(payload))
            app.wake_summary.set(str(payload))
            if app.mic_enabled.get():
                app.listen_indicator.configure(text=str(payload)[:24], bg="#1f4f7a")
        elif kind == "speech_status":
            app._apply_speech_status(payload)
        elif kind == "speech_done":
            app.status.set("Ready.")
            app.voice_summary.set(f"Voice ready on {app.settings.output_device_name}")
        elif kind == "speech_error":
            app.status.set(f"Speech unavailable: {payload}")
            app._append_line("Damien", f"Speech unavailable: {payload}")
            app._log_voice(f"speech_error_visible: {payload}")
            app._apply_speech_error(str(payload))
        elif kind == "proactive_notice":
            app._show_proactive_notice(str(payload))
        elif kind == "active_stt":
            app.active_stt_device.set(str(payload))
        elif kind == "microphone_volume":
            app.microphone_volume.set(str(payload))
        elif kind == "voice_diagnostics":
            app._show_voice_diagnostics(str(payload))
        elif kind == "wake_calibration":
            app._append_line("Wake Calibration", str(payload))
            app.status.set("Wake calibration finished. See conversation and logs/damien.log.")
        elif kind == "wake_detected":
            app._handle_wake_detected()
        elif kind == "wake_command_heard":
            app.mascot_last_heard.set("Heard: " + short_status_text(str(payload), 22))
        elif kind == "restore_window":
            app._restore_window()
        elif kind == "ollama_status":
            app._set_ollama_status(payload)
        elif kind == "ollama_down":
            app._finish_streaming_speech()
            status = app.ai.check_connection()
            app._set_ollama_status(status)
            app.status.set("Damien cannot complete the local Ollama chat request.")
            remote_message = (
                f"I cannot complete the local Ollama request yet. Configured host: "
                f"{app.settings.ollama_base_url}. {payload}"
            )
            app._replace_last_assistant_line(remote_message)
            if app.current_remote_request_id and app.remote:
                app.remote.complete(app.current_remote_request_id, remote_message)
                app.current_remote_request_id = None
        elif kind == "ollama_model_error":
            app._finish_streaming_speech()
            app.status.set("Local model could not load. Switch to a smaller model in Settings.")
            remote_message = (
                "The local model is too heavy for the available memory right now. "
                "I switched the error into a normal Damien response instead of a popup. "
                "Use a smaller model such as llama3.2:3b, or reduce context size."
            )
            app._replace_last_assistant_line(remote_message)
            app.local_engine_summary.set("Local model memory issue")
            app.ollama_message.set(str(payload))
            app._log_connection(f"ollama_model_error_visible: {payload}")
            if app.current_remote_request_id and app.remote:
                app.remote.complete(app.current_remote_request_id, remote_message)
                app.current_remote_request_id = None
        elif kind == "ollama_started":
            app.after(2500, app._check_ollama_async)
        elif kind == "error":
            app._finish_streaming_speech()
            app.status.set("Error.")
            if app.current_remote_request_id and app.remote:
                app.remote.complete(app.current_remote_request_id, f"Error: {payload}")
                app.current_remote_request_id = None
            app.listen_indicator.configure(
                text="Mic ready" if app.mic_enabled.get() else "Mic muted",
                bg="#1f4f7a" if app.mic_enabled.get() else "#7a2630",
            )
            messagebox.showerror("Damien error", str(payload))
