"""EMA/VWAP pullback continuation — works on Globex overnight.

Classic discretionary playbook: trade with the trend after a pullback into
the fast EMA / VWAP zone, not chase extremes. Suited to delayed Yahoo bars.
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
class PullbackSignal:
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
    day = df.index.date
    out = []
    for _, g in df.groupby(day):
        vol = g["volume"].replace(0, np.nan).fillna(1.0)
        typ = (g["high"] + g["low"] + g["close"]) / 3.0
        out.append((typ * vol).cumsum() / vol.cumsum())
    return pd.concat(out).reindex(df.index)


def evaluate_ema_pullback(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[PullbackSignal]:
    strat = cfg.get("ema_pullback", {})
    if bars is None or len(bars) < 60:
        return None
    df = bars.copy()
    if "volume" not in df.columns:
        df["volume"] = 1.0

    fast_n = int(strat.get("fast_ema", 20))
    slow_n = int(strat.get("slow_ema", 50))
    df["ema_fast"] = _ema(df["close"], fast_n)
    df["ema_slow"] = _ema(df["close"], slow_n)
    df["atr"] = _atr(df)
    df["vwap"] = _session_vwap(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]
    atr = float(last["atr"])
    if not np.isfinite(atr) or atr <= 0:
        return None

    c = float(last["close"])
    o = float(last["open"])
    h = float(last["high"])
    l = float(last["low"])
    ema_f = float(last["ema_fast"])
    ema_s = float(last["ema_slow"])
    vwap = float(last["vwap"])
    prev_c = float(prev["close"])

    trend_up = ema_f > ema_s and c > ema_s
    trend_dn = ema_f < ema_s and c < ema_s
    touch_zone = float(strat.get("touch_atr", 0.35)) * atr
    lookback = int(strat.get("pullback_lookback", 5))
    recent = df.iloc[-(lookback + 1) : -1]

    # Pullback in last N bars into EMA/VWAP, then reclaim with trend on the latest bar
    touched_support = bool(
        (recent["low"] <= ema_f + touch_zone).any()
        or (recent["low"] <= vwap + touch_zone).any()
        or (l <= ema_f + touch_zone)
        or (l <= vwap + touch_zone)
    )
    touched_resist = bool(
        (recent["high"] >= ema_f - touch_zone).any()
        or (recent["high"] >= vwap - touch_zone).any()
        or (h >= ema_f - touch_zone)
        or (h >= vwap - touch_zone)
    )
    bullish_reclaim = c > o and c >= prev_c and c >= min(ema_f, vwap)
    bearish_reclaim = c < o and c <= prev_c and c <= max(ema_f, vwap)

    # Also allow continuation if stretched < 1.2 ATR from EMA (not chase far extensions)
    near_ema = abs(c - ema_f) <= atr * float(strat.get("max_extension_atr", 1.2))
    long_ok = (
        trend_up
        and near_ema
        and touched_support
        and bullish_reclaim
        and c >= vwap * 0.998
    )
    short_ok = (
        trend_dn
        and near_ema
        and touched_resist
        and bearish_reclaim
        and c <= vwap * 1.002
    )

    if long_ok == short_ok:
        return None

    side = "BUY" if long_ok else "SELL"
    entry = c
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 1.6))
    target_dollars = float(strat.get("target_dollars", 100))
    min_reward = float(strat.get("min_reward_dollars", 80))
    max_risk = float(strat.get("max_risk_dollars", 150))
    min_conf = int(strat.get("min_confidence", 62))

    if side == "BUY":
        stop = min(l, ema_f) - stop_atr * atr * 0.35
        risk_pts = max(entry - stop, atr * 0.4)
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry + target_pts
    else:
        stop = max(h, ema_f) + stop_atr * atr * 0.35
        risk_pts = max(stop - entry, atr * 0.4)
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry - target_pts

    risk_dollars = abs(entry - stop) * point_value
    reward_dollars = abs(target - entry) * point_value
    if risk_dollars > max_risk or reward_dollars < min_reward:
        return None
    if risk_dollars > 0 and reward_dollars / risk_dollars < 1.3:
        return None

    conf = 64
    conf += 8 if (side == "BUY" and c > vwap) or (side == "SELL" and c < vwap) else 0
    conf += 6 if abs(ema_f - ema_s) > atr * 0.15 else 0
    conf += 4 if reward_dollars >= risk_dollars * 1.6 else 0
    conf = min(94, conf)
    if conf < min_conf:
        return None

    return PullbackSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=f"{side} EMA_PULLBACK trend+reclaim",
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_dollars),
        reward_dollars=float(reward_dollars),
    )
