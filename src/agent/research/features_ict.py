"""Deterministic ICT/SMC-style features (no vague chart language)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
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


def session_vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
    day = df.index.normalize()
    return (tp * vol).groupby(day).cumsum() / vol.groupby(day).cumsum()


def swing_high_low(df: pd.DataFrame, left: int = 3, right: int = 3) -> tuple[pd.Series, pd.Series]:
    """Confirmed swing high/low, timestamped when the right bars are known."""
    h, l = df["high"], df["low"]
    sh = h.where(h == h.rolling(left + right + 1, center=True).max())
    sl = l.where(l == l.rolling(left + right + 1, center=True).min())
    return sh.shift(right), sl.shift(right)


def bullish_fvg_mask(df: pd.DataFrame) -> pd.Series:
    """3-candle bullish FVG: candle[i-2].high < candle[i].low (gap)."""
    return df["high"].shift(2) < df["low"]


def bearish_fvg_mask(df: pd.DataFrame) -> pd.Series:
    return df["low"].shift(2) > df["high"]


def fvg_zones(df: pd.DataFrame) -> list[dict]:
    """Return recent FVG zones with top/bottom and direction."""
    zones = []
    bull = bullish_fvg_mask(df)
    bear = bearish_fvg_mask(df)
    for i in range(2, len(df)):
        if bool(bull.iloc[i]):
            bottom = float(df["high"].iloc[i - 2])
            top = float(df["low"].iloc[i])
            if top > bottom:
                zones.append(
                    {
                        "i": i,
                        "ts": df.index[i],
                        "side": "BUY",
                        "bottom": bottom,
                        "top": top,
                    }
                )
        if bool(bear.iloc[i]):
            top = float(df["low"].iloc[i - 2])
            bottom = float(df["high"].iloc[i])
            if top > bottom:
                zones.append(
                    {
                        "i": i,
                        "ts": df.index[i],
                        "side": "SELL",
                        "bottom": bottom,
                        "top": top,
                    }
                )
    return zones


def displacement_mask(df: pd.DataFrame, atr_s: pd.Series, body_atr: float = 1.25) -> pd.Series:
    """Body size >= body_atr * ATR and closes in direction of body."""
    body = (df["close"] - df["open"]).abs()
    return (body >= body_atr * atr_s) & (df["close"] != df["open"])


def dealing_range_position(df: pd.DataFrame, lookback: int = 48) -> pd.Series:
    """0=discount low, 1=premium high within rolling lookback range."""
    hi = df["high"].rolling(lookback).max()
    lo = df["low"].rolling(lookback).min()
    span = (hi - lo).replace(0, np.nan)
    return (df["close"] - lo) / span


def liquidity_raid(
    df: pd.DataFrame,
    *,
    level: float,
    side: str,
    i: int,
) -> bool:
    """True if bar i raids level (high>level for SELL raid / low<level for BUY raid)."""
    if side == "SELL":
        return float(df["high"].iloc[i]) > level
    return float(df["low"].iloc[i]) < level


def mss_after_sweep(
    df: pd.DataFrame,
    *,
    sweep_i: int,
    side: str,
    structure_lookback: int = 8,
) -> int | None:
    """Market structure shift: after sweep, close through opposing swing within lookback.

    BUY MSS after low raid: close > max(high of prior structure_lookback bars before sweep)
    SELL MSS after high raid: close < min(low of prior structure_lookback bars before sweep)
    Returns bar index of MSS or None.
    """
    if sweep_i < structure_lookback + 1:
        return None
    pre = df.iloc[sweep_i - structure_lookback : sweep_i]
    if side == "BUY":
        level = float(pre["high"].max())
        for j in range(sweep_i + 1, min(len(df), sweep_i + 12)):
            if float(df["close"].iloc[j]) > level:
                return j
    else:
        level = float(pre["low"].min())
        for j in range(sweep_i + 1, min(len(df), sweep_i + 12)):
            if float(df["close"].iloc[j]) < level:
                return j
    return None


def mtf_direction(close: pd.Series, rule: str = "last_vs_prev") -> int:
    """+1 bullish, -1 bearish, 0 flat from resampled close series."""
    if len(close) < 2:
        return 0
    a, b = float(close.iloc[-2]), float(close.iloc[-1])
    if b > a:
        return 1
    if b < a:
        return -1
    return 0


def resample_closes(df: pd.DataFrame, rule: str) -> pd.Series:
    return df["close"].resample(rule).last().dropna()
