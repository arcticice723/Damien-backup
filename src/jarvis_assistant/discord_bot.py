from __future__ import annotations

import asyncio
import json
import re
import threading
import urllib.request
from collections.abc import Callable, Iterable
from typing import Any


UrlOpener = Callable[..., Any]
CommandRunner = Callable[[str, str, str], str]
StatusCallback = Callable[[str], None]


def remote_damien_command(
    base_url: str,
    pin: str,
    text: str,
    *,
    opener: UrlOpener = urllib.request.urlopen,
    timeout: float = 95,
) -> str:
    url = base_url.rstrip("/") + "/api/command"
    payload = json.dumps({"pin": pin, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Damien Discord bridge could not reach the local app: {exc}"
    try:
        data = json.loads(body or "{}")
    except json.JSONDecodeError:
        return "Damien returned a response Discord could not read."
    return str(data.get("response") or data.get("error") or "Damien returned no response.")


def chunk_discord_reply(text: str, limit: int = 1900) -> list[str]:
    value = text or "Done."
    if limit <= 0:
        return [value]
    chunks: list[str] = []
    remaining = value
    while len(remaining) > limit:
        split_at = max(remaining.rfind("\n", 0, limit), remaining.rfind(" ", 0, limit))
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].strip() or remaining[:limit])
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


class DiscordBotBridge:
    def __init__(
        self,
        token: str,
        base_url: str,
        pin: str,
        *,
        allowed_channel_ids: Iterable[int] = (),
        command_runner: CommandRunner = remote_damien_command,
        status_callback: StatusCallback | None = None,
    ) -> None:
        self.token = token
        self.base_url = base_url
        self.pin = pin
        self.allowed_channel_ids = {int(channel_id) for channel_id in allowed_channel_ids}
        self.command_runner = command_runner
        self.status_callback = status_callback
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.client: Any | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, name="DamienDiscordBot", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if not self.client or not self.loop:
            return
        asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)

    def _run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as exc:
            self._status(f"Discord bot stopped: {exc}")

    async def _run_async(self) -> None:
        try:
            import discord
        except ImportError:
            self._status("Discord bot unavailable: install discord.py.")
            return

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        self.client = client
        self.loop = asyncio.get_running_loop()

        @client.event
        async def on_ready() -> None:
            self._status(f"Discord bot connected as {client.user}.")

        @client.event
        async def on_message(message: Any) -> None:
            if message.author == client.user:
                return
            if self.allowed_channel_ids and int(message.channel.id) not in self.allowed_channel_ids:
                return
            if not _should_answer_message(message, client.user):
                return
            text = _clean_message_content(message.content, client.user)
            if not text:
                return
            async with message.channel.typing():
                response = await asyncio.to_thread(self.command_runner, self.base_url, self.pin, text)
            for chunk in chunk_discord_reply(response):
                await message.reply(chunk, mention_author=False)

        await client.start(self.token)

    def _status(self, text: str) -> None:
        if self.status_callback:
            self.status_callback(text)


def _should_answer_message(message: Any, bot_user: Any) -> bool:
    if getattr(message, "guild", None) is None:
        return True
    content = message.content.strip().lower()
    return _mentions_bot(message, bot_user) or content.startswith(("!damien", "damien,", "damien "))


def _mentions_bot(message: Any, bot_user: Any) -> bool:
    return any(getattr(user, "id", None) == getattr(bot_user, "id", None) for user in getattr(message, "mentions", []))


def _clean_message_content(content: str, bot_user: Any) -> str:
    bot_id = getattr(bot_user, "id", None)
    text = content
    if bot_id is not None:
        text = re.sub(rf"<@!?{re.escape(str(bot_id))}>", "", text)
    text = re.sub(r"^!damien\b[:,\s-]*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"^damien\b[:,\s-]*", "", text.strip(), flags=re.IGNORECASE)
    return text.strip()
