from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class Alerter:
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.enabled = bool(cfg.get("alerts", {}).get("enabled", True))
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")

    def send(self, message: str) -> None:
        if not self.enabled:
            return
        logger.info("ALERT: %s", message)
        if self.telegram_token and self.telegram_chat:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
                httpx.post(
                    url,
                    json={"chat_id": self.telegram_chat, "text": message[:3500]},
                    timeout=10,
                )
            except Exception:
                logger.exception("Telegram alert failed")
        if self.discord_webhook:
            try:
                httpx.post(
                    self.discord_webhook,
                    json={"content": message[:1900]},
                    timeout=10,
                )
            except Exception:
                logger.exception("Discord alert failed")
