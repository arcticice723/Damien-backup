from __future__ import annotations

import queue
from typing import Any

from .ai import OllamaProvider, OpenAICloudProvider
from .app_events import DamienEventDispatcher
from .audit import AuditLogger
from .audio import SoundDeviceRecorder
from .commands import CommandDispatcher
from .conversation import ConversationHistory
from .improvement import ImprovementQueue
from .memory import LongTermMemory
from .orchestrator import AssistantOrchestrator
from .retrieval import ApprovedDocumentRetriever
from .router import ProviderRouter
from .runtime import APP_ROOT
from .tools import ToolRegistry


SERVICE_ROLE_NAMES = [
    "history",
    "commands",
    "local_ai",
    "cloud_ai",
    "retrieval",
    "memory",
    "audit",
    "improvement_queue",
    "tools",
    "orchestrator",
    "recorder",
    "events",
]


def app_service_role_names() -> list[str]:
    return list(SERVICE_ROLE_NAMES)


def ollama_runtime_base_url(settings: Any) -> str:
    remote_url = getattr(settings, "remote_brain_base_url", "").strip().rstrip("/")
    if getattr(settings, "remote_brain_enabled", False) and remote_url:
        return remote_url
    return settings.ollama_base_url


def voice_readiness_status(app: Any) -> str:
    values = []
    for name in ("mic_status", "wake_summary", "voice_summary", "proactive_summary"):
        source = getattr(app, name, None)
        if source is None or not hasattr(source, "get"):
            continue
        value = str(source.get()).strip()
        if value:
            values.append(value)
    if not values:
        return "Voice readiness is not connected to this conversation yet."
    return f"Voice status: {'; '.join(values)}."


def build_local_ollama_provider(settings: Any, model: str) -> OllamaProvider:
    return OllamaProvider(
        model=model,
        base_url=ollama_runtime_base_url(settings),
        temperature=settings.temperature,
        num_ctx=settings.num_ctx,
        thinking_mode=settings.thinking_mode,
    )


class DamienServiceInitializer:
    def __init__(self, app: Any) -> None:
        self.app = app

    def initialize(self) -> None:
        app = self.app
        app.history = ConversationHistory(app.settings.history_path)
        app.commands = CommandDispatcher.from_file(app.settings.approved_apps_path)
        app.ai = build_local_ollama_provider(app.settings, app.settings.model)
        app.cloud_ai = OpenAICloudProvider(
            app.settings.cloud_model,
            temperature=app.settings.temperature,
        )
        app.tools_supported = False
        app.retriever = ApprovedDocumentRetriever(app.settings.approved_documents_dir)
        app.memory = LongTermMemory(app.settings.memory_path, app.settings.enable_long_term_memory)
        app.audit = AuditLogger(app.settings.audit_log_path, app.settings.tool_audit_log_enabled)
        app.improvement_queue = ImprovementQueue(APP_ROOT)
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
        app.recorder = SoundDeviceRecorder(
            save_raw_audio=app.settings.save_raw_audio,
            device_index=app.settings.microphone_device_index,
        )
        app.transcriber = None
        app.tts = None
        app.events = queue.Queue()
        app.event_dispatcher = DamienEventDispatcher(app)
