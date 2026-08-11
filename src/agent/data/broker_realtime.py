"""Broker realtime market-data provider stub.

Expected external integration (Tradovate Market Data websocket / Rithmic / TopstepX):
- Authenticated MD session (separate from order API credentials in many setups)
- Front-month contract mapping (e.g. MES → MESH6)
- Tick/bar aggregation to the agent bar interval
- Heartbeat + reconnect

This class exposes the same MarketDataProvider interface. Without credentials /
subscription it reports unhealthy and raises DATA_ERROR — never invents prices.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from agent.data.base import Bar, MarketDataProvider, ProviderHealth


class BrokerRealtimeProvider(MarketDataProvider):
    """Realtime adapter scaffold. Requires broker MD session to become operational."""

    REQUIRED_ENV = (
        "TRADOVATE_USERNAME",
        "TRADOVATE_PASSWORD",
        "TRADOVATE_CID",
        "TRADOVATE_SEC",
        # MD often needs: TRADOVATE_MD_URL / market data entitlement on the account
    )

    def __init__(self, cfg: dict[str, Any] | None = None):
        self.cfg = cfg or {}
        md = self.cfg.get("market_data") or {}
        self._url = str(md.get("realtime_url") or "")
        self._connected = False
        self._last_success: Optional[datetime] = None
        self._last_error: Optional[str] = "NOT_CONNECTED: broker MD session not established"
        self._failures = 0
        self._bars: dict[str, list[Bar]] = {}
        self._last_bar_ts: dict[str, datetime] = {}

    def connect(self) -> None:
        """Establish MD websocket — not implemented without vendor SDK/credentials."""
        raise NotImplementedError(
            "BrokerRealtimeProvider.connect requires Tradovate/TopstepX market-data "
            "websocket credentials + contract mapping. Set market_data.provider=yahoo_delayed "
            "for paper/research only. See LIVE_READINESS_REPORT section K/N."
        )

    def get_bars(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> list[Bar]:
        self._failures += 1
        self._last_error = (
            f"DATA_ERROR: realtime provider not connected for {symbol}. "
            "External: Tradovate MD websocket + CME market data entitlement + front-month map."
        )
        raise RuntimeError(self._last_error)

    def get_latest_bar(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> Bar:
        return self.get_bars(symbol, interval=interval, period=period)[-1]

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            source="broker_realtime",
            last_success_utc=self._last_success,
            last_error=self._last_error,
            consecutive_failures=self._failures,
            is_healthy=False,
        )

    def validate_bar(self, bar: Bar) -> list[str]:
        """Timestamp / freshness / duplicate / out-of-order checks."""
        issues: list[str] = []
        if bar.timestamp.tzinfo is None:
            issues.append("TIMESTAMP_NAIVE")
        prev = self._last_bar_ts.get(bar.symbol)
        if prev is not None:
            if bar.timestamp == prev:
                issues.append("DUPLICATE_BAR")
            if bar.timestamp < prev:
                issues.append("OUT_OF_ORDER_BAR")
        now = datetime.now(timezone.utc)
        age = (now - bar.timestamp.astimezone(timezone.utc)).total_seconds()
        max_age = float((self.cfg.get("market_data") or {}).get("realtime_stale_seconds", 30))
        if age > max_age:
            issues.append("STALE_BAR")
        if not issues:
            self._last_bar_ts[bar.symbol] = bar.timestamp
        return issues

    def external_dependencies(self) -> list[dict[str, str]]:
        return [
            {
                "item": "Tradovate API credentials",
                "env": "TRADOVATE_USERNAME, TRADOVATE_PASSWORD, TRADOVATE_CID, TRADOVATE_SEC",
                "status": "required",
            },
            {
                "item": "Tradovate account id/spec",
                "env": "TRADOVATE_ACCOUNT_ID / TRADOVATE_ACCOUNT_SPEC",
                "status": "required for orders",
            },
            {
                "item": "CME market data entitlement on demo/live account",
                "env": "account subscription (not a local env var)",
                "status": "required for realtime bars",
            },
            {
                "item": "Market data websocket URL / SDK",
                "env": "market_data.realtime_url + Tradovate MD websocket",
                "status": "not implemented",
            },
            {
                "item": "Front-month contract mapping",
                "env": "instruments.*.tradovate_symbol (e.g. MESH6)",
                "status": "required before live brackets",
            },
            {
                "item": "ALLOW_LIVE_TRADING=1 + mode:live",
                "env": "ALLOW_LIVE_TRADING",
                "status": "explicit approval gate",
            },
        ]
