from __future__ import annotations

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _parse_tv_payload(body: bytes) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace").strip()
    # TradingView can send JSON or plain text
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    upper = text.upper()
    side = None
    if "BUY" in upper:
        side = "BUY"
    elif "SELL" in upper:
        side = "SELL"
    return {"action": side or text, "raw": text}


class WebhookHandler(BaseHTTPRequestHandler):
    secret: str = ""
    on_signal: Callable[[dict[str, Any]], None] | None = None

    def log_message(self, fmt: str, *args) -> None:
        logger.info("webhook " + fmt, *args)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/tv", "/webhook/tradingview"}:
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        token = self.headers.get("X-Webhook-Secret", "")
        q = urlparse(self.path).query
        if "secret=" in q:
            token = q.split("secret=")[-1].split("&")[0] or token

        if self.secret and token != self.secret:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}')
            return

        payload = _parse_tv_payload(body)
        logger.info("TradingView alert: %s", payload)
        if self.on_signal:
            try:
                self.on_signal(payload)
            except Exception:
                logger.exception("on_signal failed")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error":"handler failed"}')
                return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


def start_webhook_server(
    on_signal: Callable[[dict[str, Any]], None],
    *,
    host: str = "0.0.0.0",
    port: int = 8787,
    secret: str | None = None,
) -> ThreadingHTTPServer:
    WebhookHandler.secret = secret or os.getenv("WEBHOOK_SECRET", "")
    WebhookHandler.on_signal = on_signal
    server = ThreadingHTTPServer((host, port), WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("TradingView webhook listening on http://%s:%s/tv", host, port)
    return server
