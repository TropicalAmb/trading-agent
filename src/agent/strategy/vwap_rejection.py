"""VWAP rejection specialist — wick through VWAP then close reject.

Matches harness gen_vwap_rejection on 1h bars (researched timeframe).
Paper path usually supplies 5m → resampled to 1h inside the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

STRATEGY_NAME = "vwap_rejection"
DEFAULT_VERSION = "vwap_rejection_v1"


@dataclass
class VwapRejectionSignal:
    symbol: str
    side: str
    entry: float
    stop: float
    target: float
    confidence: int
    reason: str
    ts: datetime
    risk_dollars: float
    reward_dollars: float
    level: float | None = None
    vwap: float = 0.0
    market_bar_timestamp: datetime | None = None


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = (
        df["volume"].replace(0, np.nan).fillna(1.0)
        if "volume" in df.columns
        else pd.Series(1.0, index=df.index)
    )
    days = df.index.date
    return (typical * vol).groupby(days).cumsum() / vol.groupby(days).cumsum()


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


def _to_1h(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    # Already hourly-ish
    if len(df) >= 2:
        deltas = df.index.to_series().diff().dropna()
        if len(deltas) and deltas.median() >= pd.Timedelta(minutes=50):
            return df.copy()
    work = df.copy()
    if "volume" not in work.columns:
        work["volume"] = 1.0
    deltas = work.index.to_series().diff().dropna()
    median_delta = deltas.median() if len(deltas) else pd.Timedelta(minutes=5)
    hourly = work.resample("1h", label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    counts = work["close"].resample("1h", label="left", closed="left").count()
    if median_delta < pd.Timedelta(minutes=50):
        expected = max(1, int(round(pd.Timedelta(hours=1) / median_delta)))
        # A 1h close-rejection rule must not fire from the still-forming hour.
        # Allow one missing 5m print, but require an otherwise completed bucket.
        hourly = hourly.loc[counts >= max(1, expected - 1)]
    return hourly.dropna(subset=["open", "high", "low", "close"])


def evaluate_vwap_rejection(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[VwapRejectionSignal]:
    strat = cfg.get(STRATEGY_NAME) or {}
    if not bool(strat.get("enabled", True)):
        return None
    if bars is None or len(bars) < 40:
        return None

    target_r = float(strat.get("target_r_multiple", 1.5))
    stop_atr = float(strat.get("stop_atr_mult", 0.2))
    min_hour = int(strat.get("session_start_hour", 9))
    max_hour = int(strat.get("session_end_hour", 16))
    version = str(strat.get("strategy_version", DEFAULT_VERSION))
    allowed = {s.upper() for s in (strat.get("symbols") or ["NQ", "ES", "CL", "GC", "MNQ", "MES", "MCL", "MGC"])}
    sym = symbol.upper()
    if sym not in allowed:
        return None

    df = _to_1h(bars)
    if len(df) < 50:
        return None

    vwap = _session_vwap(df)
    atr = _atr(df)
    i = len(df) - 1
    ts = df.index[i]
    hour = int(ts.hour)
    if hour < min_hour or hour >= max_hour:
        return None

    c, o = float(df["close"].iloc[i]), float(df["open"].iloc[i])
    h, l = float(df["high"].iloc[i]), float(df["low"].iloc[i])
    vv, av = float(vwap.iloc[i] or 0), float(atr.iloc[i] or 0)
    if av <= 1e-12 or vv <= 0:
        return None

    # Exact harness rule: wick through VWAP, close back, opposing body
    side = None
    if l < vv <= c and c < o:
        side, stop = "SELL", h + stop_atr * av
    elif h > vv >= c and c > o:
        side, stop = "BUY", l - stop_atr * av
    else:
        return None

    entry = c
    risk = abs(entry - stop)
    if risk <= 1e-12:
        return None
    if side == "BUY":
        target = entry + risk * target_r
    else:
        target = entry - risk * target_r

    ts_dt = ts.to_pydatetime()
    if ts_dt.tzinfo is not None:
        ts_market = ts_dt.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
    else:
        # Yahoo provider indexes are deliberately naive New York market time.
        ts_market = ts_dt

    risk_d = risk * point_value
    reward_d = abs(target - entry) * point_value
    return VwapRejectionSignal(
        symbol=sym,
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        confidence=76,
        reason=(
            f"{version}:wick_reject VWAP 1h target={target_r}R "
            f"stopATR={stop_atr} (frozen-rule forward validation)"
        ),
        ts=ts_market.replace(tzinfo=ZoneInfo("America/New_York")),
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        level=vv,
        vwap=vv,
        market_bar_timestamp=ts_market,
    )
