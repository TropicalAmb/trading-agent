"""Deterministic market regime classifier (no LLM, completed bars only)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class MarketRegime(str, Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    COMPRESSION = "COMPRESSION"
    EXPANSION_UP = "EXPANSION_UP"
    EXPANSION_DOWN = "EXPANSION_DOWN"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RegimeResult:
    regime: MarketRegime
    confidence: float
    atr_pct: float
    trend_strength: float
    compression_score: float
    reasons: tuple[str, ...]


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


class MarketRegimeClassifier:
    """Classify regime from completed OHLCV bars (no lookahead)."""

    def classify(self, bars: pd.DataFrame | None) -> RegimeResult:
        if bars is None or len(bars) < 55:
            return RegimeResult(
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                atr_pct=0.0,
                trend_strength=0.0,
                compression_score=0.0,
                reasons=("INSUFFICIENT_BARS",),
            )

        df = bars.copy()
        # Use only completed bars already in frame (caller slices to market time)
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        ema20 = _ema(close, 20)
        ema50 = _ema(close, 50)
        atr = _atr(df, 14)
        atr_base = atr.rolling(50).mean()

        c = float(close.iloc[-1])
        e20 = float(ema20.iloc[-1])
        e50 = float(ema50.iloc[-1])
        a = float(atr.iloc[-1] or 0.0)
        a_base = float(atr_base.iloc[-1] or a or 1.0)
        if a_base <= 1e-12:
            a_base = 1.0

        atr_pct = a / max(abs(c), 1e-9) * 100.0
        ema_sep = abs(e20 - e50) / max(a, 1e-9)
        slope20 = float(ema20.iloc[-1] - ema20.iloc[-6]) / max(a, 1e-9)
        slope50 = float(ema50.iloc[-1] - ema50.iloc[-6]) / max(a, 1e-9)

        # Structure: recent HH/HL or LH/LL
        look = min(20, len(close) - 2)
        hh = float(high.iloc[-look:].max())
        ll = float(low.iloc[-look:].min())
        mid_hh = float(high.iloc[-look : -look // 2].max()) if look >= 4 else hh
        mid_ll = float(low.iloc[-look : -look // 2].min()) if look >= 4 else ll
        bull_struct = hh >= mid_hh and float(low.iloc[-1]) >= mid_ll * 0.998
        bear_struct = ll <= mid_ll and float(high.iloc[-1]) <= mid_hh * 1.002

        # Compression / expansion via recent TR vs ATR
        tr_last = float(high.iloc[-1] - low.iloc[-1])
        recent_tr = (high - low).iloc[-10:].mean()
        compression_score = float(np.clip(1.0 - (recent_tr / max(a, 1e-9)), 0.0, 1.0))
        expansion_ratio = tr_last / max(a, 1e-9)
        vol_ratio = a / max(a_base, 1e-9)

        reasons: list[str] = []
        regime = MarketRegime.RANGE
        conf = 50.0
        trend_strength = float(np.clip(ema_sep * 0.5 + abs(slope20) * 0.5, 0.0, 3.0))

        if vol_ratio >= 1.6:
            regime = MarketRegime.HIGH_VOLATILITY
            conf = min(90.0, 55.0 + (vol_ratio - 1.6) * 40.0)
            reasons.append(f"ATR elevated vs baseline ({vol_ratio:.2f}x)")
        elif expansion_ratio >= 1.35 and c > float(close.iloc[-2]):
            regime = MarketRegime.EXPANSION_UP
            conf = min(88.0, 55.0 + expansion_ratio * 15.0)
            reasons.append("directional expansion up")
        elif expansion_ratio >= 1.35 and c < float(close.iloc[-2]):
            regime = MarketRegime.EXPANSION_DOWN
            conf = min(88.0, 55.0 + expansion_ratio * 15.0)
            reasons.append("directional expansion down")
        elif compression_score >= 0.35 and ema_sep < 0.45:
            regime = MarketRegime.COMPRESSION
            conf = min(85.0, 50.0 + compression_score * 50.0)
            reasons.append("compressed ranges / low expansion")
        elif e20 > e50 and c > e20 and slope20 > 0 and (bull_struct or slope50 >= 0):
            regime = MarketRegime.TREND_UP
            conf = min(92.0, 55.0 + ema_sep * 20.0 + max(0.0, slope20) * 15.0)
            reasons.append("EMA20>EMA50, price above fast EMA, up slope")
        elif e20 < e50 and c < e20 and slope20 < 0 and (bear_struct or slope50 <= 0):
            regime = MarketRegime.TREND_DOWN
            conf = min(92.0, 55.0 + ema_sep * 20.0 + max(0.0, -slope20) * 15.0)
            reasons.append("EMA20<EMA50, price below fast EMA, down slope")
        else:
            regime = MarketRegime.RANGE
            conf = min(80.0, 45.0 + (1.0 - min(ema_sep, 1.0)) * 30.0)
            reasons.append("weak EMA separation / mixed structure")

        return RegimeResult(
            regime=regime,
            confidence=round(float(conf), 2),
            atr_pct=round(float(atr_pct), 4),
            trend_strength=round(float(trend_strength), 4),
            compression_score=round(float(compression_score), 4),
            reasons=tuple(reasons),
        )


def regime_weight(cfg: dict[str, Any], strategy: str, regime: MarketRegime) -> float:
    """Favorable/neutral/unfavorable multiplier (clamped later in scoring)."""
    table = (cfg.get("strategy_regime_weights") or {}).get(strategy) or {}
    return float(table.get(regime.value, table.get(str(regime), 1.0)))
