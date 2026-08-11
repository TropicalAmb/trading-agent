"""TradingView MTF Sweep Retest Assistant — 1:1 parity engine.

Source: data/indicator_parity/MTF_Sweep_Retest_Assistant.pine
Strict HTF (all 3 must agree). No soft_htf. No global-score gating.

Base timeline: 1-minute bars preferred; HTF 15m/1h/4h derived with no lookahead
(live HTF candle state = current incomplete bucket open/close as of each bar).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass
class IndicatorParityState:
    timestamp: str
    symbol: str
    dir_15m: int
    dir_1h: int
    dir_4h: int
    ema20: float
    ema50: float
    vwap: float
    pdh: float
    pdl: float
    pullback: bool  # retest setup active (longSetup or shortSetup)
    momentum: bool  # confirmation candle vs prior high/low
    overextended: bool
    long_bias: bool
    short_bias: bool
    long_setup: bool
    short_setup: bool
    buy_now: bool
    sell_now: bool
    action: str
    confidence_pct: int
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    side: str | None = None
    entry_mode: str = "exact"  # exact | pullback | momentum
    atr: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class IndicatorParitySignal:
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
    entry_mode: str = "exact"
    state: dict[str, Any] = field(default_factory=dict)


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


def _session_vwap_pine(df: pd.DataFrame) -> pd.Series:
    """Approximate TradingView ta.vwap(close) with daily reset."""
    # TV vwap typically uses hlc3; Pine here uses ta.vwap(close) → close*volume
    vol = df["volume"].replace(0, np.nan).fillna(1.0) if "volume" in df.columns else pd.Series(1.0, index=df.index)
    px = df["close"].astype(float)
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        days = idx.tz_convert("America/New_York").date
    else:
        days = idx.date
    cum_pv = (px * vol).groupby(days).cumsum()
    cum_v = vol.groupby(days).cumsum()
    return cum_pv / cum_v


def _htf_dir_asof(df: pd.DataFrame, rule: str) -> pd.Series:
    """Live HTF candle direction at each base bar (no future data).

    Matches Pine useLiveHTF=true: current TF open vs current TF close as-of now.
    """
    o = df["open"].resample(rule, label="left", closed="left").first()
    c = df["close"].resample(rule, label="left", closed="left").last()
    # forward-fill onto base index
    o_asof = o.reindex(df.index, method="ffill")
    c_asof = c.reindex(df.index, method="ffill")
    out = pd.Series(0, index=df.index, dtype=int)
    out = out.mask(c_asof > o_asof, 1)
    out = out.mask(c_asof < o_asof, -1)
    return out.fillna(0).astype(int)


def _prior_day_hl(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    daily = df.resample("1D", label="left", closed="left").agg(
        {"high": "max", "low": "min"}
    )
    pdh = daily["high"].shift(1)
    pdl = daily["low"].shift(1)
    return pdh.reindex(df.index, method="ffill"), pdl.reindex(df.index, method="ffill")


def compute_parity_frame(df: pd.DataFrame, cfg: dict[str, Any] | None = None) -> pd.DataFrame:
    """Vectorized indicator state on base bars (1m preferred)."""
    strat = (cfg or {}).get("indicator_parity") or (cfg or {}).get("sweep_retest") or {}
    use_vwap = bool(strat.get("use_vwap", True))
    fast_len = int(strat.get("fast_ema", 20))
    slow_len = int(strat.get("slow_ema", 50))
    retest_atr = float(strat.get("retest_zone_atr", 0.15))
    sweep_valid = int(strat.get("sweep_valid_bars", 240))
    overext_atr = float(strat.get("overext_atr", 1.8))

    work = df.copy()
    work.columns = [str(c).lower() for c in work.columns]
    if "volume" not in work.columns:
        work["volume"] = 1.0
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)

    work["ema20"] = _ema(work["close"], fast_len)
    work["ema50"] = _ema(work["close"], slow_len)
    work["atr"] = _atr(work, 14)
    work["vwap"] = _session_vwap_pine(work)
    work["s15"] = _htf_dir_asof(work, "15min")
    work["s1h"] = _htf_dir_asof(work, "1h")
    work["s4h"] = _htf_dir_asof(work, "4h")
    work["pdh"], work["pdl"] = _prior_day_hl(work)

    # STRICT all-3 HTF (Pine allBullNow / allBearNow) — no soft_htf
    all_bull = (work["s15"] == 1) & (work["s1h"] == 1) & (work["s4h"] == 1)
    all_bear = (work["s15"] == -1) & (work["s1h"] == -1) & (work["s4h"] == -1)
    vwap_bull = work["close"] > work["vwap"]
    vwap_bear = work["close"] < work["vwap"]
    long_bias = all_bull & (vwap_bull if use_vwap else True)
    short_bias = all_bear & (vwap_bear if use_vwap else True)

    short_sweep = (work["high"] > work["pdh"]) & (work["close"] < work["pdh"])
    long_sweep = (work["low"] < work["pdl"]) & (work["close"] > work["pdl"])

    # Sweep validity window in bars (Pine bar_index distance)
    last_short = np.full(len(work), -10**9, dtype=int)
    last_long = np.full(len(work), -10**9, dtype=int)
    ss = short_sweep.to_numpy()
    ls = long_sweep.to_numpy()
    cur_s = cur_l = -10**9
    for i in range(len(work)):
        if ss[i]:
            cur_s = i
        if ls[i]:
            cur_l = i
        last_short[i] = cur_s
        last_long[i] = cur_l
    idx = np.arange(len(work))
    short_active = (idx - last_short) <= sweep_valid
    long_active = (idx - last_long) <= sweep_valid

    atr = work["atr"]
    short_retest = (work["high"] >= work["pdh"] - atr * retest_atr) & (
        work["high"] <= work["pdh"] + atr * retest_atr
    )
    long_retest = (work["low"] <= work["pdl"] + atr * retest_atr) & (
        work["low"] >= work["pdl"] - atr * retest_atr
    )
    short_setup = short_active & short_retest.to_numpy() & (work["close"] < work["pdh"]).to_numpy()
    long_setup = long_active & long_retest.to_numpy() & (work["close"] > work["pdl"]).to_numpy()

    prev_low = work["low"].shift(1)
    prev_high = work["high"].shift(1)
    bull_candle = work["close"] > work["open"]
    bear_candle = work["close"] < work["open"]
    mom_long = bull_candle & (work["close"] > prev_high)
    mom_short = bear_candle & (work["close"] < prev_low)

    buy_exact = long_bias.to_numpy() & long_setup & mom_long.to_numpy()
    sell_exact = short_bias.to_numpy() & short_setup & mom_short.to_numpy()
    # Mode splits (research) — components of the indicator, not new inventions
    buy_pullback = long_bias.to_numpy() & long_setup & bull_candle.to_numpy()
    sell_pullback = short_bias.to_numpy() & short_setup & bear_candle.to_numpy()
    buy_momentum = long_bias.to_numpy() & mom_long.to_numpy()
    sell_momentum = short_bias.to_numpy() & mom_short.to_numpy()

    over_long = (work["close"] - work["ema20"]) > overext_atr * atr
    over_short = (work["ema20"] - work["close"]) > overext_atr * atr

    # Confidence (Pine score)
    score = (
        np.where(work["s15"] == 1, 20, np.where(work["s15"] == -1, -20, 0))
        + np.where(work["s1h"] == 1, 20, np.where(work["s1h"] == -1, -20, 0))
        + np.where(work["s4h"] == 1, 20, np.where(work["s4h"] == -1, -20, 0))
    )
    if use_vwap:
        score = score + np.where(vwap_bull, 20, np.where(vwap_bear, -20, 0))
    ema_bull = (work["close"] > work["ema20"]) & (work["ema20"] > work["ema50"])
    ema_bear = (work["close"] < work["ema20"]) & (work["ema20"] < work["ema50"])
    score = score + np.where(ema_bull, 20, np.where(ema_bear, -20, 0))
    bull_pct = np.clip(np.rint((score + 100) / 2.0), 0, 100).astype(int)

    out = work.copy()
    out["long_bias"] = long_bias
    out["short_bias"] = short_bias
    out["long_setup"] = long_setup
    out["short_setup"] = short_setup
    out["pullback"] = long_setup | short_setup
    out["momentum"] = mom_long | mom_short
    out["overextended"] = over_long | over_short
    out["buy_now"] = buy_exact
    out["sell_now"] = sell_exact
    out["buy_pullback"] = buy_pullback
    out["sell_pullback"] = sell_pullback
    out["buy_momentum"] = buy_momentum
    out["sell_momentum"] = sell_momentum
    out["confidence_pct"] = bull_pct
    out["dir_15m"] = work["s15"]
    out["dir_1h"] = work["s1h"]
    out["dir_4h"] = work["s4h"]
    return out


def _stops_targets(
    side: str,
    entry: float,
    pdh: float,
    pdl: float,
    atr: float,
    *,
    stop_atr_mult: float,
    target_r: float,
) -> tuple[float, float]:
    if side == "BUY":
        stop = min(pdl, entry - atr * stop_atr_mult)
        risk = max(entry - stop, atr * 0.5)
        target = entry + risk * target_r
    else:
        stop = max(pdh, entry + atr * stop_atr_mult)
        risk = max(stop - entry, atr * 0.5)
        target = entry - risk * target_r
    return float(stop), float(target)


def state_at(
    frame: pd.DataFrame,
    i: int,
    *,
    symbol: str,
    entry_mode: str = "exact",
    cfg: dict[str, Any] | None = None,
) -> IndicatorParityState:
    strat = (cfg or {}).get("indicator_parity") or {}
    stop_atr = float(strat.get("stop_atr_mult", 1.0))
    target_r = float(strat.get("target_r_multiple", 2.0))
    row = frame.iloc[i]
    if entry_mode == "pullback":
        buy, sell = bool(row["buy_pullback"]), bool(row["sell_pullback"])
    elif entry_mode == "momentum":
        buy, sell = bool(row["buy_momentum"]), bool(row["sell_momentum"])
    else:
        buy, sell = bool(row["buy_now"]), bool(row["sell_now"])

    action = "Wait"
    if buy:
        action = "Buy Now"
    elif sell:
        action = "Sell Now"
    elif bool(row["long_setup"]):
        action = "Watching Long Retest"
    elif bool(row["short_setup"]):
        action = "Watching Short Retest"
    elif bool(row["long_bias"]):
        action = "Long Bias"
    elif bool(row["short_bias"]):
        action = "Short Bias"

    side = entry = stop = target = None
    if buy or sell:
        side = "BUY" if buy else "SELL"
        entry = float(row["close"])
        atr = float(row["atr"] or 0) or abs(entry) * 0.001
        stop, target = _stops_targets(
            side,
            entry,
            float(row["pdh"]),
            float(row["pdl"]),
            atr,
            stop_atr_mult=stop_atr,
            target_r=target_r,
        )

    return IndicatorParityState(
        timestamp=str(frame.index[i]),
        symbol=symbol,
        dir_15m=int(row["dir_15m"]),
        dir_1h=int(row["dir_1h"]),
        dir_4h=int(row["dir_4h"]),
        ema20=float(row["ema20"]),
        ema50=float(row["ema50"]),
        vwap=float(row["vwap"]),
        pdh=float(row["pdh"]) if pd.notna(row["pdh"]) else float("nan"),
        pdl=float(row["pdl"]) if pd.notna(row["pdl"]) else float("nan"),
        pullback=bool(row["pullback"]),
        momentum=bool(row["momentum"]),
        overextended=bool(row["overextended"]),
        long_bias=bool(row["long_bias"]),
        short_bias=bool(row["short_bias"]),
        long_setup=bool(row["long_setup"]),
        short_setup=bool(row["short_setup"]),
        buy_now=buy,
        sell_now=sell,
        action=action,
        confidence_pct=int(row["confidence_pct"]),
        entry=entry,
        stop=stop,
        target=target,
        side=side,
        entry_mode=entry_mode,
        atr=float(row["atr"] or 0),
    )


def evaluate_indicator_parity(
    symbol: str,
    bars: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    point_value: float = 5.0,
    entry_mode: str = "exact",
) -> Optional[IndicatorParitySignal]:
    strat = cfg.get("indicator_parity") or {}
    if not bool(strat.get("enabled", True)):
        return None
    if bars is None or len(bars) < 100:
        return None
    mode = str(strat.get("entry_mode") or entry_mode)
    frame = compute_parity_frame(bars, cfg)
    st = state_at(frame, len(frame) - 1, symbol=symbol, entry_mode=mode, cfg=cfg)
    if not st.buy_now and not st.sell_now:
        return None
    if st.entry is None or st.stop is None or st.target is None or st.side is None:
        return None
    # Indicator itself has no min_confidence gate in Pine for markers — keep optional
    min_conf = int(strat.get("min_confidence", 0))
    conf = st.confidence_pct if st.side == "BUY" else (100 - st.confidence_pct)
    if conf < min_conf:
        return None
    risk_d = abs(st.entry - st.stop) * point_value
    reward_d = abs(st.target - st.entry) * point_value
    max_risk = float(strat.get("max_risk_dollars", 0) or 0)
    if max_risk > 0 and risk_d > max_risk:
        return None
    ts = bars.index[-1].to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return IndicatorParitySignal(
        symbol=symbol.upper(),
        side=st.side,
        entry=st.entry,
        stop=st.stop,
        target=st.target,
        confidence=int(conf),
        reason=f"indicator_parity:{mode}:{st.action}",
        ts=ts,
        risk_dollars=risk_d,
        reward_dollars=reward_d,
        level=st.pdl if st.side == "BUY" else st.pdh,
        entry_mode=mode,
        state={
            "dir_15m": st.dir_15m,
            "dir_1h": st.dir_1h,
            "dir_4h": st.dir_4h,
            "pullback": st.pullback,
            "momentum": st.momentum,
            "overextended": st.overextended,
            "action": st.action,
            "confidence_pct": st.confidence_pct,
        },
    )
