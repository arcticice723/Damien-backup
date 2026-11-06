from __future__ import annotations

import threading
from collections.abc import Callable


class TrayController:
    def __init__(
        self,
        restore: Callable[[], None],
        quit_app: Callable[[], None],
        toggle_mic: Callable[[], None],
        status_text: Callable[[], str],
    ) -> None:
        self.restore = restore
        self.quit_app = quit_app
        self.toggle_mic = toggle_mic
        self.status_text = status_text
        self.icon = None
        self.available = False
        self.error = ""

    def start(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError as exc:
            self.error = f"Tray dependencies are missing: {exc}"
            return

        image = Image.new("RGBA", (64, 64), (16, 20, 24, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill=(31, 122, 77, 255))
        draw.text((24, 20), "D", fill=(255, 255, 255, 255))

        self.icon = pystray.Icon(
            "Damien",
            image,
            "Damien",
            menu=pystray.Menu(
                pystray.MenuItem(lambda _item: self.status_text(), None, enabled=False),
                pystray.MenuItem("Restore", lambda _icon, _item: self.restore()),
                pystray.MenuItem("Mute/Unmute Microphone", lambda _icon, _item: self.toggle_mic()),
                pystray.MenuItem("Quit", lambda _icon, _item: self.quit_app()),
            ),
        )
        self.available = True
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self) -> None:
        if self.icon is not None:
            self.icon.stop()
            self.icon = None
