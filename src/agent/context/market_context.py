"""TradingView-style market context (deterministic, no TV dependency, no lookahead)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from agent.context.regime import MarketRegime, MarketRegimeClassifier, RegimeResult


@dataclass(frozen=True)
class MarketContext:
    direction_15m: int
    direction_1h: int
    direction_4h: int
    mtf_bull_count: int
    mtf_bear_count: int
    above_vwap: bool
    below_vwap: bool
    ema_bull: bool
    ema_bear: bool
    pdh: float | None
    pdl: float | None
    near_pdh: bool
    near_pdl: bool
    overextended_long: bool
    overextended_short: bool
    momentum_up: bool
    momentum_down: bool
    regime: MarketRegime
    regime_confidence: float
    reasons: tuple[str, ...]


def _candle_dir(o: float, c: float) -> int:
    if c > o:
        return 1
    if c < o:
        return -1
    return 0


def _resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample using index timestamps (market time). Incomplete last bar dropped."""
    if not isinstance(df.index, pd.DatetimeIndex):
        idx = pd.to_datetime(df.index)
        x = df.copy()
        x.index = idx
    else:
        x = df
    ohlc = x.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    ohlc = ohlc.dropna(subset=["open", "close"])
    # Drop last bucket as potentially incomplete (no lookahead into partial HTF bar)
    if len(ohlc) >= 2:
        ohlc = ohlc.iloc[:-1]
    return ohlc


def _session_vwap(df: pd.DataFrame) -> float:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0)
    # Approximate session: last 78 five-minute bars (~RTH) or all available
    n = min(len(df), 78)
    sl = slice(-n, None)
    v = float((tp.iloc[sl] * vol.iloc[sl]).sum() / max(vol.iloc[sl].sum(), 1e-9))
    return v


def _prior_day_levels(df: pd.DataFrame) -> tuple[Optional[float], Optional[float]]:
    if not isinstance(df.index, pd.DatetimeIndex):
        return None, None
    days = df.index.normalize().unique()
    if len(days) < 2:
        return None, None
    prev = days[-2]
    day = df[df.index.normalize() == prev]
    if day.empty:
        return None, None
    return float(day["high"].max()), float(day["low"].min())


def build_market_context(
    bars: pd.DataFrame,
    *,
    cfg: dict[str, Any] | None = None,
    regime_result: RegimeResult | None = None,
) -> MarketContext:
    cfg = cfg or {}
    reasons: list[str] = []
    if bars is None or len(bars) < 30:
        rr = regime_result or MarketRegimeClassifier().classify(bars)
        return MarketContext(
            direction_15m=0,
            direction_1h=0,
            direction_4h=0,
            mtf_bull_count=0,
            mtf_bear_count=0,
            above_vwap=False,
            below_vwap=False,
            ema_bull=False,
            ema_bear=False,
            pdh=None,
            pdl=None,
            near_pdh=False,
            near_pdl=False,
            overextended_long=False,
            overextended_short=False,
            momentum_up=False,
            momentum_down=False,
            regime=rr.regime,
            regime_confidence=rr.confidence,
            reasons=("INSUFFICIENT_BARS",),
        )

    df = bars.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # HTF candle direction = close vs open of completed HTF bars (NOT EMA)
    d15 = d1h = d4h = 0
    try:
        r15 = _resample_ohlc(df, "15min")
        if len(r15):
            d15 = _candle_dir(float(r15["open"].iloc[-1]), float(r15["close"].iloc[-1]))
            reasons.append(f"15m_candle={'bull' if d15>0 else 'bear' if d15<0 else 'flat'}")
    except Exception:
        pass
    try:
        r1h = _resample_ohlc(df, "1h")
        if len(r1h):
            d1h = _candle_dir(float(r1h["open"].iloc[-1]), float(r1h["close"].iloc[-1]))
            reasons.append(f"1h_candle={'bull' if d1h>0 else 'bear' if d1h<0 else 'flat'}")
    except Exception:
        pass
    try:
        r4h = _resample_ohlc(df, "4h")
        if len(r4h):
            d4h = _candle_dir(float(r4h["open"].iloc[-1]), float(r4h["close"].iloc[-1]))
            reasons.append(f"4h_candle={'bull' if d4h>0 else 'bear' if d4h<0 else 'flat'}")
    except Exception:
        pass

    dirs = [d15, d1h, d4h]
    mtf_bull = sum(1 for d in dirs if d > 0)
    mtf_bear = sum(1 for d in dirs if d < 0)

    close = df["close"].astype(float)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    c = float(close.iloc[-1])
    e20 = float(ema20.iloc[-1])
    e50 = float(ema50.iloc[-1])
    ema_bull = e20 > e50 and c > e20
    ema_bear = e20 < e50 and c < e20
    if ema_bull:
        reasons.append("ema_structure_bull")
    elif ema_bear:
        reasons.append("ema_structure_bear")

    vwap = _session_vwap(df)
    above_vwap = c > vwap
    below_vwap = c < vwap
    reasons.append("above_vwap" if above_vwap else "below_vwap" if below_vwap else "at_vwap")

    pdh, pdl = _prior_day_levels(df)
    # ATR for proximity / extension
    prev = close.shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev).abs(),
            (df["low"] - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1] or 0.0)
    near_pdh = bool(pdh is not None and atr > 0 and abs(c - pdh) <= 0.35 * atr)
    near_pdl = bool(pdl is not None and atr > 0 and abs(c - pdl) <= 0.35 * atr)

    over_long = bool(atr > 0 and (c - e20) > 1.8 * atr)
    over_short = bool(atr > 0 and (e20 - c) > 1.8 * atr)

    body = abs(float(df["close"].iloc[-1]) - float(df["open"].iloc[-1]))
    momentum_up = body >= 0.45 * atr and float(df["close"].iloc[-1]) > float(df["open"].iloc[-1])
    momentum_down = body >= 0.45 * atr and float(df["close"].iloc[-1]) < float(df["open"].iloc[-1])

    rr = regime_result or MarketRegimeClassifier().classify(df)

    return MarketContext(
        direction_15m=d15,
        direction_1h=d1h,
        direction_4h=d4h,
        mtf_bull_count=mtf_bull,
        mtf_bear_count=mtf_bear,
        above_vwap=above_vwap,
        below_vwap=below_vwap,
        ema_bull=ema_bull,
        ema_bear=ema_bear,
        pdh=pdh,
        pdl=pdl,
        near_pdh=near_pdh,
        near_pdl=near_pdl,
        overextended_long=over_long,
        overextended_short=over_short,
        momentum_up=momentum_up,
        momentum_down=momentum_down,
        regime=rr.regime,
        regime_confidence=rr.confidence,
        reasons=tuple(reasons),
    )
