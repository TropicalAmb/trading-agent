"""Opening-range breakout / retest / failed-break for London & NY."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
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


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        days = idx.tz_convert(ET).date
    else:
        days = idx.date
    return (typical * vol).groupby(days).cumsum() / vol.groupby(days).cumsum()


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

    default_duration = int(strat.get("duration_minutes", 15))
    sessions = strat.get("sessions") or {
        "london": "03:00",
        "ny": "09:30",
    }
    stop_atr = float(strat.get("stop_atr_mult", 0.85))
    target_r = float(strat.get("target_r_multiple", 1.6))
    max_risk = float(strat.get("max_risk_dollars", 150))
    min_reward = float(strat.get("min_reward_dollars", 80))
    min_conf = int(strat.get("min_confidence", 64))
    # Per-session entry style: retest | first_break
    # WIT research + walk-forward: NY 5m first_break + skip Friday was strongest OOS book.
    default_style = "retest" if bool(strat.get("require_retest", True)) else "first_break"

    atr = _atr(df)
    a = float(atr.iloc[-1] or 0.0)
    if a <= 1e-12:
        return None

    x = df.copy()
    if not isinstance(x.index, pd.DatetimeIndex):
        x.index = pd.to_datetime(x.index)

    or_hi = or_lo = None
    sess_name = None
    duration = default_duration
    entry_style = default_style
    for name, hhmm in sessions.items():
        dur = int(
            strat.get(f"duration_minutes_{name}", default_duration)
            or default_duration
        )
        style = str(
            strat.get(f"entry_mode_{name}", strat.get("entry_mode", default_style))
            or default_style
        ).lower()
        hi, lo = _session_or(x, open_hhmm=str(hhmm), duration_min=dur)
        if hi is not None:
            or_hi, or_lo, sess_name = hi, lo, name
            duration = dur
            entry_style = style
            # Prefer the most recent completed OR that still has post-OR bars
            oh, om = map(int, str(hhmm).split(":"))
            post_start = x.index[-1].normalize() + pd.Timedelta(hours=oh, minutes=om + dur)
            post = x[x.index >= post_start]
            if len(post) >= 2:
                break
    if or_hi is None or or_lo is None:
        return None

    last = x.iloc[-1]
    prev = x.iloc[-2]
    c, o = float(last["close"]), float(last["open"])
    h, l = float(last["high"]), float(last["low"])
    pc = float(prev["close"])
    body = abs(c - o)

    side = None
    level = None
    mode = ""
    if entry_style == "first_break":
        # No chasing giant expansion candles (exhaustion filter)
        max_body = float(strat.get("max_breakout_body_atr", 1.25)) * a
        if body <= max_body and c > or_hi and c > o and pc <= or_hi:
            side, level, mode = "BUY", or_hi, "or_first_break"
        elif body <= max_body and c < or_lo and c < o and pc >= or_lo:
            side, level, mode = "SELL", or_lo, "or_first_break"
    else:
        # Retest / failed-OR (A+ group framework)
        if pc > or_hi and l <= or_hi + 0.15 * a and c >= or_hi and c > o:
            side, level, mode = "BUY", or_hi, "or_retest"
        elif pc < or_lo and h >= or_lo - 0.15 * a and c <= or_lo and c < o:
            side, level, mode = "SELL", or_lo, "or_retest"
        elif float(prev["high"]) > or_hi and c < or_hi and c < o:
            side, level, mode = "SELL", or_hi, "failed_or"
        elif float(prev["low"]) < or_lo and c > or_lo and c > o:
            side, level, mode = "BUY", or_lo, "failed_or"

    if side is None or level is None:
        return None

    # Accuracy filter (research): long only above VWAP, short only below
    if bool(strat.get("require_vwap_align", True)):
        vwap = _session_vwap(x)
        v = float(vwap.iloc[-1])
        if np.isfinite(v):
            if side == "BUY" and c < v:
                return None
            if side == "SELL" and c > v:
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
    if max_risk > 0 and risk_d > max_risk:
        return None
    if reward_d < min_reward:
        return None
    if risk_d > 0 and reward_d / risk_d < 1.3:
        return None

    conf = 65
    conf += 8 if mode == "or_retest" else 0
    conf += 4 if mode == "failed_or" else 0
    conf += 3 if mode == "or_first_break" else 0
    if bool(strat.get("require_vwap_align", True)):
        conf += 4
    conf = min(92, conf)
    if conf < min_conf:
        return None

    return OpeningRangeSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=f"{side} OPENING_RANGE {sess_name} {mode} {duration}m vwap_align",
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_d),
        reward_dollars=float(reward_d),
        level=float(level),
    )
