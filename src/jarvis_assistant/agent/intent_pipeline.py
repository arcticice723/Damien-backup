from __future__ import annotations

from collections.abc import Callable

DirectIntentHandler = Callable[[str], str | None]


class DirectIntentPipeline:
    def __init__(self, handlers: list[DirectIntentHandler] | None = None) -> None:
        self.handlers = handlers or []

    def handle(self, text: str) -> str | None:
        for handler in self.handlers:
            response = handler(text)
            if response is not None:
                return response
        return None
