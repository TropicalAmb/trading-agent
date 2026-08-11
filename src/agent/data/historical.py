"""Historical bar provider — same MarketDataProvider interface as Yahoo/broker RT."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from agent.data.base import Bar, MarketDataProvider, ProviderHealth


class HistoricalProvider(MarketDataProvider):
    """Serve preloaded DataFrames as standardized Bars (research / replay)."""

    def __init__(self, frames: dict[str, pd.DataFrame] | None = None, *, source: str = "historical"):
        self._frames = {str(k).upper(): v for k, v in (frames or {}).items()}
        self._source = source
        self._last_success: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._failures = 0

    def load_symbol(self, symbol: str, df: pd.DataFrame) -> None:
        self._frames[str(symbol).upper()] = df

    def get_bars(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> list[Bar]:
        df = self._frames.get(str(symbol).upper())
        if df is None or df.empty:
            self._failures += 1
            self._last_error = f"no historical frame for {symbol}"
            raise RuntimeError(f"DATA_ERROR: {self._last_error}")
        now = datetime.now(timezone.utc)
        bars: list[Bar] = []
        for ts, row in df.iterrows():
            t = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if getattr(t, "tzinfo", None) is None:
                t = t.replace(tzinfo=timezone.utc)
            bars.append(
                Bar(
                    symbol=str(symbol).upper(),
                    timestamp=t,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0) or 0),
                    source=self._source,
                    is_realtime=False,
                    estimated_delay_seconds=0.0,
                    is_stale=False,
                    received_time=now,
                    metadata={"interval": interval, "period": period},
                )
            )
        self._last_success = now
        self._failures = 0
        return bars

    def get_latest_bar(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> Bar:
        bars = self.get_bars(symbol, interval=interval, period=period)
        return bars[-1]

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            source=self._source,
            last_success_utc=self._last_success,
            last_error=self._last_error,
            consecutive_failures=self._failures,
            is_healthy=self._failures == 0 and bool(self._frames),
        )
