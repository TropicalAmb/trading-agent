"""Zero-spend hybrid paper feed: paid Databento cache plus current Yahoo tail.

This provider never calls the Databento API. It uses the locally purchased
GLBX.MDP3 cache where it overlaps cleanly with Yahoo, then keeps Yahoo's latest
delayed bars so autonomous paper trading can continue after the cache endpoint.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from agent.data.base import Bar, MarketDataProvider, ProviderHealth

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")
CACHE_FORMAT_VERSION = "databento_continuous_v1"


class DatabentoCacheYahooProvider(MarketDataProvider):
    """Merge verified local Databento history with Yahoo's current delayed tail."""

    def __init__(
        self,
        yahoo_provider: MarketDataProvider,
        *,
        cache_dir: str | Path = "data/databento",
        cache_roots: list[str] | tuple[str, ...] = ("NQ", "ES", "CL", "GC"),
        cache_ttl_seconds: float = 30.0,
        max_relative_basis_gap: float = 0.02,
    ):
        self.yahoo = yahoo_provider
        self.cache_dir = Path(cache_dir)
        self.cache_roots = {str(s).upper() for s in cache_roots}
        self.cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self.max_relative_basis_gap = max(0.0, float(max_relative_basis_gap))
        self._frames: dict[tuple[str, str], pd.DataFrame] = {}
        self._cache_rejections: dict[str, str] = {}
        self._combined_cache: dict[
            tuple[str, str, str], tuple[float, list[Bar]]
        ] = {}

    @property
    def _last_fetch_attempt(self):
        """Compatibility for existing heartbeat/feed metadata."""
        return getattr(self.yahoo, "_last_fetch_attempt", None)

    @property
    def _last_success(self):
        """Compatibility for existing heartbeat/feed metadata."""
        return getattr(self.yahoo, "_last_success", None)

    @staticmethod
    def _period_days(period: str) -> int:
        raw = str(period).strip().lower()
        try:
            if raw.endswith("d"):
                return max(1, int(raw[:-1]))
            if raw.endswith("mo"):
                return max(1, int(raw[:-2]) * 30)
        except ValueError:
            pass
        return 10

    def _load_cache_frame(self, root: str, interval: str) -> pd.DataFrame:
        key = (root, str(interval).lower())
        if key in self._frames:
            return self._frames[key]
        path = self.cache_dir / f"{root}_1m_cache.parquet"
        if not path.exists():
            self._frames[key] = pd.DataFrame()
            return self._frames[key]

        meta = self._cache_meta(root)
        expected_symbol = f"{root}.v.0"
        if (
            meta.get("cache_format_version") != CACHE_FORMAT_VERSION
            or str(meta.get("stype_in") or "").lower() != "continuous"
            or str(meta.get("databento") or meta.get("symbol") or "").lower()
            != expected_symbol.lower()
        ):
            reason = (
                "legacy parent-symbol cache is not a valid continuous contract; "
                f"expected {expected_symbol} stype=continuous format={CACHE_FORMAT_VERSION}"
            )
            self._cache_rejections[root] = reason
            logger.error("Databento cache rejected for %s: %s", root, reason)
            self._frames[key] = pd.DataFrame()
            return self._frames[key]

        try:
            frame = pd.read_parquet(path)
        except Exception as exc:
            # A damaged/locked research cache must never take down current
            # paper data; Yahoo remains the safe exact-symbol fallback.
            logger.warning(
                "Databento cache unreadable %s; Yahoo-only fallback: %s", path, exc
            )
            self._frames[key] = pd.DataFrame()
            return self._frames[key]
        frame.columns = [str(c).lower() for c in frame.columns]
        required = ["open", "high", "low", "close"]
        if not set(required).issubset(frame.columns):
            logger.warning("Databento cache missing OHLC columns: %s", path)
            self._frames[key] = pd.DataFrame()
            return self._frames[key]
        if "volume" not in frame.columns:
            frame["volume"] = 0.0
        frame = frame[required + ["volume"]].sort_index()
        frame.index = pd.to_datetime(frame.index)
        if frame.index.tz is None:
            frame.index = pd.to_datetime(frame.index).tz_localize(ET)
        else:
            frame.index = pd.to_datetime(frame.index).tz_convert(ET)

        # A continuous 1m series may have isolated roll gaps, but a material
        # fraction of >1% minute jumps indicates rows from different contracts
        # were interleaved.  Never allow that corruption into paper signals.
        jumps = frame["close"].astype(float).pct_change().abs().dropna()
        large_jump_fraction = float((jumps > 0.01).mean()) if len(jumps) else 0.0
        if large_jump_fraction > 0.002:
            reason = (
                f"continuity audit failed: {large_jump_fraction:.3%} of 1m returns "
                "exceed 1%"
            )
            self._cache_rejections[root] = reason
            logger.error("Databento cache rejected for %s: %s", root, reason)
            self._frames[key] = pd.DataFrame()
            return self._frames[key]

        iv = str(interval).lower()
        rules = {
            "5m": ("5min", 5),
            "5min": ("5min", 5),
            "1h": ("1h", 60),
            "60m": ("1h", 60),
        }
        if iv in rules:
            rule, expected = rules[iv]
            counts = frame["close"].resample(
                rule, label="left", closed="left"
            ).count()
            frame = frame.resample(rule, label="left", closed="left").agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            # Never splice an unfinished cache bucket into a close-based strategy.
            frame = frame.loc[counts >= max(1, expected - 1)]
        elif iv not in {"1m", "1min"}:
            logger.info(
                "Databento cache interval %s unsupported; using Yahoo only", interval
            )
            self._frames[key] = pd.DataFrame()
            return self._frames[key]

        frame = frame.dropna(subset=required)
        frame.index = frame.index.tz_convert(ET).tz_localize(None)
        self._frames[key] = frame
        return frame

    def _cache_meta(self, root: str) -> dict[str, Any]:
        path = self.cache_dir / f"{root}_1m_cache_meta.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get_bars(
        self, symbol: str, *, interval: str = "5m", period: str = "10d"
    ) -> list[Bar]:
        symbol_u = str(symbol).upper()
        key = (symbol_u, str(interval), str(period))
        cached = self._combined_cache.get(key)
        if cached and (time.monotonic() - cached[0]) <= self.cache_ttl_seconds:
            return list(cached[1])

        yahoo_bars = self.yahoo.get_bars(symbol_u, interval=interval, period=period)
        # Paid caches are exact full-size roots. Do not substitute ES/NQ/CL/GC
        # prices for their micro contracts or for uncached Dow/Russell products.
        if symbol_u not in self.cache_roots or not yahoo_bars:
            return yahoo_bars

        db = self._load_cache_frame(symbol_u, interval)
        if db.empty:
            fallback = list(yahoo_bars)
            rejection = self._cache_rejections.get(symbol_u)
            if fallback and rejection:
                fallback[-1] = replace(
                    fallback[-1],
                    metadata={
                        **(fallback[-1].metadata or {}),
                        "databento_cache_status": "rejected",
                        "databento_cache_reject_reason": rejection,
                        "databento_api_called": False,
                    },
                )
            self._combined_cache[key] = (time.monotonic(), fallback)
            return fallback

        yahoo_by_ts = {
            (b.timestamp.replace(tzinfo=None) if b.timestamp.tzinfo else b.timestamp): b
            for b in yahoo_bars
        }
        yahoo_frame = pd.DataFrame(
            {"close": [b.close for b in yahoo_by_ts.values()]},
            index=pd.DatetimeIndex(list(yahoo_by_ts)),
        )
        overlap = db.index.intersection(yahoo_frame.index)
        if overlap.empty:
            logger.warning(
                "Databento cache has no Yahoo overlap for %s; refusing unverified splice",
                symbol_u,
            )
            self._combined_cache[key] = (time.monotonic(), list(yahoo_bars))
            return yahoo_bars
        overlap = overlap[-100:]
        db_close = db.loc[overlap, "close"].astype(float)
        yh_close = yahoo_frame.loc[overlap, "close"].astype(float)
        basis_gap = float(
            ((db_close - yh_close).abs() / yh_close.abs().clip(lower=1e-9)).median()
        )
        if basis_gap > self.max_relative_basis_gap:
            logger.warning(
                "Databento/Yahoo basis gap %.3f%% exceeds %.3f%% for %s; "
                "Yahoo-only fallback",
                basis_gap * 100,
                self.max_relative_basis_gap * 100,
                symbol_u,
            )
            self._combined_cache[key] = (time.monotonic(), list(yahoo_bars))
            return yahoo_bars

        days = self._period_days(period)
        start = datetime.now(ET).replace(tzinfo=None) - timedelta(days=days)
        latest_yahoo_ts = max(yahoo_by_ts)
        db_slice = db.loc[(db.index >= start) & (db.index <= latest_yahoo_ts)]
        received = yahoo_bars[-1].received_time
        db_bars: dict[datetime, Bar] = {}
        meta = self._cache_meta(symbol_u)
        for ts, row in db_slice.iterrows():
            market_ts = pd.Timestamp(ts).to_pydatetime().replace(tzinfo=None)
            db_bars[market_ts] = Bar(
                symbol=symbol_u,
                timestamp=market_ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume") or 0.0),
                source="databento_cache",
                is_realtime=False,
                estimated_delay_seconds=0.0,
                is_stale=False,
                received_time=received,
                metadata={
                    "dataset": "GLBX.MDP3",
                    "cache_root": symbol_u,
                    "cache_end": meta.get("end"),
                    "paid_cache": True,
                },
            )

        merged = dict(yahoo_by_ts)
        # Databento is research truth on verified overlapping timestamps.
        merged.update(db_bars)
        result = [merged[ts] for ts in sorted(merged)]
        latest = result[-1]
        result[-1] = replace(
            latest,
            source="databento_cache+yahoo_delayed",
            is_stale=yahoo_bars[-1].is_stale,
            estimated_delay_seconds=yahoo_bars[-1].estimated_delay_seconds,
            metadata={
                **(latest.metadata or {}),
                "bar_interval": interval,
                "bar_interval_seconds": (yahoo_bars[-1].metadata or {}).get(
                    "bar_interval_seconds"
                ),
                "paid_databento_bars": len(db_bars),
                "yahoo_tail_bars": sum(ts > db.index.max() for ts in yahoo_by_ts),
                "databento_yahoo_basis_gap": basis_gap,
                "cache_end": meta.get("end"),
                "databento_api_called": False,
            },
        )
        logger.info(
            "hybrid bars %s paid_databento=%s yahoo_tail=%s cache_end=%s "
            "basis_gap=%.4f%%",
            symbol_u,
            len(db_bars),
            result[-1].metadata.get("yahoo_tail_bars"),
            meta.get("end"),
            basis_gap * 100,
        )
        self._combined_cache[key] = (time.monotonic(), list(result))
        return result

    def get_latest_bar(
        self, symbol: str, *, interval: str = "5m", period: str = "10d"
    ) -> Bar:
        bars = self.get_bars(symbol, interval=interval, period=period)
        if not bars:
            raise RuntimeError(f"No bars for {symbol}")
        return bars[-1]

    def health(self) -> ProviderHealth:
        health = self.yahoo.health()
        return ProviderHealth(
            source="databento_cache+yahoo_delayed",
            last_success_utc=health.last_success_utc,
            last_error=health.last_error,
            consecutive_failures=health.consecutive_failures,
            is_healthy=health.is_healthy,
        )
