from __future__ import annotations

from dataclasses import dataclass


DEFAULT_OLLAMA_MODEL = "llama3:latest"


@dataclass(frozen=True)
class LocalModelProfile:
    name: str
    label: str
    role: str


RECOMMENDED_MODEL_PROFILES = (
    LocalModelProfile("llama3:latest", "Balanced default", "Everyday Damien chat"),
    LocalModelProfile("qwen3:4b", "Smart lightweight", "General reasoning and instruction following"),
    LocalModelProfile("llama3.2:3b", "Fast fallback", "Quick responses and low memory pressure"),
    LocalModelProfile("gemma3:latest", "Compact generalist", "Summaries and broad knowledge"),
    LocalModelProfile("phi4-mini-reasoning:latest", "Reasoning mode", "Harder logic/math prompts"),
    LocalModelProfile("deepseek-r1:latest", "Deep reasoning", "Slow but useful for deliberate thinking"),
    LocalModelProfile("deepseek-coder:latest", "Tiny coding fallback", "Emergency low-memory fallback"),
)

MODEL_FALLBACK_ORDER = (
    "llama3.2:3b",
    "qwen3:4b",
    "gemma3:latest",
    "deepseek-coder:latest",
)


def recommended_model_order(installed_models: list[str]) -> list[str]:
    installed = list(dict.fromkeys(model for model in installed_models if model.strip()))
    recommended_names = [profile.name for profile in RECOMMENDED_MODEL_PROFILES]
    ordered = [model for model in recommended_names if model in installed]
    ordered.extend(model for model in installed if model not in ordered)
    return ordered


def recommended_model_summary(installed_models: list[str]) -> str:
    installed = set(installed_models)
    labels = [f"{profile.name} ({profile.label})" for profile in RECOMMENDED_MODEL_PROFILES if profile.name in installed]
    return ", ".join(labels)


def fallback_model(current_model: str, installed_models: list[str]) -> str | None:
    installed = set(installed_models)
    for model in MODEL_FALLBACK_ORDER:
        if model != current_model and model in installed:
            return model
    return None
