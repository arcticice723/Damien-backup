from __future__ import annotations

from dataclasses import dataclass

from .ai import ConnectionStatus
from .local_models import recommended_model_summary


@dataclass(frozen=True)
class OllamaStatusView:
    message: str
    summary: str
    privacy: str
    status: str
    banner_bg: str
    banner_fg: str


def cloud_status_text(settings: object) -> str:
    if bool(getattr(settings, "free_only_mode")):
        return (
            f"Free-only mode: on; all model routing stays local through {getattr(settings, 'model')}. "
            "Paid cloud providers are blocked."
        )
    state = "enabled" if bool(getattr(settings, "enable_cloud_provider")) else "disabled"
    return (
        f"Hybrid routing: cloud {state}; local fallback {getattr(settings, 'model')}; "
        f"cloud model {getattr(settings, 'cloud_model')}; risk mode {getattr(settings, 'automation_risk_mode')}."
    )


def model_profile_summary(models: list[str]) -> str:
    summary = recommended_model_summary(models)
    if summary:
        return "Recommended installed models: " + summary
    return "Installed Ollama models appear here after download."


def normalize_connection_status(status: object, ollama_base_url: str) -> ConnectionStatus:
    tags_url = f"{ollama_base_url}/api/tags"
    if isinstance(status, bool):
        return ConnectionStatus(status, tags_url, "")
    if isinstance(status, ConnectionStatus):
        return status
    return ConnectionStatus(False, tags_url, str(status))


def connected_ollama_status_view(
    base_url: str,
    model: str,
    model_exists: bool,
    tools_enabled: bool,
    tools_supported: bool,
) -> OllamaStatusView:
    model_note = "found in ollama list" if model_exists else "not found in ollama list"
    tool_note = "tools enabled" if tools_enabled and tools_supported else "tools disabled for this model"
    return OllamaStatusView(
        message=f"Local Ollama is connected at {base_url}. Model: {model} ({model_note}); {tool_note}.",
        summary=f"{model} connected",
        privacy="Free-only local routing",
        status="Ready. Damien is connected to local Ollama.",
        banner_bg="#17251d",
        banner_fg="#d8f3dc",
    )


def offline_ollama_status_view(base_url: str, status: ConnectionStatus) -> OllamaStatusView:
    return OllamaStatusView(
        message=(
            f"Damien cannot reach the configured local Ollama host: {base_url}. "
            f"Probe: {status.url}. Details: {status.detail or 'No response from /api/tags.'} "
            "Use Start Ollama, Retry, or Open Settings."
        ),
        summary="Ollama offline",
        privacy="",
        status="Ollama is offline. Chat responses are paused until local Ollama is reachable.",
        banner_bg="#2a2020",
        banner_fg="#f7e6d0",
    )
