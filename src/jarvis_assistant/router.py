from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .config import Settings


LOCAL_PROVIDER = "ollama"
CLOUD_PROVIDER = "cloud-disabled"


@dataclass(frozen=True)
class RoutingDecision:
    provider: str
    reason: str
    cloud_data_sent: bool = False


class ProviderRouter:
    COMPLEX_PATTERN = re.compile(
        r"\b(research|analyze|plan|compare|summari[sz]e|strategy|write|draft|explain|debug|design)\b",
        re.IGNORECASE,
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(self, text: str) -> RoutingDecision:
        if self.settings.free_only_mode:
            return RoutingDecision(LOCAL_PROVIDER, "Free-only mode is enabled; paid cloud providers are blocked.")
        if not self.settings.enable_cloud_provider:
            return RoutingDecision(LOCAL_PROVIDER, "Cloud provider disabled in settings.")
        if not os.environ.get("OPENAI_API_KEY"):
            return RoutingDecision(LOCAL_PROVIDER, "Cloud provider enabled but OPENAI_API_KEY is not configured.")
        if len(text) > 500 or self.COMPLEX_PATTERN.search(text):
            return RoutingDecision(
                self.settings.cloud_provider,
                "Complex request routed to optional cloud provider.",
                cloud_data_sent=True,
            )
        return RoutingDecision(LOCAL_PROVIDER, "Fast local response preferred.")
