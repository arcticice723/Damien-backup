from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher, get_close_matches


@dataclass(frozen=True)
class Interpretation:
    original: str
    corrected: str
    changed: bool
    reason: str = ""


class UtteranceInterpreter:
    """Small local typo/STT cleanup layer for command routing."""

    COMMAND_WORDS = {
        "open",
        "launch",
        "start",
        "list",
        "show",
        "search",
        "find",
        "look",
        "copy",
        "remember",
        "note",
        "notes",
        "clipboard",
        "approved",
        "apps",
        "documents",
        "files",
        "web",
        "internet",
        "online",
        "status",
        "time",
        "date",
        "play",
        "watch",
        "continue",
        "resume",
        "shuffle",
        "set",
        "use",
        "switch",
        "crunchyroll",
        "itunes",
        "profile",
        "playlist",
    }
    WORD_CORRECTIONS = {
        "oppen": "open",
        "opem": "open",
        "opin": "open",
        "lunch": "launch",
        "lanch": "launch",
        "launce": "launch",
        "starch": "start",
        "surch": "search",
        "serch": "search",
        "fin": "find",
        "dockuments": "documents",
        "documints": "documents",
        "aps": "apps",
        "apz": "apps",
        "clipbord": "clipboard",
        "rember": "remember",
        "dime": "time",
        "thyme": "time",
        "pla": "play",
        "pley": "play",
        "wach": "watch",
        "crunchyrole": "crunchyroll",
        "crunchyrol": "crunchyroll",
    }
    PHRASE_CORRECTIONS = (
        (re.compile(r"\bi\s+tunes\b", re.IGNORECASE), "itunes"),
        (re.compile(r"\bcrunchy\s+roll\b", re.IGNORECASE), "crunchyroll"),
        (re.compile(r"\bape(?:g|x)['’]?s?\s+legends?\b", re.IGNORECASE), "apex legends"),
        (re.compile(r"\bno\s+mans\s+sky\b", re.IGNORECASE), "no man's sky"),
    )

    def interpret(self, text: str) -> Interpretation:
        cleaned = self._basic_cleanup(text)
        corrected = self._correct_phrases(cleaned)
        corrected = self._correct_words(corrected)
        corrected = self._correct_common_questions(corrected)
        corrected = re.sub(r"\s+", " ", corrected).strip()
        changed = corrected.casefold() != text.strip().casefold()
        return Interpretation(text, corrected, changed, "local typo/STT cleanup" if changed else "")

    def _basic_cleanup(self, text: str) -> str:
        text = text.strip()
        text = text.replace("’", "'")
        text = re.sub(r"[!?]+$", "", text)
        text = re.sub(r"\s+", " ", text)
        text = _strip_wake_prefix(text)
        text = _strip_polite_prefix(text)
        return text

    def _correct_phrases(self, text: str) -> str:
        corrected = text
        for pattern, replacement in self.PHRASE_CORRECTIONS:
            corrected = pattern.sub(replacement, corrected)
        return corrected

    def _correct_words(self, text: str) -> str:
        words = re.findall(r"[a-zA-Z0-9']+|[^a-zA-Z0-9']+", text)
        corrected: list[str] = []
        for word in words:
            if not re.match(r"[a-zA-Z0-9']+$", word):
                corrected.append(word)
                continue
            lower = word.lower().strip("'")
            replacement = self.WORD_CORRECTIONS.get(lower)
            if replacement is None and len(lower) >= 4:
                close = get_close_matches(lower, self.COMMAND_WORDS, n=1, cutoff=0.84)
                replacement = close[0] if close else None
            corrected.append(_match_case(word, replacement) if replacement else word)
        return "".join(corrected)

    def _correct_common_questions(self, text: str) -> str:
        lower = text.lower().strip(" .")
        if _similar(lower, "what time is it") >= 0.82:
            return "what time is it"
        if _similar(lower, "what apps can you open") >= 0.82:
            return "what apps can you open"
        if _similar(lower, "list approved apps") >= 0.82:
            return "list approved apps"
        return text


def _match_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if original[:1].isupper():
        return replacement.capitalize()
    return replacement


def _similar(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def _strip_wake_prefix(text: str) -> str:
    return re.sub(
        r"^\s*(?:hey\s+)?(?:damien|damian|daemon|daymien|daymian|damon)[,\s]+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _strip_polite_prefix(text: str) -> str:
    return re.sub(
        r"^\s*(?:(?:can|could|would)\s+you\s+|please\s+|will\s+you\s+)+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
