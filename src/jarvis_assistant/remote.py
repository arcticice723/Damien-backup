from __future__ import annotations

import html
import hmac
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import urllib.parse
import uuid
from dataclasses import dataclass
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


@dataclass
class RemoteRequest:
    request_id: str
    text: str
    event: threading.Event
    response: str = ""


class RemoteControlServer:
    def __init__(
        self,
        host: str,
        port: int,
        pin: str,
        command_callback: Callable[[str, str], None],
        status_callback: Callable[[], dict[str, str]],
    ) -> None:
        self.host = host
        self.port = port
        self.pin = pin
        self.command_callback = command_callback
        self.status_callback = status_callback
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.requests: dict[str, RemoteRequest] = {}
        self.lock = threading.Lock()

    def start(self) -> None:
        self.server = ThreadingHTTPServer((self.host, self.port), self._handler())
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def submit_command(self, text: str, timeout_seconds: float = 90.0) -> str:
        request_id = _request_id()
        request = RemoteRequest(request_id, text, threading.Event())
        with self.lock:
            self.requests[request_id] = request
        self.command_callback(request_id, text)
        request.event.wait(timeout_seconds)
        with self.lock:
            self.requests.pop(request_id, None)
        return request.response or "Command sent. Damien is still working."

    def complete(self, request_id: str, response: str) -> None:
        with self.lock:
            request = self.requests.get(request_id)
        if request is not None:
            request.response = response
            request.event.set()

    @property
    def local_url(self) -> str:
        return f"http://{_lan_ip()}:{self.port}"

    @property
    def tailscale_url(self) -> str | None:
        address = _tailscale_ipv4()
        return f"http://{address}:{self.port}" if address else None

    @property
    def tailscale_installed(self) -> bool:
        return _tailscale_executable() is not None

    @property
    def tailscale_serve_url(self) -> str | None:
        executable = _tailscale_executable()
        if not executable:
            return None
        try:
            result = subprocess.run(
                [executable, "serve", "status"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        match = re.search(r"https://[^\s|()]+", result.stdout)
        return match.group(0).rstrip(".,;") if match else None

    def _handler(self):
        remote = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args) -> None:
                return

            def do_GET(self) -> None:
                if self.path.startswith("/api/status"):
                    values = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    if not hmac.compare_digest(values.get("pin", [""])[0], remote.pin):
                        self._send_json({"error": "Invalid password."}, status=403)
                        return
                    self._send_json(remote.status_callback())
                    return
                self._send_html(_page(remote.local_url))

            def do_POST(self) -> None:
                if self.path != "/api/command":
                    self._send_json({"error": "Not found."}, status=404)
                    return
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0 or length > 16_384:
                    self._send_json({"error": "Invalid request size."}, status=413)
                    return
                raw = self.rfile.read(length).decode("utf-8", errors="ignore")
                content_type = self.headers.get("Content-Type", "")
                try:
                    if "application/json" in content_type:
                        payload = json.loads(raw or "{}")
                    else:
                        form = urllib.parse.parse_qs(raw)
                        payload = {key: values[0] if values else "" for key, values in form.items()}
                except (json.JSONDecodeError, TypeError):
                    self._send_json({"error": "Invalid request."}, status=400)
                    return
                if not hmac.compare_digest(str(payload.get("pin", "")), remote.pin):
                    self._send_json({"error": "Invalid password."}, status=403)
                    return
                text = str(payload.get("text", "")).strip()
                if not text:
                    self._send_json({"error": "Empty command."}, status=400)
                    return
                self._send_json({"response": remote.submit_command(text)})

            def _send_html(self, body: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(encoded)

            def _send_json(self, payload: dict, status: int = 200) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(encoded)

        return Handler


def _page(local_url: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#101820">
<title>Damien Remote</title>
<style>
:root {{ color-scheme: dark; font-family: "Segoe UI", system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: radial-gradient(ellipse at 50% -20%, #213d46 0, #101820 54%); color: #edf5f7; }}
main {{ width: min(100%, 760px); margin: 0 auto; padding: 32px 18px; }}
header {{ margin: 0 auto 20px; max-width: 620px; }}
.eyebrow {{ color: #64d7c0; letter-spacing: .12em; text-transform: uppercase; font-size: 12px; font-weight: 700; }}
h1 {{ margin: 8px 0 6px; font-size: clamp(28px, 7vw, 38px); line-height: 1.1; }}
p {{ color: #aebdc3; line-height: 1.5; }}
.panel {{ max-width: 620px; margin: 0 auto; background: #18242b; border: 1px solid #2d4149; border-radius: 18px; padding: clamp(18px, 5vw, 28px); box-shadow: 0 20px 60px #0005; }}
label {{ display: block; margin: 16px 0 7px; color: #cad7da; font-weight: 650; font-size: 14px; }}
input, textarea {{ width: 100%; border: 1px solid #40565e; border-radius: 10px; background: #101a20; color: #f3fafb; padding: 13px 14px; font: inherit; outline: none; }}
input:focus, textarea:focus {{ border-color: #64d7c0; box-shadow: 0 0 0 3px #64d7c022; }}
textarea {{ min-height: 120px; resize: vertical; }}
button {{ width: 100%; margin-top: 16px; border: 0; border-radius: 10px; background: #64d7c0; color: #102321; padding: 14px 18px; font: inherit; font-weight: 750; cursor: pointer; }}
button:disabled {{ opacity: .65; cursor: wait; }}
.hint {{ font-size: 13px; margin-top: 16px; overflow-wrap: anywhere; }}
h2 {{ font-size: 16px; margin: 22px 0 8px; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; border: 1px solid #2d4149; border-radius: 10px; background: #101a20; color: #d9e5e8; padding: 14px; min-height: 76px; }}
</style>
</head>
<body>
<main>
<header>
<div class="eyebrow">Local companion</div>
<h1>Damien Remote</h1>
<p>Connect to Damien on your PC using your phone password.</p>
<p class="hint">Home Wi-Fi uses unencrypted HTTP. For away access, use your Tailscale HTTPS address for encrypted connections.</p>
</header>
<div class="panel">
<form id="command-form">
<label for="password">Password</label>
<input id="password" name="password" type="password" autocomplete="current-password" required>
<label for="text">Command</label>
<textarea id="text" name="text" placeholder="Ask Damien to help with something…" required></textarea>
<button id="send" type="submit">Send to Damien</button>
</form>
<p class="hint">This PC: <span id="portal-url">{html.escape(local_url)}</span></p>
<h2>Response</h2>
<pre id="response" aria-live="polite">Ready.</pre>
</div>
</main>
<script>
const form = document.getElementById('command-form');
const response = document.getElementById('response');
const send = document.getElementById('send');
document.getElementById('portal-url').textContent = window.location.origin;
form.addEventListener('submit', async (event) => {{
  event.preventDefault();
  send.disabled = true;
  response.textContent = 'Damien is working…';
  const payload = {{ pin: form.password.value, text: form.text.value }};
  try {{
    const result = await fetch('/api/command', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload)
    }});
    const json = await result.json();
    response.textContent = json.response || json.error || 'No response.';
  }} catch (_error) {{
    response.textContent = 'Could not reach Damien. Check the Wi-Fi or Tailscale connection on both devices.';
  }} finally {{
    send.disabled = false;
  }}
}});
</script>
</body>
</html>"""


def _request_id() -> str:
    return uuid.uuid4().hex


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _tailscale_ipv4() -> str | None:
    executable = _tailscale_executable()
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "ip", "-4"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for value in result.stdout.split():
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if address.version == 4 and address in ipaddress.ip_network("100.64.0.0/10"):
            return str(address)
    return None


def _tailscale_executable() -> str | None:
    candidates = [shutil.which("tailscale.exe"), shutil.which("tailscale")]
    roots = [
        Path(value)
        for value in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))
        if value
    ]
    candidates.extend(str(root / "Tailscale" / "tailscale.exe") for root in roots)
    candidates.extend(str(root / "Tailscale IPN" / "tailscale.exe") for root in roots)
    return next((path for path in candidates if path and Path(path).is_file()), None)
