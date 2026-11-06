from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterable

from .base import ChatMessage, GenerationStats, StreamEvent


class OpenAICloudProvider:
    def __init__(
        self,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.25,
        timeout: int = 180,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def stream(self, messages: list[ChatMessage], tools: list[dict] | None = None) -> Iterable[StreamEvent]:
        del tools
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Cloud provider is enabled, but OPENAI_API_KEY is not configured.")
        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "temperature": self.temperature,
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Cloud chat request failed. HTTP {exc.code} {exc.reason}. Response body: {body}") from exc
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content:
            yield StreamEvent("text", content)
        usage = data.get("usage", {})
        yield StreamEvent(
            "done",
            stats=GenerationStats(
                elapsed_seconds=max(time.perf_counter() - started, 0.001),
                prompt_eval_count=int(usage.get("prompt_tokens") or 0),
                eval_count=int(usage.get("completion_tokens") or 0),
            ),
        )

