from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from agent.broker.ibkr import BrokerClient

logger = logging.getLogger(__name__)


def pick_expiry(
    expiries: list[date], min_dte: int, max_dte: int, today: date | None = None
) -> date | None:
    today = today or date.today()
    eligible = [
        e for e in expiries if min_dte <= (e - today).days <= max_dte
    ]
    if not eligible:
        return None
    # Prefer nearer expiry inside window
    return min(eligible, key=lambda e: (e - today).days)


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    window = values[-period:]
    return sum(window) / period


def estimate_iv_rank(closes: list[float]) -> float:
    """Placeholder IV rank proxy from realized vol percentile (0-100).

    Real IV rank should come from option IV history; this keeps the gate usable offline.
    """
    if len(closes) < 10:
        return 50.0
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            rets.append(abs(closes[i] / closes[i - 1] - 1))
    if not rets:
        return 50.0
    latest = rets[-1]
    below = sum(1 for r in rets if r <= latest)
    return 100.0 * below / len(rets)


class MarketDataService:
    def __init__(self, broker: BrokerClient, cfg: dict[str, Any]):
        self.broker = broker
        self.cfg = cfg

    def underlying_context(self, symbol: str) -> dict[str, Any]:
        spot, quote_ts = self.broker.get_spot(symbol)
        closes = self.broker.get_historical_closes(
            symbol, days=max(30, int(self.cfg["strategy"].get("trend_sma_period", 20)) + 5)
        )
        period = int(self.cfg["strategy"].get("trend_sma_period", 20))
        trend_sma = sma(closes, period)
        iv_rank = estimate_iv_rank(closes)
        bullish = trend_sma is not None and spot >= trend_sma
        bearish = trend_sma is not None and spot < trend_sma
        quote_age = (datetime.now(timezone.utc) - quote_ts).total_seconds()
        return {
            "symbol": symbol,
            "spot": spot,
            "quote_ts": quote_ts,
            "quote_age_sec": quote_age,
            "closes": closes,
            "sma": trend_sma,
            "bullish": bullish,
            "bearish": bearish,
            "iv_rank": iv_rank,
        }

    def chain_for_window(self, symbol: str) -> tuple[date | None, list[dict[str, Any]]]:
        strat = self.cfg["strategy"]
        expiries = []
        if hasattr(self.broker, "list_option_expiries"):
            expiries = self.broker.list_option_expiries(symbol)
        else:
            # fallback synthetic
            today = date.today()
            expiries = [today + timedelta(days=d) for d in (14, 21, 28)]
        expiry = pick_expiry(expiries, int(strat["min_dte"]), int(strat["max_dte"]))
        if expiry is None:
            logger.warning("No expiry in DTE window for %s", symbol)
            return None, []
        chain = self.broker.get_option_chain_snapshots(symbol, expiry)
        return expiry, chain
