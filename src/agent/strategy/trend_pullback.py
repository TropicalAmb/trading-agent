"""Simple HTF-trend pullback specialist — additive TradeSetup producer.

Deterministic rules (not a rewrite of ema_pullback):
1) Trend: EMA20 vs EMA50
2) Pullback into EMA20 zone
3) Reclaim / rejection candle in trend direction
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


@dataclass
class TrendPullbackSignal:
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


def evaluate_trend_pullback(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[TrendPullbackSignal]:
    strat = cfg.get("trend_pullback") or {}
    if not bool(strat.get("enabled", True)):
        return None
    if df is None or len(df) < 60:
        return None

    touch_atr = float(strat.get("touch_atr", 0.40))
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 1.5))
    max_risk = float(strat.get("max_risk_dollars", 0) or 0)
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 62))
    lookback = int(strat.get("pullback_lookback", 6))

    atr = _atr(df)
    ema20 = _ema(df["close"], 20)
    ema50 = _ema(df["close"], 50)
    a = float(atr.iloc[-1] or 0.0)
    if a <= 1e-12:
        return None

    last = df.iloc[-1]
    c, o = float(last["close"]), float(last["open"])
    h, l = float(last["high"]), float(last["low"])
    e20, e50 = float(ema20.iloc[-1]), float(ema50.iloc[-1])
    window = df.iloc[-(lookback + 1) : -1]
    if window.empty:
        return None

    bull = e20 > e50 and c > e50
    bear = e20 < e50 and c < e50
    side = None
    level = e20
    if bull:
        touched = bool((window["low"] <= e20 + touch_atr * a).any())
        reclaim = c > e20 and c > o and l <= e20 + touch_atr * a
        if touched and reclaim:
            side = "BUY"
    elif bear:
        touched = bool((window["high"] >= e20 - touch_atr * a).any())
        reclaim = c < e20 and c < o and h >= e20 - touch_atr * a
        if touched and reclaim:
            side = "SELL"
    if side is None:
        return None

    entry = c
    if side == "BUY":
        stop = min(l, e20) - stop_atr * a * 0.35
        risk_pts = max(entry - stop, a * 0.35)
        target = entry + max(risk_pts * target_r, min_reward / max(point_value, 1e-9))
    else:
        stop = max(h, e20) + stop_atr * a * 0.35
        risk_pts = max(stop - entry, a * 0.35)
        target = entry - max(risk_pts * target_r, min_reward / max(point_value, 1e-9))

    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if max_risk > 0 and risk_d > max_risk:
        return None
    if reward_d < min_reward * 0.5:
        return None

    conf = min_conf + (6 if abs(e20 - e50) > a * 0.15 else 0)
    conf = min(88, conf)
    ts = df.index[-1].to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return TrendPullbackSignal(
        symbol=symbol.upper(),
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        confidence=conf,
        reason=f"trend_pullback:{side}:ema20_reclaim",
        ts=ts,
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        level=level,
    )
