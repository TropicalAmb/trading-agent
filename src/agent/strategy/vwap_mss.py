"""VWAP + Market Structure Shift (simple live engine).

Deterministic OHLCV rules aligned with research candidate:
MSS close-through structure (mode C) + VWAP reclaim/retest + 15m/1h/4h alignment.
Paper research version: vwap_mss_v1 — not the 354-variant grid.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class VwapMssSignal:
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
    level: float
    pdh: float = 0.0
    pdl: float = 0.0


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


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


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    day = df.index.normalize()
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
    typ = (df["high"] + df["low"] + df["close"]) / 3.0
    return (typ * vol).groupby(day).cumsum() / vol.groupby(day).cumsum()


def _mtf_dir(close: pd.Series) -> int:
    if len(close) < 2:
        return 0
    a, b = float(close.iloc[-2]), float(close.iloc[-1])
    if b > a:
        return 1
    if b < a:
        return -1
    return 0


def _last_confirmed_swing(
    highs: np.ndarray, lows: np.ndarray, i: int, *, side: str, left: int = 3, right: int = 3
) -> Optional[float]:
    """Most recent swing fully confirmed (no lookahead past i)."""
    # swing pivot at j confirmed when j+right < i
    for j in range(i - right - 1, left - 1, -1):
        if j - left < 0 or j + right >= i:
            continue
        if side == "BUY":
            window = highs[j - left : j + right + 1]
            if highs[j] >= window.max() and (window == highs[j]).sum() == 1:
                return float(highs[j])
        else:
            window = lows[j - left : j + right + 1]
            if lows[j] <= window.min() and (window == lows[j]).sum() == 1:
                return float(lows[j])
    return None


def evaluate_vwap_mss(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[VwapMssSignal]:
    strat = cfg.get("vwap_mss") or {}
    if bars is None or len(bars) < 80:
        return None

    df = bars.copy()
    df.columns = [c.lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = 1.0
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        from zoneinfo import ZoneInfo

        idx = idx.tz_convert(ZoneInfo("America/New_York")).tz_localize(None)
    df.index = idx

    atr_s = _atr(df)
    vwap = _session_vwap(df)
    i = len(df) - 1
    av = float(atr_s.iloc[i] or 0)
    if av <= 0 or not np.isfinite(float(vwap.iloc[i])):
        return None

    c = float(df["close"].iloc[i])
    o = float(df["open"].iloc[i])
    h = float(df["high"].iloc[i])
    l = float(df["low"].iloc[i])
    pc = float(df["close"].iloc[i - 1])
    vv = float(vwap.iloc[i])

    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)

    # MTF alignment (completed buckets as-of last bar)
    c15 = df["close"].resample("15min").last().dropna()
    c1h = df["close"].resample("1h").last().dropna()
    c4h = df["close"].resample("4h").last().dropna()
    d15, d1h, d4h = _mtf_dir(c15), _mtf_dir(c1h), _mtf_dir(c4h)
    require_mtf = int(strat.get("min_mtf_align", 3))

    # VWAP modes: reclaim or retest-after-reclaim
    reclaim_buy = pc < vv and c > vv and c > o
    reclaim_sell = pc > vv and c < vv and c < o
    retest_buy = False
    retest_sell = False
    for k in range(max(1, i - 6), i):
        pk, ck, vk = float(df["close"].iloc[k - 1]), float(df["close"].iloc[k]), float(vwap.iloc[k])
        if pk < vk and ck > vk and l <= vv * 1.001 and c > vv and c > o:
            retest_buy = True
        if pk > vk and ck < vk and h >= vv * 0.999 and c < vv and c < o:
            retest_sell = True

    side = None
    vwap_mode = ""
    if reclaim_buy or retest_buy:
        side, vwap_mode = "BUY", ("retest" if retest_buy and not reclaim_buy else "reclaim")
    elif reclaim_sell or retest_sell:
        side, vwap_mode = "SELL", ("retest" if retest_sell and not reclaim_sell else "reclaim")
    else:
        return None

    want = 1 if side == "BUY" else -1
    mtf_score = sum(1 for d in (d15, d1h, d4h) if d == want)
    if mtf_score < require_mtf:
        return None

    struct = _last_confirmed_swing(highs, lows, i, side=side)
    if struct is None:
        return None
    # MSS mode C: close through structure
    if side == "BUY" and not (c > struct):
        return None
    if side == "SELL" and not (c < struct):
        return None

    # Optional soft: note PDH/PDL sweep nearby (confidence bonus only)
    daily = df.resample("1D").agg({"high": "max", "low": "min"}).dropna()
    pdh = float(daily["high"].iloc[-2]) if len(daily) >= 2 else h
    pdl = float(daily["low"].iloc[-2]) if len(daily) >= 2 else l
    look = df.iloc[max(0, i - 16) : i]
    swept = False
    if side == "BUY" and len(look):
        swept = float(look["low"].min()) < pdl
    elif side == "SELL" and len(look):
        swept = float(look["high"].max()) > pdh

    # Stop beyond structural invalidation; target ~1.25R (research higher-WR side)
    target_r = float(strat.get("target_r", 1.25))
    if side == "BUY":
        stop = min(float(df["low"].iloc[max(0, i - 3) : i + 1].min()), struct) - 0.15 * av
        if stop >= c:
            stop = c - av
        entry = c
        risk = abs(entry - stop)
        target = entry + risk * target_r
    else:
        stop = max(float(df["high"].iloc[max(0, i - 3) : i + 1].max()), struct) + 0.15 * av
        if stop <= c:
            stop = c + av
        entry = c
        risk = abs(entry - stop)
        target = entry - risk * target_r

    if risk <= 1e-9:
        return None

    # No-chase: reject if far from VWAP
    max_overext = float(strat.get("max_overext_atr", 1.25))
    if abs(entry - vv) / av > max_overext:
        return None

    risk_d = risk * point_value
    reward_d = abs(target - entry) * point_value
    min_rr = float(strat.get("min_rr", 1.2))
    if reward_d / max(risk_d, 1e-9) < min_rr:
        return None
    max_risk = float(strat.get("max_risk_dollars", 500))
    min_reward = float(strat.get("min_reward_dollars", 50))
    if risk_d > max_risk or reward_d < min_reward:
        return None

    conf = int(strat.get("base_confidence", 74))
    conf += 4 * (mtf_score - 2)
    if swept:
        conf += 6
    if vwap_mode == "retest":
        conf += 3
    conf = min(96, max(55, conf))
    min_conf = int(strat.get("min_confidence", 70))
    if conf < min_conf:
        return None

    reason = (
        f"VWAP_MSS {vwap_mode} mss_close mtf={mtf_score}/3 "
        f"struct={struct:.2f} target_r={target_r}"
        + (" pdh_pdl_sweep" if swept else "")
    )
    ts = df.index[i]
    if isinstance(ts, pd.Timestamp):
        ts_dt = ts.to_pydatetime().replace(tzinfo=timezone.utc)
    else:
        ts_dt = datetime.now(timezone.utc)

    return VwapMssSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=conf,
        reason=reason,
        ts=ts_dt,
        risk_dollars=float(risk_d),
        reward_dollars=float(reward_d),
        level=float(struct),
        pdh=pdh,
        pdl=pdl,
    )
