from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Iterable

from .base import ChatMessage, ConnectionStatus, GenerationStats, StreamEvent


class OllamaProvider:
    def __init__(
        self,
        model: str,
        base_url: str,
        temperature: float,
        num_ctx: int,
        thinking_mode: str = "auto",
        timeout: int = 180,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.thinking_mode = thinking_mode
        self.timeout = timeout

    def is_reachable(self, timeout: int = 3) -> bool:
        return self.check_connection(timeout).reachable

    def check_connection(self, timeout: int = 3) -> ConnectionStatus:
        url = f"{self.base_url}/api/tags"
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout):
                return ConnectionStatus(True, url, "Ollama tags endpoint responded.")
        except urllib.error.HTTPError as exc:
            return ConnectionStatus(False, url, f"HTTP {exc.code}: {exc.reason}")
        except urllib.error.URLError as exc:
            return ConnectionStatus(False, url, self._format_url_error(exc))
        except TimeoutError as exc:
            return ConnectionStatus(False, url, f"Timed out: {exc}")

    def list_models(self, timeout: int = 5) -> list[dict]:
        request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, TypeError):
            return []
        return [model for model in payload.get("models", []) if isinstance(model, dict)]

    def model_exists(self) -> bool:
        return any(self._model_matches(model) for model in self.list_models())

    def model_supports_tools(self) -> bool:
        for model in self.list_models():
            if self._model_matches(model):
                capabilities = model.get("capabilities") or []
                return "tools" in capabilities or "tool" in capabilities
        return False

    def model_supports_thinking(self) -> bool:
        for model in self.list_models():
            if self._model_matches(model):
                capabilities = model.get("capabilities") or []
                return "thinking" in capabilities or "think" in capabilities
        return False

    def stream(self, messages: list[ChatMessage], tools: list[dict] | None = None) -> Iterable[StreamEvent]:
        endpoint = f"{self.base_url}/api/chat"
        payload: dict = {
            "model": self.model,
            "messages": [self._message_to_dict(message) for message in messages],
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
            },
        }
        if tools:
            payload["tools"] = tools
        think = self._think_value()
        if think is not None:
            payload["think"] = think

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    chunk = json.loads(raw_line.decode("utf-8"))
                    message = chunk.get("message", {})
                    thinking = message.get("thinking", "")
                    if thinking:
                        yield StreamEvent("thinking", thinking)
                    content = message.get("content", "")
                    if content:
                        yield StreamEvent("text", content)
                    tool_calls = message.get("tool_calls") or []
                    if tool_calls:
                        yield StreamEvent("tool_calls", tool_calls=tool_calls)
                    if chunk.get("done"):
                        elapsed = max(time.perf_counter() - started, 0.001)
                        eval_count = int(chunk.get("eval_count") or 0)
                        eval_duration_ns = int(chunk.get("eval_duration") or 0)
                        tps = eval_count / (eval_duration_ns / 1_000_000_000) if eval_duration_ns else 0.0
                        yield StreamEvent(
                            "done",
                            stats=GenerationStats(
                                elapsed_seconds=elapsed,
                                prompt_eval_count=int(chunk.get("prompt_eval_count") or 0),
                                eval_count=eval_count,
                                tokens_per_second=tps,
                            ),
                        )
        except urllib.error.HTTPError as exc:
            body = self._read_http_error_body(exc)
            if is_model_load_error(body):
                raise RuntimeError(
                    "Ollama could not load the configured local model because this PC ran out of model memory. "
                    f"Model: {self.model}. Try a smaller local model or reduce context size in Settings. "
                    f"Details: {body or '<empty>'}"
                ) from exc
            raise RuntimeError(
                "Ollama chat request failed. "
                f"Endpoint: {endpoint}. Model: {self.model}. HTTP {exc.code} {exc.reason}. "
                f"Response body: {body or '<empty>'}"
            ) from exc
        except urllib.error.URLError as exc:
            health = self.check_connection()
            if health.reachable:
                raise RuntimeError(
                    f"Ollama is reachable at {health.url}, but the chat request failed. "
                    f"Endpoint: {endpoint}. Model: {self.model}. Details: {self._format_url_error(exc)}"
                ) from exc
            raise RuntimeError(f"Ollama is not reachable at {health.url}. Details: {health.detail}") from exc

    def generate(self, messages: list[ChatMessage]) -> str:
        return "".join(event.content for event in self.stream(messages) if event.kind == "text").strip()

    def _think_value(self) -> bool | None:
        if self.thinking_mode == "auto":
            return None
        if not self.model_supports_thinking():
            return None
        if self.thinking_mode == "on":
            return True
        if self.thinking_mode == "off":
            return False
        return None

    @staticmethod
    def _message_to_dict(message: ChatMessage) -> dict:
        data = {"role": message.role, "content": message.content}
        if message.tool_calls:
            data["tool_calls"] = message.tool_calls
        return data

    @staticmethod
    def _format_url_error(exc: urllib.error.URLError) -> str:
        reason = getattr(exc, "reason", exc)
        return str(reason)

    def _model_matches(self, model: dict) -> bool:
        return self.model in {model.get("name"), model.get("model")}

    @staticmethod
    def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
        try:
            return exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""


def is_model_load_error(text: str) -> bool:
    value = text.lower()
    markers = (
        "unable to allocate",
        "failed to allocate",
        "cuda_host buffer",
        "cudart",
        "out of memory",
        "server process has terminated",
    )
    return any(marker in value for marker in markers)
