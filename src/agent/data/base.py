"""Market data provider interface — strategies never touch Yahoo directly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Bar:
    symbol: str
    timestamp: datetime  # market/bar time (exchange session clock)
    open: float
    high: float
    low: float
    close: float
    volume: float
    source: str
    is_realtime: bool
    estimated_delay_seconds: float
    is_stale: bool
    received_time: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    source: str
    last_success_utc: Optional[datetime]
    last_error: Optional[str]
    consecutive_failures: int
    is_healthy: bool


class MarketDataProvider(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> list[Bar]:
        """Return bars oldest→newest. Raises on total failure after retries."""

    @abstractmethod
    def get_latest_bar(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> Bar:
        ...

    @abstractmethod
    def health(self) -> ProviderHealth:
        ...

    def to_dataframe(self, bars: list[Bar]):
        """Convenience for existing strategy engines that expect a DataFrame."""
        import pandas as pd

        if not bars:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        idx = [b.timestamp for b in bars]
        df = pd.DataFrame(
            {
                "open": [b.open for b in bars],
                "high": [b.high for b in bars],
                "low": [b.low for b in bars],
                "close": [b.close for b in bars],
                "volume": [b.volume for b in bars],
            },
            index=pd.DatetimeIndex(idx),
        )
        return df
