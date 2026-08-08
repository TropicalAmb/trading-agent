"""Shallow trend continuation — does NOT require exact EMA20 touch."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


@dataclass
class TrendContinuationSignal:
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


def evaluate_trend_continuation(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[TrendContinuationSignal]:
    strat = cfg.get("trend_continuation") or {}
    if not bool(strat.get("enabled", True)):
        return None
    if df is None or len(df) < 50:
        return None

    max_retrace = float(strat.get("max_retrace_atr", 1.1))
    min_impulse = float(strat.get("min_impulse_atr", 1.2))
    max_ext = float(strat.get("max_extension_atr", 1.6))
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 1.6))
    max_risk = float(strat.get("max_risk_dollars", 150))
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 64))

    atr = _atr(df)
    ema20 = _ema(df["close"], 20)
    ema50 = _ema(df["close"], 50)
    a = float(atr.iloc[-1] or 0.0)
    if a <= 1e-12:
        return None

    close = df["close"].astype(float)
    e20, e50 = float(ema20.iloc[-1]), float(ema50.iloc[-1])
    c = float(close.iloc[-1])
    o = float(df["open"].iloc[-1])
    h = float(df["high"].iloc[-1])
    l = float(df["low"].iloc[-1])

    bull = e20 > e50 and c > e50
    bear = e20 < e50 and c < e50
    if not bull and not bear:
        return None

    # Impulse over last 8 bars then shallow retrace
    swing = df.iloc[-10:-1]
    if bull:
        impulse = float(swing["high"].max()) - float(swing["low"].iloc[0])
        retrace = float(swing["high"].max()) - c
        if impulse < min_impulse * a or retrace > max_retrace * a:
            return None
        if (c - e20) > max_ext * a:
            return None  # already extended — skip
        if not (c > o):  # resume candle
            return None
        side = "BUY"
        stop = min(l, float(swing["low"].min())) - 0.2 * a
        entry = c
        risk_pts = max(entry - stop, a * 0.4)
        target = entry + max(risk_pts * target_r, min_reward / point_value)
    else:
        impulse = float(swing["high"].iloc[0]) - float(swing["low"].min())
        retrace = c - float(swing["low"].min())
        if impulse < min_impulse * a or retrace > max_retrace * a:
            return None
        if (e20 - c) > max_ext * a:
            return None
        if not (c < o):
            return None
        side = "SELL"
        stop = max(h, float(swing["high"].max())) + 0.2 * a
        entry = c
        risk_pts = max(stop - entry, a * 0.4)
        target = entry - max(risk_pts * target_r, min_reward / point_value)

    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if risk_d > max_risk or reward_d < min_reward:
        return None
    if risk_d > 0 and reward_d / risk_d < 1.3:
        return None

    conf = 66
    conf += 8 if abs(c - e20) <= 0.8 * a else 0
    conf += 6 if reward_d >= risk_d * 1.6 else 0
    conf = min(90, conf)
    if conf < min_conf:
        return None

    return TrendContinuationSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=f"{side} TREND_CONTINUATION shallow_retrace",
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_d),
        reward_dollars=float(reward_d),
    )
