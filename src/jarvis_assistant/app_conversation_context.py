from __future__ import annotations

from typing import Any

from .ai import ChatMessage


def approved_docs_context_message(docs: list[str]) -> str | None:
    if not docs:
        return None
    return "Approved local document excerpts:\n" + "\n\n".join(docs)


def memory_context_message(memories: list[dict[str, Any]]) -> str | None:
    if not memories:
        return None
    return "Inspectable long-term memory:\n" + "\n".join(str(memory["content"]) for memory in memories)


class ConversationContextBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def messages_with_context(self, text: str) -> list[ChatMessage]:
        app = self.app
        messages = app.history.for_provider()
        if app.settings.enable_retrieval:
            docs_message = approved_docs_context_message(app.retriever.search(text))
            if docs_message is not None:
                messages.append(ChatMessage("system", docs_message))
        memories = app.memory.list_memories()[:8] if app.settings.enable_long_term_memory else []
        memory_message = memory_context_message(memories)
        if memory_message is not None:
            messages.append(ChatMessage("system", memory_message))
        return messages
