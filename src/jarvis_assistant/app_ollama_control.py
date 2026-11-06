from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from typing import Any

from .ai import ConnectionStatus
from .app_status import (
    cloud_status_text,
    connected_ollama_status_view,
    normalize_connection_status,
    offline_ollama_status_view,
)
from .app_services import build_local_ollama_provider, ollama_runtime_base_url, voice_readiness_status
from .audit import AuditLogger
from .config import load_settings, update_settings
from .local_models import fallback_model
from .memory import LongTermMemory
from .orchestrator import AssistantOrchestrator
from .router import ProviderRouter
from .system_metrics import get_installed_ollama_models
from .tools import ToolRegistry


@dataclass(frozen=True)
class FallbackSwitchResult:
    available: bool
    next_model: str | None
    log_message: str
    summary: str | None = None


def startup_detail_from_stderr(stderr: str) -> str:
    stderr_text = stderr.strip()
    if not stderr_text:
        return ""
    if "Only one usage of each socket address" in stderr_text or "bind" in stderr_text:
        return "ollama serve reported that the port is already in use; probing /api/tags because Ollama is likely already running."
    return f"ollama serve exited: {stderr_text}"


def status_with_startup_detail(status: ConnectionStatus, startup_detail: str) -> ConnectionStatus:
    if not status.reachable and startup_detail:
        return ConnectionStatus(status.reachable, status.url, f"{status.detail} Startup detail: {startup_detail}")
    return status


def fallback_switch_result(current_model: str, installed_models: list[str], reason: str) -> FallbackSwitchResult:
    next_model = fallback_model(current_model, installed_models)
    reason_preview = reason[:300]
    if next_model is None:
        return FallbackSwitchResult(
            available=False,
            next_model=None,
            log_message=f"model_fallback_unavailable: current={current_model}; reason={reason_preview}",
        )
    return FallbackSwitchResult(
        available=True,
        next_model=next_model,
        log_message=f"model_fallback_selected: from={current_model}; to={next_model}; reason={reason_preview}",
        summary=f"{next_model} fallback",
    )


def selected_model_settings_update(
    selected_model: str,
    thinking_mode: str,
    remote_brain_enabled: bool,
    remote_brain_base_url: str,
) -> dict[str, str | bool]:
    return {
        "model": selected_model.strip(),
        "thinking_mode": thinking_mode.strip() or "auto",
        "remote_brain_enabled": remote_brain_enabled,
        "remote_brain_base_url": remote_brain_base_url.strip().rstrip("/"),
    }


def ollama_check_message() -> str:
    return "Checking local Ollama connection..."


class OllamaRuntimeController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def use_selected_model(self) -> None:
        app = self.app
        selected_model = app.model_choice.get().strip()
        update_settings(
            selected_model_settings_update(
                selected_model,
                app.thinking_choice.get(),
                app.remote_brain_enabled.get(),
                app.remote_brain_base_url.get(),
            )
        )
        app.settings = load_settings()
        app.ai = build_local_ollama_provider(app.settings, selected_model)
        self.refresh_orchestration()
        app.status.set(f"Using Ollama model {selected_model}.")
        app._check_ollama_async()

    def switch_to_fallback_model(self, reason: str) -> bool:
        app = self.app
        current_model = app.ai.model
        installed = get_installed_ollama_models(ollama_runtime_base_url(app.settings))
        fallback = fallback_switch_result(current_model, installed, reason)
        if fallback.next_model is None:
            app._log_connection(fallback.log_message)
            return False
        next_model = fallback.next_model
        update_settings({"model": next_model})
        app.settings = load_settings()
        app.model_choice.set(next_model)
        app.ai = build_local_ollama_provider(app.settings, next_model)
        self.refresh_orchestration()
        app.local_engine_summary.set(fallback.summary or f"{next_model} fallback")
        app._log_connection(fallback.log_message)
        return True

    def refresh_orchestration(self) -> None:
        app = self.app
        app.memory = LongTermMemory(app.settings.memory_path, app.settings.enable_long_term_memory)
        app.audit = AuditLogger(app.settings.audit_log_path, app.settings.tool_audit_log_enabled)
        app.tools = ToolRegistry(
            app.commands,
            app.retriever,
            app.memory,
            risk_mode=app.settings.automation_risk_mode,
        )
        app.orchestrator = AssistantOrchestrator(
            ProviderRouter(app.settings),
            app.tools,
            app.audit,
            persona_style=app.settings.voice_persona_style,
            improvement_queue=app.improvement_queue,
            voice_status_provider=lambda: voice_readiness_status(app),
        )
        if hasattr(app, "cloud_status"):
            app.cloud_status.set(cloud_status_text(app.settings))

    def check_async(self) -> None:
        app = self.app
        app.ollama_message.set(ollama_check_message())
        threading.Thread(target=app._check_ollama_worker, daemon=True).start()

    def check_worker(self) -> None:
        app = self.app
        status = app.ai.check_connection()
        app._log_connection(f"Probe {status.url}: reachable={status.reachable}; detail={status.detail}")
        app.events.put(("ollama_status", status))

    def set_status(self, status: object) -> None:
        app = self.app
        base_url = ollama_runtime_base_url(app.settings)
        status = normalize_connection_status(status, base_url)
        connected = status.reachable
        app.ollama_connected.set(connected)
        if connected:
            model_exists = app.ai.model_exists()
            app.tools_supported = app.ai.model_supports_tools()
            view = connected_ollama_status_view(
                base_url=base_url,
                model=app.model_choice.get(),
                model_exists=model_exists,
                tools_enabled=app.settings.enable_tools,
                tools_supported=app.tools_supported,
            )
            app.ollama_message.set(view.message)
            app.local_engine_summary.set(view.summary)
            app.privacy_summary.set(view.privacy)
            app._log_connection(
                f"Ollama connected. host={base_url}; model={app.ai.model}; "
                f"model_exists={model_exists}; tools_supported={app.tools_supported}"
            )
            self._apply_banner_colors(view.banner_bg, view.banner_fg)
            app.status.set(view.status)
        else:
            view = offline_ollama_status_view(base_url, status)
            app.ollama_message.set(view.message)
            self._apply_banner_colors(view.banner_bg, view.banner_fg)
            app.status.set(view.status)
            app.local_engine_summary.set(view.summary)

    def start_ollama(self) -> None:
        app = self.app
        app.ollama_message.set("Trying to start Ollama locally...")
        threading.Thread(target=app._start_ollama_worker, daemon=True).start()

    def start_ollama_worker(self) -> None:
        OllamaStartController(self.app).start()

    def probe_after_start_attempt(self, startup_detail: str) -> None:
        OllamaStartController(self.app).probe_after_start_attempt(startup_detail)

    def _apply_banner_colors(self, bg: str, fg: str) -> None:
        app = self.app
        app.ollama_banner.configure(bg=bg)
        for child in app.ollama_banner.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=bg, fg=fg)


class OllamaStartController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def start(self) -> None:
        startup_detail = ""
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            startup_detail = "Ollama executable was not found on PATH."
            self.app._log_connection(f"Start Ollama failed: {startup_detail}")
            self.probe_after_start_attempt(startup_detail)
            return
        except Exception as exc:
            startup_detail = f"Automatic start failed: {exc}"
            self.app._log_connection(f"Start Ollama failed: {exc}")
            self.probe_after_start_attempt(startup_detail)
            return
        try:
            _stdout, stderr = process.communicate(timeout=1.0)
            startup_detail = startup_detail_from_stderr(stderr or "")
            if startup_detail:
                self.app._log_connection(f"ollama serve exited quickly. stderr={(stderr or '').strip()}")
                if "likely already running" in startup_detail:
                    self.app._log_connection(startup_detail)
        except subprocess.TimeoutExpired:
            self.app._log_connection("ollama serve is still running after startup attempt; probing /api/tags.")
            self.app.events.put(("ollama_started", ""))
            return
        self.probe_after_start_attempt(startup_detail)

    def probe_after_start_attempt(self, startup_detail: str) -> None:
        status = self.app.ai.check_connection()
        status = status_with_startup_detail(status, startup_detail)
        self.app._log_connection(f"Post-start probe {status.url}: reachable={status.reachable}; detail={status.detail}")
        self.app.events.put(("ollama_status", status))
