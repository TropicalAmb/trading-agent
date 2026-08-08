"""Yahoo delayed futures provider for paper validation."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from agent.data.base import Bar, MarketDataProvider, ProviderHealth
from agent.runtime.scan_status import parse_interval_seconds

ET = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)

YAHOO_MAP = {
    "MES": "MES=F",
    "MNQ": "MNQ=F",
    "ES": "ES=F",
    "NQ": "NQ=F",
    "MGC": "MGC=F",
    "MYM": "MYM=F",
    "M2K": "M2K=F",
    "MCL": "MCL=F",
    "CL": "CL=F",
    "GC": "GC=F",
    "YM": "YM=F",
    "RTY": "RTY=F",
}

# Paper validation: Yahoo futures often ~10–15 minutes delayed
DEFAULT_ESTIMATED_DELAY_SEC = 13 * 60
DEFAULT_EXPECTED_DELAY_SEC = 15 * 60
DEFAULT_STALE_TOLERANCE_SEC = 7 * 60
# Legacy absolute ceiling if formula not used via cfg override
STALE_AFTER_SEC = 45 * 60


class YahooDelayedFuturesProvider(MarketDataProvider):
    def __init__(
        self,
        *,
        estimated_delay_seconds: float = DEFAULT_ESTIMATED_DELAY_SEC,
        expected_delay_seconds: float = DEFAULT_EXPECTED_DELAY_SEC,
        stale_extra_tolerance_seconds: float = DEFAULT_STALE_TOLERANCE_SEC,
        stale_after_seconds: float | None = None,
        request_timeout_sec: float = 40.0,
        max_retries: int = 3,
        default_bar_interval: str = "5m",
    ):
        self.estimated_delay_seconds = float(estimated_delay_seconds)
        self.expected_delay_seconds = float(expected_delay_seconds)
        self.stale_extra_tolerance_seconds = float(stale_extra_tolerance_seconds)
        self.stale_after_seconds = (
            float(stale_after_seconds) if stale_after_seconds is not None else None
        )
        self.request_timeout_sec = float(request_timeout_sec)
        self.max_retries = int(max_retries)
        self.default_bar_interval = str(default_bar_interval)
        self._last_success: Optional[datetime] = None
        self._last_fetch_attempt: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._failures = 0

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            source="yahoo_delayed",
            last_success_utc=self._last_success,
            last_error=self._last_error,
            consecutive_failures=self._failures,
            is_healthy=self._failures < 5,
        )

    def provider_meta(self) -> dict[str, Any]:
        interval = self.default_bar_interval
        thr = self._stale_threshold(interval)
        return {
            "source": "yahoo_delayed",
            "bar_interval": interval,
            "bar_interval_seconds": parse_interval_seconds(interval),
            "bar_interval_label": interval,
            "expected_delay_seconds": self.expected_delay_seconds,
            "estimated_delay_seconds": self.estimated_delay_seconds,
            "stale_threshold_seconds": thr,
            "last_fetch_attempt": self._last_fetch_attempt.isoformat()
            if self._last_fetch_attempt
            else None,
            "last_successful_fetch": self._last_success.isoformat()
            if self._last_success
            else None,
        }

    def _stale_threshold(self, interval: str) -> float:
        if self.stale_after_seconds is not None:
            return float(self.stale_after_seconds)
        return (
            self.expected_delay_seconds
            + float(parse_interval_seconds(interval))
            + self.stale_extra_tolerance_seconds
        )

    def get_bars(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> list[Bar]:
        self._last_fetch_attempt = datetime.now(timezone.utc)
        df = self._download_df(symbol, interval=interval, period=period)
        received = datetime.now(timezone.utc)
        thr = self._stale_threshold(interval)
        interval_sec = parse_interval_seconds(interval)
        bars: list[Bar] = []
        for ts, row in df.iterrows():
            market_ts = pd.Timestamp(ts).to_pydatetime()
            if market_ts.tzinfo is None:
                market_aware = market_ts.replace(tzinfo=ET)
                market_naive_et = market_ts
            else:
                market_aware = market_ts.astimezone(ET)
                market_naive_et = market_aware.replace(tzinfo=None)
            market_utc = market_aware.astimezone(timezone.utc)
            delay = max(0.0, (received - market_utc).total_seconds())
            # Expected Yahoo delay alone must NOT mark stale
            is_stale = delay > thr
            bars.append(
                Bar(
                    symbol=symbol.upper(),
                    timestamp=market_naive_et,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0.0),
                    source="yahoo_delayed",
                    is_realtime=False,
                    estimated_delay_seconds=max(self.estimated_delay_seconds, delay),
                    is_stale=is_stale,
                    received_time=received,
                    metadata={
                        "yahoo_ticker": YAHOO_MAP.get(symbol.upper(), symbol),
                        "bar_interval": interval,
                        "bar_interval_seconds": interval_sec,
                        "bar_interval_label": interval,
                        "feed_delay_seconds": delay,
                        "stale_threshold_seconds": thr,
                    },
                )
            )
        logger.info(
            "provider bars %s interval=%s market_bar=%s received=%s feed_delay=%.0fs stale_thr=%.0fs",
            symbol,
            interval,
            bars[-1].timestamp.isoformat() if bars else None,
            received.isoformat(),
            bars[-1].estimated_delay_seconds if bars else -1,
            thr,
        )
        return bars

    def get_latest_bar(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> Bar:
        bars = self.get_bars(symbol, interval=interval, period=period)
        if not bars:
            raise RuntimeError(f"No bars for {symbol}")
        return bars[-1]

    def _download_df(self, symbol: str, *, interval: str, period: str) -> pd.DataFrame:
        import yfinance as yf

        ticker = YAHOO_MAP.get(symbol.upper(), symbol)
        last_err: Exception | None = None
        periods = [period, "5d", "10d"]
        for attempt in range(self.max_retries):
            per = periods[min(attempt, len(periods) - 1)]
            try:

                def _dl() -> pd.DataFrame:
                    df = yf.download(
                        ticker,
                        interval=interval,
                        period=per,
                        auto_adjust=True,
                        progress=False,
                    )
                    if df is None or df.empty:
                        raise RuntimeError(f"No bars for {ticker}")
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = [c[0] for c in df.columns]
                    df = df.rename(columns=str.lower)
                    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
                    df.index = pd.to_datetime(df.index)
                    if df.index.tz is not None:
                        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
                    return df[["open", "high", "low", "close", "volume"]]

                with ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(_dl)
                    df = fut.result(timeout=self.request_timeout_sec)
                self._last_success = datetime.now(timezone.utc)
                self._last_error = None
                self._failures = 0
                return df
            except FuturesTimeout:
                last_err = TimeoutError(f"Yahoo timeout for {ticker}")
                self._failures += 1
                self._last_error = str(last_err)
                logger.warning("Yahoo %s timeout attempt %s", ticker, attempt + 1)
            except Exception as exc:
                last_err = exc
                self._failures += 1
                self._last_error = str(exc)
                logger.warning("Yahoo %s fail attempt %s: %s", ticker, attempt + 1, exc)
                time.sleep(min(8.0, 1.2 * (2**attempt)))
        if isinstance(last_err, TimeoutError) or (
            last_err is not None and "timeout" in str(last_err).lower()
        ):
            raise TimeoutError(f"DATA_TIMEOUT: {ticker}: {last_err}")
        raise RuntimeError(f"DATA_ERROR: No bars for {ticker}: {last_err}")


def make_provider(cfg: dict[str, Any]) -> MarketDataProvider:
    md = cfg.get("market_data", {})
    name = str(md.get("provider", "yahoo_delayed")).lower()
    if name in {"yahoo", "yahoo_delayed", "yfinance"}:
        stale_override = md.get("stale_after_seconds")
        return YahooDelayedFuturesProvider(
            estimated_delay_seconds=float(
                md.get("estimated_delay_seconds", DEFAULT_ESTIMATED_DELAY_SEC)
            ),
            expected_delay_seconds=float(
                md.get("expected_delay_seconds", md.get("estimated_delay_seconds", DEFAULT_EXPECTED_DELAY_SEC))
            ),
            stale_extra_tolerance_seconds=float(
                md.get("stale_extra_tolerance_seconds", DEFAULT_STALE_TOLERANCE_SEC)
            ),
            stale_after_seconds=float(stale_override) if stale_override is not None else None,
            request_timeout_sec=float(md.get("request_timeout_sec", 40)),
            max_retries=int(md.get("max_retries", 3)),
            default_bar_interval=str(md.get("bar_interval", "5m")),
        )
    raise ValueError(f"Unknown market_data.provider: {name}")
