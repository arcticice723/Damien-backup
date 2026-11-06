from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


class BrowserAutomationError(RuntimeError):
    pass


class ChromeController:
    def __init__(self, user_data_dir: Path, port: int = 9223) -> None:
        self.user_data_dir = user_data_dir
        self.port = port

    def open_crunchyroll_title(self, title: str, profile_name: str = "") -> str:
        value = title.strip(" .")
        if not value:
            return "I need a show title to open in Crunchyroll."
        self._ensure_chrome()
        search_url = "https://www.crunchyroll.com/search?q=" + urllib.parse.quote(value)
        if profile_name.strip():
            self._navigate("https://www.crunchyroll.com/profiles/select")
            clicked = self._click_text(profile_name.strip(), timeout_seconds=8)
            self._navigate(search_url)
            if clicked:
                return f"Opened Crunchyroll for {value} using profile {profile_name.strip()}."
            return (
                f"Opened Crunchyroll for {value}, but I could not confirm the {profile_name.strip()} profile. "
                "If the profile picker is showing, choose it once and try again."
            )
        self._navigate(search_url)
        return f"Opened Crunchyroll for {value}."

    def _ensure_chrome(self) -> None:
        if self._json("json/version", timeout=1.0) is not None:
            return
        chrome = _chrome_path()
        if chrome is None:
            raise BrowserAutomationError("Google Chrome was not found.")
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [
                str(chrome),
                f"--remote-debugging-port={self.port}",
                f"--user-data-dir={self.user_data_dir}",
                "--no-first-run",
                "--new-window",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            if self._json("json/version", timeout=1.0) is not None:
                return
            time.sleep(0.25)
        raise BrowserAutomationError("Chrome did not start its local control port.")

    def _navigate(self, url: str) -> None:
        tab = self._first_tab()
        with _DevToolsSocket(tab["webSocketDebuggerUrl"]) as ws:
            ws.call("Page.enable")
            ws.call("Runtime.enable")
            ws.call("Page.navigate", {"url": url})
            self._wait_ready(ws)

    def _click_text(self, text: str, timeout_seconds: float = 6.0) -> bool:
        requested = text.casefold()
        script = f"""
(() => {{
  const wanted = {json.dumps(requested)};
  const nodes = Array.from(document.querySelectorAll('button, a, [role="button"], [tabindex], div, span'));
  const target = nodes.find((node) => {{
    const label = ((node.innerText || node.textContent || node.getAttribute('aria-label') || '') + '').trim().toLowerCase();
    return label === wanted || label.includes(wanted);
  }});
  if (!target) return false;
  target.scrollIntoView({{block: 'center', inline: 'center'}});
  target.click();
  return true;
}})()
"""
        deadline = time.time() + timeout_seconds
        tab = self._first_tab()
        with _DevToolsSocket(tab["webSocketDebuggerUrl"]) as ws:
            ws.call("Runtime.enable")
            while time.time() < deadline:
                response = ws.call("Runtime.evaluate", {"expression": script, "returnByValue": True})
                value = response.get("result", {}).get("result", {}).get("value")
                if value is True:
                    time.sleep(0.75)
                    return True
                time.sleep(0.35)
        return False

    def _wait_ready(self, ws: "_DevToolsSocket", timeout_seconds: float = 8.0) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response = ws.call(
                "Runtime.evaluate",
                {"expression": "document.readyState", "returnByValue": True},
            )
            state = response.get("result", {}).get("result", {}).get("value")
            if state in {"interactive", "complete"}:
                return
            time.sleep(0.2)

    def _first_tab(self) -> dict:
        tabs = self._json("json", timeout=2.0)
        if not isinstance(tabs, list):
            raise BrowserAutomationError("Chrome control tab list is unavailable.")
        for tab in tabs:
            if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
                return tab
        raise BrowserAutomationError("Chrome has no controllable page tab.")

    def _json(self, path: str, timeout: float) -> object | None:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/{path}", timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None


class _DevToolsSocket:
    def __init__(self, websocket_url: str) -> None:
        parsed = urllib.parse.urlparse(websocket_url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        self.sock: socket.socket | None = None
        self.next_id = 1

    def __enter__(self) -> "_DevToolsSocket":
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response:
            raise BrowserAutomationError("Chrome DevTools websocket handshake failed.")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        if expected not in response:
            raise BrowserAutomationError("Chrome DevTools websocket verification failed.")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.sock is not None:
            self.sock.close()

    def call(self, method: str, params: dict | None = None) -> dict:
        message_id = self.next_id
        self.next_id += 1
        self._send_json({"id": message_id, "method": method, "params": params or {}})
        while True:
            message = self._recv_json()
            if message.get("id") == message_id:
                return message

    def _send_json(self, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend([0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, "big"))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        assert self.sock is not None
        self.sock.sendall(bytes(header) + mask + masked)

    def _recv_json(self) -> dict:
        assert self.sock is not None
        while True:
            first = self.sock.recv(2)
            if len(first) < 2:
                raise BrowserAutomationError("Chrome DevTools websocket closed.")
            opcode = first[0] & 0x0F
            length = first[1] & 0x7F
            if length == 126:
                length = int.from_bytes(self.sock.recv(2), "big")
            elif length == 127:
                length = int.from_bytes(self.sock.recv(8), "big")
            data = _recv_exact(self.sock, length)
            if opcode == 1:
                return json.loads(data.decode("utf-8"))
            if opcode == 8:
                raise BrowserAutomationError("Chrome DevTools websocket closed.")


def _recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < length:
        chunk = sock.recv(length - len(chunks))
        if not chunk:
            raise BrowserAutomationError("Chrome DevTools websocket closed.")
        chunks.extend(chunk)
    return bytes(chunks)


def _chrome_path() -> Path | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
