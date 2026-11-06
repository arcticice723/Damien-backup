from __future__ import annotations

import re


_WAKE_PREFIX = re.compile(
    r"^\s*(?:(?:hey|ok|okay)\s+)?(?:damien|damian|daemon|daymien|daymian|damon)\s*[,;:]?\s*",
    flags=re.IGNORECASE,
)
_POLITE_PREFIX = re.compile(
    r"^\s*(?:(?:please)\s+|(?:(?:can|could|would|will)\s+you\s+))*",
    flags=re.IGNORECASE,
)


def strip_wake_prefix(text: str) -> str:
    without_wake = _WAKE_PREFIX.sub("", text, count=1)
    return _POLITE_PREFIX.sub("", without_wake, count=1)
