"""Simple liquidity-reversal specialist — additive TradeSetup producer.

Deterministic rules (not a rewrite of liquidity_sweep):
1) Sweep: wick beyond recent swing high/low
2) Close back inside the range (rejection)
3) Fade the sweep in the reclaim direction
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


@dataclass
class LiquidityReversalSignal:
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


def evaluate_liquidity_reversal(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[LiquidityReversalSignal]:
    strat = cfg.get("liquidity_reversal") or {}
    if not bool(strat.get("enabled", True)):
        return None
    if df is None or len(df) < 40:
        return None

    swing_n = int(strat.get("swing_lookback", 12))
    stop_atr = float(strat.get("stop_atr_mult", 0.85))
    target_r = float(strat.get("target_r_multiple", 1.5))
    max_risk = float(strat.get("max_risk_dollars", 0) or 0)
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 64))
    min_wick_atr = float(strat.get("min_wick_atr", 0.25))

    atr = _atr(df)
    a = float(atr.iloc[-1] or 0.0)
    if a <= 1e-12:
        return None

    hist = df.iloc[-(swing_n + 2) : -1]
    if len(hist) < swing_n:
        return None
    swing_hi = float(hist["high"].iloc[:swing_n].max())
    swing_lo = float(hist["low"].iloc[:swing_n].min())
    last = df.iloc[-1]
    c, o = float(last["close"]), float(last["open"])
    h, l = float(last["high"]), float(last["low"])

    side = None
    level = None
    # Sweep high then close back below → short
    if h > swing_hi + min_wick_atr * a * 0.1 and c < swing_hi and c < o:
        side, level = "SELL", swing_hi
    # Sweep low then close back above → long
    elif l < swing_lo - min_wick_atr * a * 0.1 and c > swing_lo and c > o:
        side, level = "BUY", swing_lo
    if side is None or level is None:
        return None

    entry = c
    if side == "BUY":
        stop = min(l, level) - stop_atr * a * 0.35
        risk_pts = max(entry - stop, a * 0.35)
        target = entry + max(risk_pts * target_r, min_reward / max(point_value, 1e-9))
    else:
        stop = max(h, level) + stop_atr * a * 0.35
        risk_pts = max(stop - entry, a * 0.35)
        target = entry - max(risk_pts * target_r, min_reward / max(point_value, 1e-9))

    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if max_risk > 0 and risk_d > max_risk:
        return None
    if reward_d < min_reward * 0.5:
        return None

    wick = (h - max(c, o)) if side == "SELL" else (min(c, o) - l)
    conf = min_conf + (5 if wick >= min_wick_atr * a else 0)
    conf = min(88, conf)
    ts = df.index[-1].to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return LiquidityReversalSignal(
        symbol=symbol.upper(),
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        confidence=conf,
        reason=f"liquidity_reversal:{side}:swing_reject",
        ts=ts,
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        level=level,
    )
