"""Breakout / momentum continuation — MOMENTUM_PRESENT ≠ MOMENTUM_ENTRY_VALID."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
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
    momentum_present: bool = True
    entry_valid: bool = True


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


def evaluate_momentum(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[MomentumSignal]:
    strat = cfg.get("momentum") or {}
    if not bool(strat.get("enabled", True)):
        return None
    if df is None or len(df) < 40:
        return None

    min_body = float(strat.get("min_body_atr", 0.40))
    max_body = float(strat.get("max_body_atr", 1.20))
    max_dist = float(strat.get("max_distance_from_fast_ema_atr", 0.60))
    close_str_min = float(strat.get("close_strength_min", 0.65))
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 1.6))
    max_risk = float(strat.get("max_risk_dollars", 150))
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 62))

    atr = _atr(df)
    ema20 = _ema(df["close"], 20)
    ema50 = _ema(df["close"], 50)
    row = df.iloc[-1]
    prev = df.iloc[-2]
    a = float(atr.iloc[-1] or 0.0)
    if a <= 1e-12:
        return None

    o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
    body = abs(c - o)
    full = max(h - l, 1e-9)
    body_atr = body / a
    close_strength = (c - l) / full if c >= o else (h - c) / full

    # MOMENTUM_PRESENT
    momentum_present = body_atr >= min_body
    if not momentum_present:
        return None

    side = "BUY" if c > o else "SELL"
    # Exhaustion: oversized body
    if body_atr > max_body:
        logger.debug("%s MOMENTUM_PRESENT but exhaustion body=%.2fATR", symbol, body_atr)
        return None

    e20 = float(ema20.iloc[-1])
    e50 = float(ema50.iloc[-1])
    dist = abs(c - e20) / a
    if dist > max_dist:
        logger.debug("%s momentum too extended from EMA (%.2fATR)", symbol, dist)
        return None

    if close_strength < close_str_min:
        return None

    # Breakout / continuation: close beyond prior structural extreme
    look = int(strat.get("breakout_lookback", 8))
    prior_high = float(df["high"].iloc[-look - 1 : -1].max())
    prior_low = float(df["low"].iloc[-look - 1 : -1].min())
    if side == "BUY":
        if not (c >= prior_high and e20 >= e50 * 0.999):
            return None
        entry = c
        stop = entry - stop_atr * a
        target = entry + target_r * (entry - stop)
    else:
        if not (c <= prior_low and e20 <= e50 * 1.001):
            return None
        entry = c
        stop = entry + stop_atr * a
        target = entry - target_r * (stop - entry)

    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if risk_d > max_risk or reward_d < min_reward:
        return None
    if risk_d > 0 and reward_d / risk_d < 1.3:
        return None

    conf = min_conf
    conf += 6 if body_atr >= 0.55 else 0
    conf += 6 if close_strength >= 0.75 else 0
    conf += 4 if dist <= 0.35 else 0
    conf = int(min(92, conf))

    ts = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else datetime.now(timezone.utc)
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=timezone.utc)

    return MomentumSignal(
        symbol=symbol.upper(),
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=conf,
        reason=f"{side} MOMENTUM_ENTRY_VALID body={body_atr:.2f}ATR close_str={close_strength:.2f}",
        ts=ts,
        risk_dollars=float(risk_d),
        reward_dollars=float(reward_d),
        momentum_present=True,
        entry_valid=True,
    )
