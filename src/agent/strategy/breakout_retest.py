"""Breakout + retest continuation. BREAKOUT_PRESENT ≠ BREAKOUT_RETEST_ENTRY_VALID."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd


@dataclass
class BreakoutRetestSignal:
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
    breakout_present: bool = True
    entry_valid: bool = True
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


def evaluate_breakout_retest(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[BreakoutRetestSignal]:
    strat = cfg.get("breakout_retest") or {}
    if not bool(strat.get("enabled", True)):
        return None
    if df is None or len(df) < 40:
        return None

    lookback = int(strat.get("breakout_lookback", 12))
    retest_bars = int(strat.get("retest_lookback", 6))
    max_body = float(strat.get("max_breakout_body_atr", 1.25))
    hold_tol = float(strat.get("retest_hold_atr", 0.25))
    stop_atr = float(strat.get("stop_atr_mult", 0.9))
    target_r = float(strat.get("target_r_multiple", 1.7))
    max_risk = float(strat.get("max_risk_dollars", 150))
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 64))

    atr = _atr(df)
    a = float(atr.iloc[-1] or 0.0)
    if a <= 1e-12:
        return None

    # Completed bars only — exclude last for level, then use last as signal bar
    hist = df.iloc[-(lookback + retest_bars + 2) : -1]
    if len(hist) < lookback + 2:
        return None
    level_high = float(hist["high"].iloc[:lookback].max())
    level_low = float(hist["low"].iloc[:lookback].min())

    # Find breakout bar in recent window (not the last bar)
    window = df.iloc[-(retest_bars + 2) : -1]
    breakout_long = None
    breakout_short = None
    for i in range(len(window)):
        row = window.iloc[i]
        body = abs(float(row["close"]) - float(row["open"]))
        if body > max_body * a:
            continue  # exhaustion — present but not valid chase
        if float(row["close"]) > level_high and float(row["close"]) > float(row["open"]):
            breakout_long = (i, float(row["close"]))
        if float(row["close"]) < level_low and float(row["close"]) < float(row["open"]):
            breakout_short = (i, float(row["close"]))

    last = df.iloc[-1]
    c, o, h, l = float(last["close"]), float(last["open"]), float(last["high"]), float(last["low"])
    side = None
    level = None
    if breakout_long is not None:
        # Retest: wick/close back near level and reclaim
        near = abs(l - level_high) <= hold_tol * a or abs(c - level_high) <= hold_tol * a
        hold = c >= level_high - hold_tol * a and c > o
        if near and hold:
            side, level = "BUY", level_high
    if side is None and breakout_short is not None:
        near = abs(h - level_low) <= hold_tol * a or abs(c - level_low) <= hold_tol * a
        hold = c <= level_low + hold_tol * a and c < o
        if near and hold:
            side, level = "SELL", level_low

    if side is None or level is None:
        return None

    entry = c
    if side == "BUY":
        stop = min(l, level) - stop_atr * a * 0.35
        risk_pts = max(entry - stop, a * 0.35)
        target = entry + max(risk_pts * target_r, min_reward / point_value)
    else:
        stop = max(h, level) + stop_atr * a * 0.35
        risk_pts = max(stop - entry, a * 0.35)
        target = entry - max(risk_pts * target_r, min_reward / point_value)

    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if risk_d > max_risk or reward_d < min_reward:
        return None
    if risk_d > 0 and reward_d / risk_d < 1.3:
        return None

    conf = 68
    conf += 8 if abs(c - level) <= 0.35 * a else 0
    conf += 6 if reward_d >= risk_d * 1.6 else 0
    conf = min(92, conf)
    if conf < min_conf:
        return None

    return BreakoutRetestSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=f"{side} BREAKOUT_RETEST hold@{level:.2f}",
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_d),
        reward_dollars=float(reward_d),
        breakout_present=True,
        entry_valid=True,
        level=float(level),
    )
