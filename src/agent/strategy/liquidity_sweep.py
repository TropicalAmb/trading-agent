"""Location-first liquidity sweep → reclaim (PDH/PDL + VWAP regime).

Inspired by how price seeks stop/liquidity beyond prior day extremes, then often
reclaims. We do NOT chase the sweep; we wait for acceptance back inside.
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
class SweepFadeSignal:
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
    pdh: float
    pdl: float


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


def evaluate_liquidity_sweep(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[SweepFadeSignal]:
    strat = cfg.get("liquidity_sweep", {})
    if bars is None or len(bars) < 80:
        return None
    df = bars.copy()
    if "volume" not in df.columns:
        df["volume"] = 1.0

    daily = df.resample("1D").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    ).dropna()
    if len(daily) < 2:
        return None
    pdh = float(daily["high"].iloc[-2])
    pdl = float(daily["low"].iloc[-2])

    df["atr"] = _atr(df)
    df["vwap"] = _session_vwap(df)
    df["ema_fast"] = _ema(df["close"], int(strat.get("fast_ema", 20)))
    df["ema_slow"] = _ema(df["close"], int(strat.get("slow_ema", 50)))
    atr = float(df["atr"].iloc[-1])
    if not np.isfinite(atr) or atr <= 0:
        return None

    lookback = int(strat.get("sweep_lookback_bars", 12))
    window = df.iloc[-(lookback + 3) : -1]
    last = df.iloc[-1]
    prev = df.iloc[-2]
    c = float(last["close"])
    o = float(last["open"])
    h = float(last["high"])
    l = float(last["low"])
    vwap = float(last["vwap"])
    trend_up = float(last["ema_fast"]) >= float(last["ema_slow"])
    trend_dn = float(last["ema_fast"]) <= float(last["ema_slow"])

    # Magnets: prior day extremes + recent swing (equal-high / equal-low style pool)
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())
    level_high = max(pdh, swing_high)
    level_low = min(pdl, swing_low)

    swept_high = bool((window["high"] > pdh).any()) or bool(
        (window["high"] >= swing_high * 0.999).sum() >= 2
        and float(window["high"].iloc[-1]) >= swing_high
    )
    swept_low = bool((window["low"] < pdl).any()) or bool(
        (window["low"] <= swing_low * 1.001).sum() >= 2
        and float(window["low"].iloc[-1]) <= swing_low
    )
    # Reclaim: acceptance back inside after the raid (not chase the wick)
    # Soft reclaim for delayed bars: close back inside PDH/PDL is enough with candle direction
    soft = bool(strat.get("soft_reclaim", True))
    if soft:
        reclaim_short = swept_high and c < pdh and c < o
        reclaim_long = swept_low and c > pdl and c > o
    else:
        reclaim_short = swept_high and c < pdh and c < o and c < float(prev["low"])
        reclaim_long = swept_low and c > pdl and c > o and c > float(prev["high"])

    # VWAP filter: shorts prefer below/at VWAP after sweep high; longs above after sweep low
    short_ok = reclaim_short and c <= vwap * (1 + float(strat.get("vwap_slack", 0.0005)))
    long_ok = reclaim_long and c >= vwap * (1 - float(strat.get("vwap_slack", 0.0005)))
    # Prefer fading with regime, not fighting a strong opposite trend
    if short_ok and trend_up and not bool(strat.get("allow_against_trend", False)):
        short_ok = False
    if long_ok and trend_dn and not bool(strat.get("allow_against_trend", False)):
        long_ok = False

    stop_buf = float(strat.get("stop_buffer_atr", 0.35)) * atr
    target_r = float(strat.get("target_r_multiple", 1.8))
    target_dollars = float(strat.get("target_dollars", 150))
    min_reward = float(strat.get("min_reward_dollars", 120))
    max_risk = float(strat.get("max_risk_dollars", 150))
    min_conf = int(strat.get("min_confidence", 70))

    side = None
    entry = c
    stop = target = 0.0
    if short_ok:
        side = "SELL"
        # Stop beyond the swept liquidity wick (MM pool), not on the obvious level
        stop = max(h, level_high) + stop_buf
        risk_pts = max(stop - entry, atr * 0.5)
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry - target_pts
    elif long_ok:
        side = "BUY"
        stop = min(l, level_low) - stop_buf
        risk_pts = max(entry - stop, atr * 0.5)
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry + target_pts
    else:
        return None

    risk_dollars = abs(entry - stop) * point_value
    reward_dollars = abs(target - entry) * point_value
    if risk_dollars > max_risk or reward_dollars < min_reward:
        return None
    if risk_dollars > 0 and reward_dollars / risk_dollars < 1.5:
        return None

    conf = 62
    conf += 12 if (swept_high and side == "SELL") or (swept_low and side == "BUY") else 0
    conf += 8 if (side == "SELL" and c < vwap) or (side == "BUY" and c > vwap) else 0
    conf += 6 if reward_dollars >= risk_dollars * 1.8 else 0
    conf = min(96, conf)
    if conf < min_conf:
        return None

    return SweepFadeSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=f"{side} LIQUIDITY_SWEEP reclaim PDH/PDL+VWAP",
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_dollars),
        reward_dollars=float(reward_dollars),
        pdh=pdh,
        pdl=pdl,
    )


class LiquiditySweepScanner:
    def __init__(self, cfg: dict[str, Any], bar_source):
        self.cfg = cfg
        self.bar_source = bar_source

    def scan_symbol(self, symbol: str) -> Optional[SweepFadeSignal]:
        meta = self.cfg.get("instruments", {}).get(symbol, {})
        pv = float(meta.get("point_value", 5.0))
        try:
            return evaluate_liquidity_sweep(
                symbol, self.bar_source(symbol), self.cfg, point_value=pv
            )
        except Exception:
            logger.exception("liquidity_sweep failed %s", symbol)
            return None

    def scan_universe(self) -> list[SweepFadeSignal]:
        out = []
        for sym in self.cfg.get("universe", {}).get("symbols", []):
            s = self.scan_symbol(sym)
            if s is not None:
                out.append(s)
        out.sort(key=lambda x: x.confidence, reverse=True)
        return out
