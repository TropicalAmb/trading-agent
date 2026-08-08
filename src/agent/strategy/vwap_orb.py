from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


@dataclass
class OrbSignal:
    symbol: str
    side: str
    entry: float
    stop: float
    target: float
    confidence: int
    reason: str
    or_high: float
    or_low: float
    vwap: float
    ts: datetime
    risk_dollars: float
    reward_dollars: float


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0)
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        days = idx.tz_convert(ET).date
    else:
        days = idx.date
    return (typical * vol).groupby(days).cumsum() / vol.groupby(days).cumsum()


def _atr(df: pd.DataFrame, n: int = 14) -> float:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    val = float(tr.rolling(n).mean().iloc[-1])
    return val if np.isfinite(val) and val > 0 else float(df["close"].iloc[-1]) * 0.001


def evaluate_vwap_orb(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
    now: datetime | None = None,
) -> Optional[OrbSignal]:
    """Filtered Opening Range Breakout + VWAP alignment (research default)."""
    strat = cfg.get("vwap_orb", {})
    if bars is None or len(bars) < 40:
        return None

    df = bars.copy()
    df.columns = [c.lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = 1.0

    # Normalize index to ET-naive for session slicing
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(ET).tz_localize(None)
    df.index = idx

    or_start = time(*map(int, str(strat.get("or_start", "09:30")).split(":")))
    or_end = time(*map(int, str(strat.get("or_end", "09:45")).split(":")))
    entry_end = time(*map(int, str(strat.get("entry_end", "11:30")).split(":")))
    flatten_ct = time(*map(int, str(strat.get("flatten_ct", "15:05")).split(":")))

    now = now or datetime.now(ET)
    if now.tzinfo is None:
        now_et = now.replace(tzinfo=ET)
    else:
        now_et = now.astimezone(ET)

    # Topstep-style: no new risk near flatten
    ct = now_et.astimezone(ZoneInfo("America/Chicago")).time()
    if ct >= flatten_ct:
        return None

    today = now_et.date()
    day = df[df.index.date == today]
    if day.empty:
        # use last available session in data
        today = df.index[-1].date()
        day = df[df.index.date == today]
    if len(day) < 5:
        return None

    or_bars = day.between_time(or_start.strftime("%H:%M"), or_end.strftime("%H:%M"))
    # between_time end is inclusive-ish; exclude bars after or_end strictly
    or_bars = day[(day.index.time >= or_start) & (day.index.time < or_end)]
    if len(or_bars) < 2:
        return None

    or_high = float(or_bars["high"].max())
    or_low = float(or_bars["low"].min())
    or_width = or_high - or_low
    min_width = float(strat.get("min_or_width_points", 4.0))
    max_width = float(strat.get("max_or_width_points", 120.0))
    # Per-symbol overrides (MNQ typically wider than MES)
    sym_caps = strat.get("width_caps", {})
    if symbol in sym_caps:
        min_width = float(sym_caps[symbol].get("min", min_width))
        max_width = float(sym_caps[symbol].get("max", max_width))
    if or_width < min_width or or_width > max_width:
        logger.info("%s OR width %.2f outside [%.1f, %.1f]", symbol, or_width, min_width, max_width)
        return None

    # Only after OR complete and before entry_end
    last_t = day.index[-1].time()
    if last_t < or_end or last_t > entry_end:
        return None

    df["vwap"] = _session_vwap(df)
    df["ema_fast"] = _ema(df["close"], int(strat.get("fast_ema", 20)))
    df["ema_slow"] = _ema(df["close"], int(strat.get("slow_ema", 50)))
    row = df.loc[day.index[-1]]
    close = float(row["close"])
    vwap = float(row["vwap"])
    ema_f = float(row["ema_fast"])
    ema_s = float(row["ema_slow"])
    atr = _atr(df)

    long_break = close > or_high and close > vwap and ema_f >= ema_s
    short_break = close < or_low and close < vwap and ema_f <= ema_s
    if not long_break and not short_break:
        return None

    # Prefer first break only: if both sides already traded through, skip chop
    traded_above = bool((day["high"] > or_high).sum() >= 1)
    traded_below = bool((day["low"] < or_low).sum() >= 1)
    if traded_above and traded_below and bool(strat.get("skip_two_sided_days", True)):
        # Allow only if this is the second-direction continuation filter (optional)
        if not bool(strat.get("allow_second_break", False)):
            logger.info("%s two-sided OR day — skip", symbol)
            return None

    side = "BUY" if long_break else "SELL"
    entry = close
    buffer = float(strat.get("stop_buffer_points", 1.0))
    target_dollars = float(strat.get("target_dollars", 150.0))
    max_risk = float(strat.get("max_risk_dollars", 100.0))
    min_reward = float(strat.get("min_reward_dollars", 100.0))
    target_r = float(strat.get("target_r_multiple", 2.0))

    if side == "BUY":
        stop = or_low - buffer
        risk_pts = max(entry - stop, atr * 0.5)
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        # Cap risk in points by dollars
        max_risk_pts = max_risk / point_value
        if risk_pts > max_risk_pts:
            stop = entry - max_risk_pts
            risk_pts = max_risk_pts
            target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry + target_pts
    else:
        stop = or_high + buffer
        risk_pts = max(stop - entry, atr * 0.5)
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        max_risk_pts = max_risk / point_value
        if risk_pts > max_risk_pts:
            stop = entry + max_risk_pts
            risk_pts = max_risk_pts
            target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry - target_pts

    risk_dollars = risk_pts * point_value
    reward_dollars = abs(target - entry) * point_value
    if risk_dollars > max_risk + 1e-6 or reward_dollars < min_reward:
        return None

    # Confidence heuristic: wider OR + VWAP distance + trend stack
    conf = 55
    conf += 10 if or_width >= min_width * 1.5 else 0
    conf += 10 if (side == "BUY" and close > vwap) or (side == "SELL" and close < vwap) else 0
    conf += 10 if (side == "BUY" and ema_f > ema_s) or (side == "SELL" and ema_f < ema_s) else 0
    conf += 5 if risk_dollars <= max_risk * 0.8 else 0
    conf = min(95, conf)
    min_conf = int(strat.get("min_confidence", 65))
    if conf < min_conf:
        return None

    reason = (
        f"{side} filtered-ORB+VWAP or=[{or_low:.2f},{or_high:.2f}] "
        f"vwap={vwap:.2f}"
    )
    return OrbSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=reason,
        or_high=or_high,
        or_low=or_low,
        vwap=vwap,
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_dollars),
        reward_dollars=float(reward_dollars),
    )


class VwapOrbScanner:
    def __init__(self, cfg: dict[str, Any], bar_source):
        self.cfg = cfg
        self.bar_source = bar_source

    def scan_universe(self) -> list[OrbSignal]:
        out: list[OrbSignal] = []
        for sym in self.cfg.get("universe", {}).get("symbols", []):
            try:
                meta = self.cfg.get("instruments", {}).get(sym, {})
                sig = evaluate_vwap_orb(
                    sym,
                    self.bar_source(sym),
                    self.cfg,
                    point_value=float(meta.get("point_value", 5.0)),
                )
                if sig:
                    out.append(sig)
                    logger.info("%s", sig.reason)
            except Exception:
                logger.exception("vwap_orb scan failed %s", sym)
        out.sort(key=lambda s: s.confidence, reverse=True)
        return out
