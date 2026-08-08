"""Opening-range breakout / retest / failed-break for London & NY."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")


@dataclass
class OpeningRangeSignal:
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


def _session_or(
    df: pd.DataFrame, *, open_hhmm: str, duration_min: int
) -> tuple[Optional[float], Optional[float]]:
    if not isinstance(df.index, pd.DatetimeIndex) or len(df) < 10:
        return None, None
    oh, om = map(int, open_hhmm.split(":"))
    # Opening-range times are America/New_York clock times
    idx = df.index
    if getattr(idx, "tz", None) is None:
        idx_et = idx.tz_localize(ET)
    else:
        idx_et = idx.tz_convert(ET)
    x = df.copy()
    x.index = idx_et
    day = idx_et[-1].normalize()
    start = day + pd.Timedelta(hours=oh, minutes=om)
    end = start + pd.Timedelta(minutes=duration_min)
    or_bars = x[(x.index >= start) & (x.index < end)]
    if len(or_bars) < 2:
        return None, None
    return float(or_bars["high"].max()), float(or_bars["low"].min())


def evaluate_opening_range(
    symbol: str,
    df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[OpeningRangeSignal]:
    strat = cfg.get("opening_range") or {}
    if not bool(strat.get("enabled", True)):
        return None
    if df is None or len(df) < 40:
        return None

    duration = int(strat.get("duration_minutes", 15))
    sessions = strat.get("sessions") or {
        "london": "03:00",
        "ny": "09:30",
    }
    stop_atr = float(strat.get("stop_atr_mult", 0.85))
    target_r = float(strat.get("target_r_multiple", 1.6))
    max_risk = float(strat.get("max_risk_dollars", 150))
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 64))
    require_retest = bool(strat.get("require_retest", True))

    atr = _atr(df)
    a = float(atr.iloc[-1] or 0.0)
    if a <= 1e-12:
        return None

    x = df.copy()
    if not isinstance(x.index, pd.DatetimeIndex):
        x.index = pd.to_datetime(x.index)

    or_hi = or_lo = None
    sess_name = None
    for name, hhmm in sessions.items():
        hi, lo = _session_or(x, open_hhmm=str(hhmm), duration_min=duration)
        if hi is not None:
            or_hi, or_lo, sess_name = hi, lo, name
            # Prefer the most recent completed OR that still has post-OR bars
            post = x[x.index >= (x.index[-1].normalize() + pd.Timedelta(hours=int(hhmm.split(':')[0]), minutes=int(hhmm.split(':')[1]) + duration))]
            if len(post) >= 2:
                break
    if or_hi is None or or_lo is None:
        return None

    last = x.iloc[-1]
    prev = x.iloc[-2]
    c, o = float(last["close"]), float(last["open"])
    h, l = float(last["high"]), float(last["low"])
    pc = float(prev["close"])

    side = None
    level = None
    mode = ""
    # Breakout + retest hold (default) — do not auto-trade first break
    if require_retest:
        if pc > or_hi and l <= or_hi + 0.15 * a and c >= or_hi and c > o:
            side, level, mode = "BUY", or_hi, "or_retest"
        elif pc < or_lo and h >= or_lo - 0.15 * a and c <= or_lo and c < o:
            side, level, mode = "SELL", or_lo, "or_retest"
        # Failed breakout reversal
        elif float(prev["high"]) > or_hi and c < or_hi and c < o:
            side, level, mode = "SELL", or_hi, "failed_or"
        elif float(prev["low"]) < or_lo and c > or_lo and c > o:
            side, level, mode = "BUY", or_lo, "failed_or"
    else:
        if c > or_hi and c > o:
            side, level, mode = "BUY", or_hi, "or_break"
        elif c < or_lo and c < o:
            side, level, mode = "SELL", or_lo, "or_break"

    if side is None or level is None:
        return None

    entry = c
    if side == "BUY":
        stop = min(l, level) - stop_atr * a * 0.3
        risk_pts = max(entry - stop, a * 0.35)
        target = entry + max(risk_pts * target_r, min_reward / point_value)
    else:
        stop = max(h, level) + stop_atr * a * 0.3
        risk_pts = max(stop - entry, a * 0.35)
        target = entry - max(risk_pts * target_r, min_reward / point_value)

    risk_d = abs(entry - stop) * point_value
    reward_d = abs(target - entry) * point_value
    if risk_d > max_risk or reward_d < min_reward:
        return None
    if risk_d > 0 and reward_d / risk_d < 1.3:
        return None

    conf = 65
    conf += 8 if mode == "or_retest" else 0
    conf += 4 if mode == "failed_or" else 0
    conf = min(90, conf)
    if conf < min_conf:
        return None

    return OpeningRangeSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=f"{side} OPENING_RANGE {sess_name} {mode}",
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_d),
        reward_dollars=float(reward_d),
        level=float(level),
    )
