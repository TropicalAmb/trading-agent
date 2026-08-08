from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from agent.models import AccountSnapshot

logger = logging.getLogger(__name__)


class TradovateClient:
    """Tradovate REST client for Topstep/Tradovate futures accounts.

    Auth: username/password/appId/appVersion → access token
    Docs: demo https://demo.tradovateapi.com/v1  live https://live.tradovateapi.com/v1
    Orders must include isAutomated: true for CME compliance.
    """

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        app_id: str | None = None,
        app_version: str = "1.0",
        device_id: str | None = None,
        cid: str | None = None,
        sec: str | None = None,
        demo: bool = True,
        account_id: int | None = None,
        account_spec: str | None = None,
    ):
        self.username = username or os.getenv("TRADOVATE_USERNAME", "")
        self.password = password or os.getenv("TRADOVATE_PASSWORD", "")
        self.app_id = app_id or os.getenv("TRADOVATE_APP_ID", "Sample App")
        self.app_version = app_version or os.getenv("TRADOVATE_APP_VERSION", "0.0.1")
        self.device_id = device_id or os.getenv("TRADOVATE_DEVICE_ID", "trading-agent")
        self.cid = cid or os.getenv("TRADOVATE_CID", "")
        self.sec = sec or os.getenv("TRADOVATE_SEC", "")
        env_demo = os.getenv("TRADOVATE_DEMO")
        if env_demo is not None:
            self.demo = env_demo.lower() in {"1", "true", "yes"}
        else:
            self.demo = demo
        self.account_id = account_id or (
            int(os.getenv("TRADOVATE_ACCOUNT_ID")) if os.getenv("TRADOVATE_ACCOUNT_ID") else None
        )
        self.account_spec = account_spec or os.getenv("TRADOVATE_ACCOUNT_SPEC", "")
        self.base = (
            "https://demo.tradovateapi.com/v1"
            if self.demo
            else "https://live.tradovateapi.com/v1"
        )
        self._token: Optional[str] = None
        self._connected = False

    def connect(self) -> None:
        if not self.username or not self.password:
            raise RuntimeError(
                "TRADOVATE_USERNAME / TRADOVATE_PASSWORD missing in .env"
            )
        payload = {
            "name": self.username,
            "password": self.password,
            "appId": self.app_id,
            "appVersion": self.app_version,
            "deviceId": self.device_id,
            "cid": self.cid or 0,
            "sec": self.sec or "NA",
        }
        # cid/sec are integers/strings from Tradovate API key application
        if self.cid:
            try:
                payload["cid"] = int(self.cid)
            except ValueError:
                payload["cid"] = self.cid
        with httpx.Client(timeout=30) as client:
            r = client.post(f"{self.base}/auth/accesstokenrequest", json=payload)
            r.raise_for_status()
            data = r.json()
        self._token = data.get("accessToken")
        if not self._token:
            raise RuntimeError(f"Tradovate auth failed: {data}")
        self._connected = True
        logger.info("Tradovate connected demo=%s", self.demo)
        if self.account_id is None:
            accounts = self._get("/account/list")
            if accounts:
                self.account_id = int(accounts[0]["id"])
                self.account_spec = accounts[0].get("name", self.account_spec)
                logger.info(
                    "Using Tradovate account id=%s spec=%s",
                    self.account_id,
                    self.account_spec,
                )

    def disconnect(self) -> None:
        self._connected = False
        self._token = None

    def is_connected(self) -> bool:
        return self._connected and bool(self._token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _get(self, path: str) -> Any:
        with httpx.Client(timeout=30) as client:
            r = client.get(f"{self.base}{path}", headers=self._headers())
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        with httpx.Client(timeout=30) as client:
            r = client.post(f"{self.base}{path}", headers=self._headers(), json=body)
            r.raise_for_status()
            return r.json()

    def get_account_snapshot(self) -> AccountSnapshot:
        # Best-effort cash/equity from account risk / cashBalance endpoints
        equity = 0.0
        try:
            balances = self._get("/cashBalance/list")
            if isinstance(balances, list) and balances:
                # amount fields vary; try common keys
                b0 = balances[0]
                equity = float(b0.get("amount", b0.get("realizedPnL", 0)) or 0)
        except Exception:
            logger.exception("cashBalance list failed")
        return AccountSnapshot(
            equity=equity or 50_000.0,
            cash=equity or 50_000.0,
            buying_power=equity or 50_000.0,
            open_positions=0,
            open_underlyings=[],
            realized_pnl_today=0.0,
            unrealized_pnl=0.0,
            healthy=self.is_connected(),
            notes=["tradovate"],
        )

    def get_spot(self, symbol: str) -> tuple[float, datetime]:
        # Quotes often need market data websocket; fallback for scaffolding
        raise NotImplementedError(
            "Use Yahoo/bar source for signals; Tradovate quotes need MD websocket"
        )

    def place_bracket_order(
        self, signal: Any, *, qty: int = 1, dry_run: bool = True
    ) -> dict[str, Any]:
        detail = {
            "symbol": signal.symbol,
            "side": signal.side,
            "entry": signal.entry,
            "stop": signal.stop,
            "target": signal.target,
            "qty": qty,
            "accountId": self.account_id,
        }
        if dry_run:
            logger.info("DRY RUN Tradovate bracket: %s", detail)
            return {
                "dry_run": True,
                "submitted": False,
                "order_id": None,
                "status": "DRY_RUN",
                "detail": detail,
            }
        if not self.account_id:
            raise RuntimeError("TRADOVATE_ACCOUNT_ID not set")

        action = "Buy" if signal.side == "BUY" else "Sell"
        # Front-month symbol resolution is account/contract specific; caller should
        # pass a Tradovate contract name when ready (e.g. MESH6). For now use symbol.
        body = {
            "accountSpec": self.account_spec,
            "accountId": self.account_id,
            "action": action,
            "symbol": signal.symbol,
            "orderQty": qty,
            "orderType": "Market",
            "isAutomated": True,
        }
        result = self._post("/order/placeorder", body)
        oid = result.get("orderId") or result.get("id")
        logger.info("Tradovate order placed id=%s", oid)
        # TODO: attach OCO stop/target via /order/placeoco once contract ids known
        return {
            "dry_run": False,
            "submitted": True,
            "order_id": str(oid) if oid is not None else None,
            "status": "Submitted",
            "detail": {**detail, "raw": result},
        }
