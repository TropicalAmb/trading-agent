"""Databento historical CME futures provider (research / walk-forward).

Requires DATABENTO_API_KEY in the environment (.env).
New Databento accounts typically receive ~$125 free historical credits.

Dataset: GLBX.MDP3 (CME Globex). Use volume-ranked continuous symbology for
single-series research: stype_in=continuous, symbols like NQ.v.0 / CL.v.0.
Parent symbols such as CL.FUT return every outright and spread and must never be
flattened by timestamp into a continuous price series.

The paper path uses already-purchased local Databento caches plus a current Yahoo
tail. This API-backed provider remains for explicit offline research/downloads.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd

from agent.data.base import Bar, MarketDataProvider, ProviderHealth

logger = logging.getLogger(__name__)

# Map agent book symbols → Databento parent futures roots
DATABENTO_PARENT = {
    "NQ": "NQ.FUT",
    "MNQ": "MNQ.FUT",
    "ES": "ES.FUT",
    "MES": "MES.FUT",
    "CL": "CL.FUT",
    "MCL": "MCL.FUT",
    "GC": "GC.FUT",
    "MGC": "MGC.FUT",
    "YM": "YM.FUT",
    "MYM": "MYM.FUT",
    "RTY": "RTY.FUT",
    "M2K": "M2K.FUT",
}

DATABENTO_CONTINUOUS = {
    symbol: f"{symbol}.v.0" for symbol in DATABENTO_PARENT
}


class DatabentoHistoricalProvider(MarketDataProvider):
    """Pull OHLCV bars from Databento historical API into standardized Bars."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        dataset: str = "GLBX.MDP3",
        schema: str = "ohlcv-1m",
        default_lookback_days: int = 60,
    ):
        self.api_key = (api_key or os.getenv("DATABENTO_API_KEY") or "").strip()
        self.dataset = dataset
        self.schema = schema
        self.default_lookback_days = int(default_lookback_days)
        self._last_success: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._failures = 0
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError(
                "DATABENTO_API_KEY missing. Sign up at databento.com, copy the db-… key "
                "into .env as DATABENTO_API_KEY=db-..., then retry."
            )
        try:
            import databento as db
        except ImportError as exc:
            raise RuntimeError(
                "databento package not installed. Run: pip install databento"
            ) from exc
        self._client = db.Historical(self.api_key)
        return self._client

    def _resolve_symbol(self, symbol: str, stype_in: str = "continuous") -> str:
        raw = str(symbol).upper().replace("=F", "")
        if str(stype_in).lower() == "continuous":
            if ".V." in raw or ".N." in raw or ".C." in raw:
                root, rule, rank = raw.split(".", 2)
                return f"{root}.{rule.lower()}.{rank}"
            root = raw.replace(".FUT", "")
            return DATABENTO_CONTINUOUS.get(root, f"{root}.v.0")
        if str(stype_in).lower() == "parent":
            root = raw.replace(".FUT", "")
            return DATABENTO_PARENT.get(root, f"{root}.FUT")
        return raw

    def _schema_for_interval(self, interval: str) -> str:
        iv = str(interval).lower().strip()
        if iv in {"1m", "1min", "1T"}:
            return "ohlcv-1m"
        if iv in {"1h", "60m", "1H"}:
            return "ohlcv-1h"
        if iv in {"1d", "1D", "day"}:
            return "ohlcv-1d"
        # 5m: request 1m and resample
        return "ohlcv-1m"

    SUPPORTED_SCHEMAS = ("ohlcv-1m", "ohlcv-1s", "trades", "mbp-1")

    def fetch_ohlcv_df(
        self,
        symbol: str,
        *,
        start: datetime | str,
        end: datetime | str,
        schema: str = "ohlcv-1m",
        stype_in: str = "continuous",
    ) -> pd.DataFrame:
        """Historical OHLCV (or raw schema) DataFrame for research / finalist validation.

        schema defaults to ohlcv-1m. Optional later: trades, mbp-1, ohlcv-1s.
        """
        if schema not in self.SUPPORTED_SCHEMAS and not str(schema).startswith("ohlcv"):
            raise ValueError(f"Unsupported Databento schema: {schema}")
        client = self._ensure_client()
        requested_symbol = self._resolve_symbol(symbol, stype_in)
        try:
            store = client.timeseries.get_range(
                dataset=self.dataset,
                symbols=requested_symbol,
                schema=schema,
                stype_in=stype_in,
                start=start if isinstance(start, str) else start.isoformat(),
                end=end if isinstance(end, str) else end.isoformat(),
            )
            df = store.to_df()
        except Exception as exc:
            self._failures += 1
            self._last_error = str(exc)
            logger.exception("Databento fetch failed for %s", requested_symbol)
            raise RuntimeError(f"DATA_ERROR: Databento {requested_symbol}: {exc}") from exc
        if df is None or df.empty:
            self._failures += 1
            self._last_error = f"empty response for {requested_symbol}"
            raise RuntimeError(f"DATA_ERROR: No Databento bars for {requested_symbol}")
        work = df.copy()
        work.columns = [str(c).lower() for c in work.columns]
        if schema.startswith("ohlcv"):
            for need in ("open", "high", "low", "close"):
                if need not in work.columns:
                    raise RuntimeError(f"DATA_ERROR: Databento missing column {need}")
            if "volume" not in work.columns:
                work["volume"] = 0.0
        # Normalize index to UTC then America/New_York for research alignment
        if getattr(work.index, "tz", None) is None:
            work.index = pd.to_datetime(work.index, utc=True)
        else:
            work.index = work.index.tz_convert("UTC")
        work.index = work.index.tz_convert("America/New_York")
        # Parent symbology can emit overlapping contract/spread rows → duplicate timestamps
        root = str(symbol).upper().replace("=F", "").replace(".FUT", "")
        if "symbol" in work.columns:
            # Prefer outright month codes for the requested root (exclude calendar spreads)
            sym = work["symbol"].astype(str)
            outright = sym.str.match(rf"^{root}[HJKMNQUZ][0-9]$", case=False)
            if outright.any():
                work = work.loc[outright]
        if work.index.duplicated().any():
            work = work[~work.index.duplicated(keep="last")]
        # Hard price sanity by product (rejects junk / spread prints)
        close_floor = {
            "NQ": 5000.0,
            "MNQ": 5000.0,
            "ES": 1000.0,
            "MES": 1000.0,
            "GC": 500.0,
            "MGC": 500.0,
            "CL": 10.0,
            "MCL": 10.0,
            "YM": 10000.0,
            "MYM": 10000.0,
            "RTY": 500.0,
            "M2K": 500.0,
        }.get(root, 0.0)
        if close_floor > 0 and {"open", "high", "low", "close"}.issubset(work.columns):
            px = work["close"].astype(float)
            work = work.loc[px >= close_floor]
        work.attrs["source"] = "databento"
        work.attrs["dataset"] = self.dataset
        work.attrs["requested_symbol"] = requested_symbol
        work.attrs["stype_in"] = stype_in
        work.attrs["schema"] = schema
        self._last_success = datetime.now(timezone.utc)
        self._failures = 0
        self._last_error = None
        return work.sort_index()

    def get_bars(
        self,
        symbol: str,
        *,
        interval: str = "5m",
        period: str = "60d",
    ) -> list[Bar]:
        schema = self._schema_for_interval(interval)
        days = self.default_lookback_days
        try:
            if str(period).endswith("d"):
                days = int(str(period)[:-1])
            elif str(period).endswith("mo"):
                days = int(str(period)[:-2]) * 30
        except Exception:
            days = self.default_lookback_days
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=max(days, 7))
        work = self.fetch_ohlcv_df(symbol, start=start, end=end, schema=schema)

        # Resample 1m → 5m when requested
        iv = str(interval).lower()
        if iv in {"5m", "5min"} and schema == "ohlcv-1m":
            work = (
                work.resample("5min", label="left", closed="left")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna(subset=["open", "high", "low", "close"])
            )

        now = datetime.now(timezone.utc)
        requested_symbol = self._resolve_symbol(symbol, "continuous")
        bars: list[Bar] = []
        for ts, row in work.iterrows():
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
                    volume=float(row.get("volume") or 0),
                    source="databento",
                    is_realtime=False,
                    estimated_delay_seconds=0.0,
                    is_stale=False,
                    received_time=now,
                    metadata={
                        "dataset": self.dataset,
                        "requested_symbol": requested_symbol,
                        "stype_in": "continuous",
                        "schema": schema,
                    },
                )
            )
        return bars

    def get_latest_bar(self, symbol: str, *, interval: str = "5m", period: str = "10d") -> Bar:
        bars = self.get_bars(symbol, interval=interval, period=period)
        return bars[-1]

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            source="databento_historical",
            last_success_utc=self._last_success,
            last_error=self._last_error
            or (None if self.api_key else "DATABENTO_API_KEY missing"),
            consecutive_failures=self._failures,
            is_healthy=bool(self.api_key) and self._failures == 0,
        )


def cost_estimate_note() -> str:
    return (
        "Databento: usage-based historical (~$0.50+/GB) or CME Standard ~$199/mo. "
        "New accounts usually get ~$125 free credits — enough to validate NQ/ES 1m history."
    )
