from __future__ import annotations

import json
import re
import urllib.parse
import webbrowser
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .runtime import APP_ROOT


@dataclass(frozen=True)
class RobloxGame:
    display_name: str
    target: str
    aliases: tuple[str, ...] = ()


class RobloxGameLauncher:
    def __init__(self, root: Path = APP_ROOT) -> None:
        self.root = root
        self.config_path = root / "config" / "roblox_games.json"

    def open_game(self, requested_name: str) -> str:
        game_name = _clean_game_name(requested_name)
        if not game_name:
            return "Which Roblox game should I open?"
        resolved = self._resolve_game(game_name)
        if resolved is None:
            url = "https://www.roblox.com/discover/?Keyword=" + urllib.parse.quote(game_name)
            webbrowser.open(url)
            return f"I do not have {game_name} saved yet, so I opened Roblox search for it."
        url = _roblox_target_url(resolved.target)
        webbrowser.open(url)
        return f"Opening Roblox game: {resolved.display_name}."

    def _resolve_game(self, requested_name: str) -> RobloxGame | None:
        requested = _normalize_game_name(requested_name)
        games = self._games()
        direct = games.get(requested)
        if direct:
            return direct
        candidates: list[tuple[float, RobloxGame]] = []
        for key, game in games.items():
            names = (key, game.display_name, *game.aliases)
            score = max((_candidate_score(requested, _normalize_game_name(name)) for name in names), default=0.0)
            candidates.append((score, game))
        candidates.sort(key=lambda item: item[0], reverse=True)
        if candidates and candidates[0][0] >= 0.76:
            return candidates[0][1]
        return None

    def _games(self) -> dict[str, RobloxGame]:
        payload = self._payload()
        games: dict[str, RobloxGame] = {}
        for key, value in payload.get("games", {}).items():
            if not isinstance(value, dict):
                continue
            display_name = str(value.get("display_name") or key).strip()
            target = str(value.get("target") or value.get("place_id") or value.get("url") or "").strip()
            aliases = tuple(str(alias).strip() for alias in value.get("aliases", []) if str(alias).strip())
            if not target:
                continue
            game = RobloxGame(display_name=display_name, target=target, aliases=aliases)
            games[_normalize_game_name(key)] = game
            games[_normalize_game_name(display_name)] = game
            for alias in aliases:
                games[_normalize_game_name(alias)] = game
        return {key: value for key, value in games.items() if key}

    def _payload(self) -> dict[str, object]:
        if not self.config_path.exists():
            self._write_default_config()
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return {"games": {}}

    def _write_default_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({"games": {}}, indent=2) + "\n", encoding="utf-8")


def _roblox_target_url(target: str) -> str:
    value = target.strip()
    if value.startswith(("http://", "https://", "roblox:")):
        return value
    if re.fullmatch(r"\d+", value):
        return f"https://www.roblox.com/games/{value}"
    return "https://www.roblox.com/discover/?Keyword=" + urllib.parse.quote(value)


def _clean_game_name(value: str) -> str:
    cleaned = value.strip(" .")
    cleaned = re.sub(r"^(?:game|experience|called|named|the|my)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:game|experience)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned


def _normalize_game_name(value: str) -> str:
    cleaned = value.casefold()
    cleaned = re.sub(r"\b(?:roblox|game|experience|the|my)\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _candidate_score(requested: str, candidate: str) -> float:
    if not requested or not candidate:
        return 0.0
    if requested == candidate:
        return 1.0
    requested_tokens = set(requested.split())
    candidate_tokens = set(candidate.split())
    overlap = len(requested_tokens & candidate_tokens)
    token_score = overlap / max(len(requested_tokens), 1)
    sequence = SequenceMatcher(None, requested, candidate).ratio()
    compact = SequenceMatcher(None, requested.replace(" ", ""), candidate.replace(" ", "")).ratio()
    if requested_tokens and requested_tokens <= candidate_tokens:
        return 0.95
    return max(sequence, compact, token_score)
