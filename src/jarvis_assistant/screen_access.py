from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Any

if TYPE_CHECKING:
    from PIL import Image

from .improvement import ImprovementQueue
from .runtime import APP_ROOT

CaptureFunction = Callable[[], "Image.Image"]
OcrFunction = Callable[[Path], str]


@dataclass(frozen=True)
class ScreenCapture:
    path: Path
    width: int
    height: int


class ScreenReader:
    def __init__(
        self,
        root: Path = APP_ROOT,
        capture: CaptureFunction | None = None,
        ocr: OcrFunction | None = None,
    ) -> None:
        self.root = root
        self.capture = capture or _default_capture
        self.ocr = ocr

    def read_screen(self) -> str:
        if not self.screen_access_enabled():
            return "Screen access is disabled in Damien settings."
        try:
            result = self.capture_screen()
        except Exception as exc:
            return f"Screen capture failed: {exc}"
        return (
            f"I captured your screen ({result.width}x{result.height}) and saved it here: {result.path}. "
            "Visual description and OCR are the next layer to connect."
        )

    def understand_screen(self, request: str = "read my screen") -> str:
        if not self.screen_access_enabled():
            return "Screen access is disabled in Damien settings."
        try:
            result = self.capture_screen()
        except Exception as exc:
            return f"Screen capture failed: {exc}"
        text = self.ocr(result.path).strip() if self.ocr is not None else _visible_accessibility_text()
        if text:
            return f"I captured your screen ({result.width}x{result.height}). Visible text and controls: {text[:6000]}"
        ImprovementQueue(self.root).log(
            request=request,
            reason="Damien captured the screen but no OCR or vision backend returned readable content.",
            suggestion="Add an OCR or vision backend so Damien can describe screenshots instead of only saving them.",
        )
        return (
            f"I captured your screen ({result.width}x{result.height}) and saved it here: {result.path}. "
            "I still need an OCR or vision backend before I can describe it reliably, so I logged that upgrade for Codex."
        )

    def click_visible_button(self, label: str) -> str:
        if not self.screen_access_enabled():
            return "Screen access is disabled in Damien settings."
        wanted = " ".join(label.casefold().split())
        if not wanted:
            return "Tell me the exact visible button label to click."
        try:
            from pywinauto import Desktop

            matches = []
            for window in Desktop(backend="uia").windows(visible_only=True):
                for control in window.descendants(control_type="Button"):
                    try:
                        name = " ".join(str(control.window_text()).casefold().split())
                        if name == wanted and control.is_visible() and control.is_enabled():
                            matches.append((window, control))
                    except Exception:
                        continue
            if len(matches) != 1:
                if not matches:
                    return f"I could not find one enabled visible button named {label!r}."
                return f"More than one visible button is named {label!r}; identify the window first."
            window, control = matches[0]
            window.set_focus()
            control.click_input()
            return f"Clicked the visible button {label!r}."
        except Exception as exc:
            return f"Computer control could not click that button: {exc}"

    def capture_screen(self) -> ScreenCapture:
        image = self.capture()
        output_dir = self._capture_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = output_dir / f"screen-{stamp}.png"
        image.save(path)
        return ScreenCapture(path=path, width=image.width, height=image.height)

    def screen_access_enabled(self) -> bool:
        return bool(self._settings_payload().get("screen_access_enabled", True))

    def _capture_dir(self) -> Path:
        value = str(self._settings_payload().get("screen_capture_dir", "screenshots")).strip()
        if not value:
            value = "screenshots"
        path = Path(value)
        if not path.is_absolute():
            path = self.root / path
        return path

    def _settings_payload(self) -> dict[str, object]:
        path = self.root / "config" / "settings.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}


def _default_capture() -> Any:
    try:
        from PIL import ImageGrab
    except Exception as exc:
        raise RuntimeError("Pillow is not installed, so screen capture is unavailable.") from exc
    return ImageGrab.grab()


def _visible_accessibility_text() -> str:
    try:
        from pywinauto import Desktop
    except Exception:
        return ""
    collected: list[str] = []
    try:
        windows = Desktop(backend="uia").windows(visible_only=True)
    except Exception:
        return ""
    for window in windows[:10]:
        try:
            title = str(window.window_text()).strip()
            if title:
                collected.append(title)
            for control in window.descendants():
                try:
                    name = str(control.window_text()).strip()
                    if name and name not in collected:
                        collected.append(name)
                    if len(collected) >= 120:
                        break
                except Exception:
                    continue
        except Exception:
            continue
    return " | ".join(collected)
