"""Simple VWAP reclaim specialist — additive TradeSetup producer.

Keeps vwap_acceptance intact. This engine only fires a clean reclaim:
prior close on wrong side of VWAP → close reclaim with body confirmation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass
class VwapReclaimSignal:
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


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
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


def evaluate_vwap_reclaim(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[VwapReclaimSignal]:
    strat = cfg.get("vwap_reclaim") or {}
    if not bool(strat.get("enabled", True)):
        return None
    # If still configured as disabled alias-only, do not fire
    if strat.get("alias_of") and not bool(strat.get("enabled", False)):
        return None
    if df is None or len(df) < 40:
        return None

    stop_atr = float(strat.get("stop_atr_mult", 0.9))
    target_r = float(strat.get("target_r_multiple", 1.5))
    max_risk = float(strat.get("max_risk_dollars", 0) or 0)
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 64))
    require_hold = bool(strat.get("require_hold_bar", False))

    work = df.copy()
    if "volume" not in work.columns:
        work["volume"] = 1.0
    vwap = _session_vwap(work)
    atr = _atr(work)
    a = float(atr.iloc[-1] or 0.0)
    vv = float(vwap.iloc[-1] or 0.0)
    if a <= 1e-12 or vv <= 0:
        return None

    last = work.iloc[-1]
    prev = work.iloc[-2]
    c, o = float(last["close"]), float(last["open"])
    h, l = float(last["high"]), float(last["low"])
    pc = float(prev["close"])
    pv = float(vwap.iloc[-2])

    side = None
    if pc < pv and c > vv and c > o:
        side = "BUY"
    elif pc > pv and c < vv and c < o:
        side = "SELL"
    if side is None:
        return None

    if require_hold and len(work) >= 3:
        # Optional: previous bar already crossed; current holds side
        hold_ok = (side == "BUY" and c >= vv) or (side == "SELL" and c <= vv)
        if not hold_ok:
            return None

    entry = c
    if side == "BUY":
        stop = min(l, vv) - stop_atr * a * 0.35
        risk_pts = max(entry - stop, a * 0.35)
        target = entry + max(risk_pts * target_r, min_reward / max(point_value, 1e-9))
    else:
        stop = max(h, vv) + stop_atr * a * 0.35
        risk_pts = max(stop - entry, a * 0.35)
        target = entry - max(risk_pts * target_r, min_reward / max(point_value, 1e-9))

    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if max_risk > 0 and risk_d > max_risk:
        return None
    if reward_d < min_reward * 0.5:
        return None

    conf = min(88, min_conf + 4)
    ts = work.index[-1].to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return VwapReclaimSignal(
        symbol=symbol.upper(),
        side=side,
        entry=entry,
        stop=stop,
        target=target,
        confidence=conf,
        reason=f"vwap_reclaim:{side}:cross_hold",
        ts=ts,
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        level=vv,
        vwap=vv,
    )
