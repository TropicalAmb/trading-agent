from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SweepSignal:
    symbol: str
    side: str  # BUY | SELL
    entry: float
    stop: float
    target: float
    confidence: int
    reason: str
    pdh: float
    pdl: float
    ts: datetime
    risk_dollars: float
    reward_dollars: float


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(length).mean()


def _htf_state(df: pd.DataFrame) -> int:
    """1 bullish, -1 bearish, 0 neutral — last completed-ish bar."""
    if len(df) < 2:
        return 0
    o = float(df["open"].iloc[-1])
    c = float(df["close"].iloc[-1])
    if c > o:
        return 1
    if c < o:
        return -1
    return 0


def _resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    out = (
        df.resample(rule)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    return out


def _session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan).fillna(1.0)
    # Reset VWAP each calendar day
    day = df.index.tz_localize(None).date if df.index.tz is not None else df.index.date
    cum_pv = (typical * vol).groupby(day).cumsum()
    cum_v = vol.groupby(day).cumsum()
    return cum_pv / cum_v


def evaluate_sweep_retest(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
) -> Optional[SweepSignal]:
    """Port of the user's TradingView MTF Sweep Retest Assistant (entry rules).

    Expected bars columns: open, high, low, close, volume; DatetimeIndex.
    Base timeframe should be 5m or 15m; HTFs derived by resample.
    """
    strat = cfg.get("sweep_retest", cfg.get("strategy", {}))
    if bars is None or len(bars) < 80:
        return None

    df = bars.copy()
    df.columns = [c.lower() for c in df.columns]
    for col in ("open", "high", "low", "close"):
        if col not in df.columns:
            raise ValueError(f"bars missing {col}")
    if "volume" not in df.columns:
        df["volume"] = 1.0

    use_vwap = bool(strat.get("use_vwap", True))
    fast_len = int(strat.get("fast_ema", 20))
    slow_len = int(strat.get("slow_ema", 50))
    retest_atr = float(strat.get("retest_zone_atr", 0.15))
    sweep_valid = int(strat.get("sweep_valid_bars", 240))
    min_conf = int(strat.get("min_confidence", 70))
    target_r = float(strat.get("target_r_multiple", 2.0))
    stop_atr_mult = float(strat.get("stop_atr_mult", 1.0))
    # Dollar targeting for 1 contract (MES $5/pt default)
    target_dollars = float(strat.get("target_dollars", 150.0))
    max_risk_dollars = float(strat.get("max_risk_dollars", 100.0))

    df["fast"] = _ema(df["close"], fast_len)
    df["slow"] = _ema(df["close"], slow_len)
    df["atr"] = _atr(df)
    df["vwap"] = _session_vwap(df)

    # Previous day high/low from daily bars
    daily = _resample_ohlc(df, "1D")
    if len(daily) < 2:
        return None
    pdh = float(daily["high"].iloc[-2])
    pdl = float(daily["low"].iloc[-2])

    # HTF states from 15m / 1h / 4h
    s1 = _htf_state(_resample_ohlc(df, "15min"))
    s2 = _htf_state(_resample_ohlc(df, "1h"))
    s3 = _htf_state(_resample_ohlc(df, "4h"))

    all_bull = s1 == 1 and s2 == 1 and s3 == 1
    all_bear = s1 == -1 and s2 == -1 and s3 == -1
    # Delayed Yahoo rarely prints perfect 3-HTF alignment — 2 of 3 is enough
    soft_htf = bool(strat.get("soft_htf", True))
    if soft_htf:
        all_bull = sum(1 for s in (s1, s2, s3) if s == 1) >= 2
        all_bear = sum(1 for s in (s1, s2, s3) if s == -1) >= 2
    vwap_bull = float(df["close"].iloc[-1]) > float(df["vwap"].iloc[-1])
    vwap_bear = float(df["close"].iloc[-1]) < float(df["vwap"].iloc[-1])
    require_vwap = bool(strat.get("use_vwap", True))
    long_bias = all_bull and (vwap_bull if require_vwap else True)
    short_bias = all_bear and (vwap_bear if require_vwap else True)

    # Sweep detection over history
    high = df["high"]
    low = df["low"]
    close = df["close"]
    open_ = df["open"]
    short_sweep = (high > pdh) & (close < pdh)
    long_sweep = (low < pdl) & (close > pdl)

    last_short = short_sweep[short_sweep].index
    last_long = long_sweep[long_sweep].index
    i = len(df) - 1
    short_active = False
    long_active = False
    if len(last_short):
        bars_ago = i - df.index.get_loc(last_short[-1])
        if isinstance(bars_ago, slice):
            bars_ago = 0
        short_active = int(bars_ago) <= sweep_valid
    if len(last_long):
        bars_ago = i - df.index.get_loc(last_long[-1])
        if isinstance(bars_ago, slice):
            bars_ago = 0
        long_active = int(bars_ago) <= sweep_valid

    atr_val = float(df["atr"].iloc[-1])
    if not np.isfinite(atr_val) or atr_val <= 0:
        return None

    h = float(high.iloc[-1])
    l = float(low.iloc[-1])
    c = float(close.iloc[-1])
    o = float(open_.iloc[-1])
    prev_low = float(low.iloc[-2])
    prev_high = float(high.iloc[-2])

    short_retest = (h >= pdh - atr_val * retest_atr) and (h <= pdh + atr_val * retest_atr)
    long_retest = (l <= pdl + atr_val * retest_atr) and (l >= pdl - atr_val * retest_atr)
    short_setup = short_active and short_retest and c < pdh
    long_setup = long_active and long_retest and c > pdl

    sell_now = short_bias and short_setup and c < o and c < prev_low
    buy_now = long_bias and long_setup and c > o and c > prev_high

    # Confidence score (same weights as Pine)
    score = 0
    score += 20 if s1 == 1 else -20 if s1 == -1 else 0
    score += 20 if s2 == 1 else -20 if s2 == -1 else 0
    score += 20 if s3 == 1 else -20 if s3 == -1 else 0
    if use_vwap:
        score += 20 if vwap_bull else -20 if vwap_bear else 0
    if c > float(df["fast"].iloc[-1]) and float(df["fast"].iloc[-1]) > float(df["slow"].iloc[-1]):
        score += 20
    elif c < float(df["fast"].iloc[-1]) and float(df["fast"].iloc[-1]) < float(df["slow"].iloc[-1]):
        score -= 20
    bull_pct = int(round((score + 100) / 2.0))
    bull_pct = max(0, min(100, bull_pct))

    if not buy_now and not sell_now:
        return None

    side = "BUY" if buy_now else "SELL"
    conf = bull_pct if side == "BUY" else (100 - bull_pct)
    if conf < min_conf:
        logger.info("%s signal conf %s < min %s — skip", symbol, conf, min_conf)
        return None

    entry = c
    # Stop beyond sweep extreme / ATR
    if side == "BUY":
        stop = min(pdl, entry - atr_val * stop_atr_mult)
        risk_pts = max(entry - stop, atr_val * 0.5)
        # Prefer dollar target ~$100-200 on 1 contract when point_value known
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry + target_pts
    else:
        stop = max(pdh, entry + atr_val * stop_atr_mult)
        risk_pts = max(stop - entry, atr_val * 0.5)
        target_pts = max(risk_pts * target_r, target_dollars / point_value)
        target = entry - target_pts

    risk_dollars = risk_pts * point_value
    reward_dollars = abs(target - entry) * point_value
    if risk_dollars > max_risk_dollars:
        logger.info(
            "%s risk $%.0f > max $%.0f — skip", symbol, risk_dollars, max_risk_dollars
        )
        return None

    reason = (
        f"{side} sweep-retest "
        f"HTF=({s1},{s2},{s3}) pdh={pdh:.2f} pdl={pdl:.2f}"
    )
    return SweepSignal(
        symbol=symbol,
        side=side,
        entry=float(entry),
        stop=float(stop),
        target=float(target),
        confidence=int(conf),
        reason=reason,
        pdh=pdh,
        pdl=pdl,
        ts=datetime.now(timezone.utc),
        risk_dollars=float(risk_dollars),
        reward_dollars=float(reward_dollars),
    )


class SweepRetestScanner:
    """Fetch bars from broker/yfinance and emit sweep-retest signals."""

    def __init__(self, cfg: dict[str, Any], bar_source):
        self.cfg = cfg
        self.bar_source = bar_source  # callable(symbol) -> DataFrame

    def scan_symbol(self, symbol: str) -> Optional[SweepSignal]:
        instruments = self.cfg.get("instruments", {})
        meta = instruments.get(symbol, {})
        point_value = float(meta.get("point_value", 5.0))
        bars = self.bar_source(symbol)
        return evaluate_sweep_retest(
            symbol, bars, self.cfg, point_value=point_value
        )

    def scan_universe(self) -> list[SweepSignal]:
        symbols = list(self.cfg.get("universe", {}).get("symbols", []))
        out: list[SweepSignal] = []
        for sym in symbols:
            try:
                sig = self.scan_symbol(sym)
                if sig:
                    out.append(sig)
                    logger.info("Signal %s", sig.reason)
            except Exception:
                logger.exception("Sweep scan failed for %s", sym)
        out.sort(key=lambda s: s.confidence, reverse=True)
        return out
