from __future__ import annotations

import re
import threading
from typing import Any

from . import config
from .app_proactive_control import update_loaded_setting, update_proactive_summary


def no_visible_text_fallback() -> str:
    return "I reached the local model, but it did not return any visible text. Try again or switch local models in Settings."


def active_spoken_notices_request(text: str) -> bool:
    phrase = _normalized_voice_command(text)
    return phrase in {
        "active and speak up",
        "be active and speak up",
        "stay active and speak up",
        "turn on active mode",
        "turn on active companion mode",
        "watch out for me and speak up",
        "keep an eye out and speak up",
    }


def quiet_active_companion_request(text: str) -> bool:
    phrase = _normalized_voice_command(text)
    return phrase in {
        "dont speak up unless i ask",
        "only speak up if i ask",
        "stop being active",
        "stop speaking up",
        "stop active mode",
        "turn off active mode",
        "turn off active companion mode",
        "stop watching out for me",
        "stop keeping an eye out",
    }


def _normalized_voice_command(text: str) -> str:
    cleaned = text.casefold().replace("'", "")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    words = cleaned.split()
    if words and words[0] in {"hey", "ok", "okay"}:
        words = words[1:]
    if words and words[0] in {"damien", "damian", "daemon", "daymien", "daymian", "damon"}:
        words = words[1:]
    return " ".join(words)


class ConversationController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def handle_user_text(self, text: str) -> None:
        app = self.app
        app._stop_speaking()
        if self.handle_active_spoken_notices_request(text):
            return
        if self.handle_quiet_active_companion_request(text):
            return
        self.start_streaming_response_block(text, save_user=True)
        threading.Thread(target=app._respond, args=(text,), daemon=True).start()

    def handle_remote_user_text(self, request_id: str, text: str) -> None:
        app = self.app
        app._stop_speaking()
        app.current_remote_request_id = request_id
        if self.handle_active_spoken_notices_request(text):
            return
        if self.handle_quiet_active_companion_request(text):
            return
        self.start_streaming_response_block(text, save_user=True)
        threading.Thread(target=app._respond, args=(text,), daemon=True).start()

    def start_streaming_response_block(self, text: str, save_user: bool) -> None:
        app = self.app
        app._append_line("You", text)
        if save_user:
            app.history.add_user(text)
        app.status.set("Thinking...")
        app.current_user_request_text = text
        app.current_response = ""
        app.streaming_active = True
        app.debug_assistant_block_count = 0
        app.current_assistant_start = None
        app.current_assistant_end = None
        app.current_response_save_history = save_user
        app.current_response_speak = save_user
        if app.current_response_speak:
            app._start_streaming_speech()
        app._append_line("Damien", "")

    def handle_active_spoken_notices_request(self, text: str) -> bool:
        if not active_spoken_notices_request(text):
            return False
        app = self.app
        response = "Active companion mode is on. I will watch and speak up."
        self.start_streaming_response_block(text, save_user=True)
        app.proactive_enabled.set(True)
        app.proactive_voice_enabled.set(True)
        update_loaded_setting(app, "proactive_enabled", True)
        update_loaded_setting(app, "proactive_voice_enabled", True)
        config.update_settings({"proactive_enabled": True, "proactive_voice_enabled": True})
        update_proactive_summary(app)
        app._start_proactive_loop()
        app.events.put(("stream_text", response))
        app.events.put(("done", None))
        return True

    def handle_quiet_active_companion_request(self, text: str) -> bool:
        if not quiet_active_companion_request(text):
            return False
        app = self.app
        response = "Active companion mode is off. I will stay quiet unless you call me."
        self.start_streaming_response_block(text, save_user=True)
        app.proactive_enabled.set(False)
        app.proactive_voice_enabled.set(False)
        update_loaded_setting(app, "proactive_enabled", False)
        update_loaded_setting(app, "proactive_voice_enabled", False)
        config.update_settings({"proactive_enabled": False, "proactive_voice_enabled": False})
        loop = getattr(app, "proactive_loop", None)
        if loop is not None:
            loop.stop()
            app.proactive_loop = None
        update_proactive_summary(app)
        app.events.put(("stream_text", response))
        app.events.put(("done", None))
        return True

    def respond(self, text: str) -> None:
        app = self.app
        try:
            orchestration = app.orchestrator.prepare(text, app._messages_with_context(text))
            app._log_connection(
                f"orchestration: provider={orchestration.provider}; "
                f"cloud_data_sent={orchestration.cloud_data_sent}; "
                f"tools={[tool.name for tool in orchestration.tool_results]}"
            )
            if orchestration.direct_response is not None:
                app.events.put(("stream_text", orchestration.direct_response))
                app.events.put(("done", None))
                return

            messages = orchestration.messages
            tool_calls: list[dict] = []
            tools = app.commands.tool_specs() if app.settings.enable_tools and app.tools_supported else None
            if app.settings.enable_tools and not app.tools_supported:
                app._log_connection(f"Tools disabled for model {app.ai.model}: model does not advertise tool support in /api/tags.")
            app._log_voice(f"ollama_request_started: model={app.ai.model}; text={text!r}")
            emitted_text = False
            provider = app.cloud_ai if orchestration.provider == app.settings.cloud_provider else app.ai
            for event in provider.stream(messages, tools):
                if event.kind == "text":
                    emitted_text = True
                    app.events.put(("stream_text", event.content))
                elif event.kind == "tool_calls":
                    tool_calls.extend(event.tool_calls)
                elif event.kind == "done":
                    app.events.put(("stats", event.stats))
                    app._log_voice(
                        f"ollama_request_finished: elapsed={event.stats.elapsed_seconds if event.stats else 'unknown'}"
                    )
            if tool_calls:
                results = [app.commands.run_tool_call(call) for call in tool_calls]
                emitted_text = True
                app.events.put(("stream_text", "\n".join(results)))
            if not emitted_text:
                fallback = no_visible_text_fallback()
                app._log_connection(f"Chat returned no visible text. model={app.ai.model}; text={text!r}")
                app.events.put(("stream_text", fallback))
            app.orchestrator.log_final(text, orchestration, app.current_response.strip() or "Completed.")
            app.events.put(("done", None))
        except Exception as exc:
            self._handle_response_error(text, str(exc))

    def _handle_response_error(self, text: str, message: str) -> None:
        app = self.app
        app._log_connection(f"Chat request error: {message}")
        if "Ollama is not reachable" in message:
            app.events.put(("ollama_down", message))
        elif "Ollama could not load the configured local model" in message:
            if app._switch_to_fallback_model(message):
                app.events.put(
                    (
                        "stream_text",
                        "\nLocal model was too heavy, so I switched to a lighter installed model and retried.\n",
                    )
                )
                self.respond(text)
                return
            app.events.put(("ollama_model_error", message))
        else:
            app.events.put(("error", message))
