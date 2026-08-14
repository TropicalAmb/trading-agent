"""Leak-aware discovery harness for externally sourced futures strategy families.

This module is deliberately separate from the paper decision pipeline.  It turns a
small, pre-declared set of public strategy hypotheses into point-in-time signals,
replays the configured two-contract lifecycle on audited one-minute bars, selects
one variant per family using validation data, and opens the final chronological
holdout only after selection.

The goal is not to brute-force a 70% print.  The goal is to determine whether a
70% win rate survives friction, realistic stops, scale-out management, chronology,
and multiple-strategy selection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import comb, sqrt
from pathlib import Path
from typing import Any, Callable, Iterable
import json
import weakref

import numpy as np
import pandas as pd

from agent.research.current_specialist_validation import _verified_continuous_cache
from agent.research.harness.datasets import fetch_yahoo
from agent.research.harness.metrics import trade_stats


SOURCE_CATALOG: dict[str, dict[str, str]] = {
    "vwap_reversion": {
        "kind": "Reddit hypothesis",
        "title": "The VWAP mean reversion is my new jam",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1pladiq/the_vwap_mean_reversion_is_my_new_jam/",
    },
    "atr_rsi_reversion": {
        "kind": "Reddit hypothesis",
        "title": "Best Mean Reversion metric to base on?",
        "url": "https://www.reddit.com/r/algotrading/comments/1spr49z/best_mean_reversion_metric_to_base_on/",
    },
    "capitulation": {
        "kind": "Reddit hypothesis",
        "title": "Backtested Intraday Mean Reversion",
        "url": "https://www.reddit.com/r/algotrading/comments/1sm6y5g/backtested_intraday_mean_reversion/",
    },
    "intraday_momentum": {
        "kind": "Primary technical research",
        "title": "Market Intraday Momentum",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866",
    },
    "session_range": {
        "kind": "Reddit hypothesis",
        "title": "NY takes out London's high or low 70%+ of the time",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1kns6vk/ny_takes_out_londons_high_or_low_70_of_the_time/",
    },
    "initial_balance": {
        "kind": "Reddit hypothesis",
        "title": "Initial balance strategy",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1uto3kr/initial_balance_strategy/",
    },
    "donchian": {
        "kind": "Reddit hypothesis",
        "title": "Stairway to Heaven: a trend-following breakout system on gold",
        "url": "https://www.reddit.com/r/algotrading/comments/1unk44b/stairway_to_heaven_a_trendfollowing_breakout/",
    },
    "time_series_momentum": {
        "kind": "Primary technical research",
        "title": "Time Series Momentum",
        "url": "https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf",
    },
    "validation": {
        "kind": "Primary technical research",
        "title": "How Backtest Overfitting in Finance Leads to False Discoveries",
        "url": "https://escholarship.org/uc/item/9tq3327h",
    },
    "regime_selector": {
        "kind": "Reddit implementation hypothesis",
        "title": "It's finally working!",
        "url": "https://www.reddit.com/r/algotrading/comments/1tv8m1z/its_finally_working/",
    },
    "volume_profile_balance": {
        "kind": "Reddit implementation hypothesis",
        "title": "Balanced-market value area plus failed continuation",
        "url": "https://www.reddit.com/r/algotrading/comments/1spr49z/best_mean_reversion_metric_to_base_on/",
    },
    "daily_ibs_reversion": {
        "kind": "Reddit strategy hypothesis",
        "title": "Simple mean reversion setup with a reported 70% win rate",
        "url": "https://www.reddit.com/r/algotrading/comments/1rjvxjy/found_a_simple_mean_reversion_setup_with_70_win/",
    },
    "nq_first_pullback": {
        "kind": "Reddit strategy hypothesis",
        "title": "NQ strategy backtest: opening trend and first pullback",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1b2gi87/nq_strategy_backtest/",
    },
    "vwap_rejection": {
        "kind": "Reddit strategy hypothesis",
        "title": "Full MNQ and NQ VWAP strategy",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1kca8nt/full_mnq_and_nq_vwap_strategy/",
    },
    "nq_intraday_conditional": {
        "kind": "Primary technical research",
        "title": "Nasdaq-100 Index Futures: Intraday Momentum or Reversal?",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=712168",
    },
    "value_area_breakout": {
        "kind": "Primary technical research",
        "title": "Stop Distance, Exit Methodology, and Signal Preservation in Intraday Value Area Breakouts",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6350238",
    },
    "weekly_failed_auction": {
        "kind": "Primary technical research",
        "title": "Pre-Registered Tests of Failed Weekly Auction Reversion in Liquid Futures Markets",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6728359",
    },
    "opening_range_research": {
        "kind": "Primary technical research",
        "title": "An Investigation of Simple Intraday Trading Strategies",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2488539",
    },
    "value_area_80_rule": {
        "kind": "Public market-profile rule",
        "title": "Value Area Trading and the 80% Rule",
        "url": "https://traderprofesional.com/en/value-area-trading/",
    },
    "ny_open_three_bar": {
        "kind": "Reddit strategy hypothesis",
        "title": "Here's my strategy: first-40-minute drive, pause, continuation",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1eui37q/heres_my_strategy/",
    },
    "nq_15m_orb": {
        "kind": "Reddit strategy hypothesis",
        "title": "15 minute opening range break strategy",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1joy48s/15_minute_opening_range_break_strategy/",
    },
    "premarket_ema_pullback": {
        "kind": "Reddit strategy hypothesis",
        "title": "Beginner friendly 9/20 EMA trend pullback",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1kh3081/beginner_friendly_strategy/",
    },
    "opening_shock_reversal": {
        "kind": "Primary technical research",
        "title": "Intraday Price Reversals in the US Stock Index Futures Market: A 15-Year Study",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=689282",
    },
    "post_settlement_gap": {
        "kind": "Primary technical research",
        "title": "The Invisible Segment of the Night Market: Predicting the Opening Gap Based on Post-Settlement Distortions",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6743758",
    },
    "gap_regime": {
        "kind": "Reddit strategy hypothesis",
        "title": "Gap and Fill versus Gap and Go in index futures",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1tdz9zt/ive_become_fixated_on_gap_trades_any_advice_on/",
    },
    "initial_balance_vwap": {
        "kind": "Reddit strategy hypothesis",
        "title": "Initial balance, current-day volume-profile levels, and VWAP after the first hour",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1uto3kr/initial_balance_strategy/",
    },
    "tested_level_break": {
        "kind": "Reddit strategy hypothesis",
        "title": "Support/resistance tested repeatedly before a confirmed break",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1joy48s/15_minute_opening_range_break_strategy/",
    },
    "volume_rejection": {
        "kind": "Reddit implementation hypothesis",
        "title": "Price action and volume analysis on completed NQ bars",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1vll43k/what_timeframe_do_you_trade_for_nqmnq/",
    },
    "bulk_volume_classification": {
        "kind": "Primary technical research",
        "title": "Discerning information from trade data",
        "url": "https://opus.lib.uts.edu.au/handle/10453/121971",
    },
    "order_flow_price_impact": {
        "kind": "Primary technical research",
        "title": "The Price Impact of Order Book Events",
        "url": "https://arxiv.org/abs/1011.6402",
    },
    "vpin_futures": {
        "kind": "Primary technical research",
        "title": "Volume-Synchronised Probability of Informed Trading on Chinese Index Futures",
        "url": "https://link.springer.com/article/10.7603/s40570-016-0005-6",
    },
    "cvd_absorption": {
        "kind": "Reddit implementation hypothesis",
        "title": "Scalping NQ using CVD divergence and absorption at POC",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1g5m4we/scalping_nq_on_the_30s_using_cvd/",
    },
    "order_flow_practice": {
        "kind": "Reddit implementation hypothesis",
        "title": "Footprint absorption, stacked imbalance, CVD divergence, and volume profile",
        "url": "https://www.reddit.com/r/FuturesTrading/comments/1t6j6gi/should_i_use_order_flow/",
    },
}

FAMILY_SOURCE: dict[str, str] = {
    "vwap_band_reentry": "vwap_reversion",
    "atr_rsi_failure_reversion": "atr_rsi_reversion",
    "intraday_capitulation_reversal": "capitulation",
    "intraday_open_to_close_momentum": "intraday_momentum",
    "london_range_sweep_reversal": "session_range",
    "initial_balance_failed_break": "initial_balance",
    "trend_capitulation_reclaim": "capitulation",
    "opening_drive_pullback": "regime_selector",
    "overnight_gap_reversion": "atr_rsi_reversion",
    "volatility_compression_breakout": "time_series_momentum",
    "donchian_trend_breakout": "donchian",
    "balanced_value_area_reversion": "volume_profile_balance",
    "daily_ibs_capitulation_reversion": "daily_ibs_reversion",
    "prior_day_level_failure": "nq_first_pullback",
    "opening_range_retest_continuation": "opening_range_research",
    "opening_range_midpoint_continuation": "nq_first_pullback",
    "conditional_overnight_reversal": "nq_intraday_conditional",
    "value_area_breakout_continuation": "value_area_breakout",
    "overnight_range_break_retest": "nq_first_pullback",
    "session_extreme_two_bar_reversal": "vwap_rejection",
    "weekly_value_area_failed_auction": "weekly_failed_auction",
    "value_area_80_rule_rotation": "value_area_80_rule",
    "ny_open_three_bar_continuation": "ny_open_three_bar",
    "nq_15m_opening_range_retest": "nq_15m_orb",
    "nq_premarket_ema_engulfing": "premarket_ema_pullback",
    "nq_opening_shock_reversal": "opening_shock_reversal",
    "gap_reject_then_go": "gap_regime",
    "initial_balance_vwap_retest": "initial_balance_vwap",
    "volume_climax_rejection": "volume_rejection",
    "lunch_vwap_reclaim": "vwap_reversion",
    "two_test_range_breakout": "tested_level_break",
    "nq_post_settlement_alignment": "post_settlement_gap",
    "bvc_cvd_divergence": "cvd_absorption",
    "bvc_absorption_reversal": "bulk_volume_classification",
    "bvc_pressure_breakout": "order_flow_price_impact",
    "vpin_failed_extension": "vpin_futures",
    "impact_shock_reversal": "order_flow_practice",
}


@dataclass(frozen=True)
class SplitLock:
    development_end: str
    validation_end: str
    holdout_start: str
    n_days_development: int
    n_days_validation: int
    n_days_holdout: int


@dataclass(frozen=True)
class Candidate:
    family: str
    variant: str
    source_id: str
    symbol: str
    side: str
    signal_ts: str
    entry_ts: str
    entry: float
    stop: float
    target_r: float = 1.5
    forced_exit_ts: str | None = None
    notes: str = ""


Generator = Callable[[pd.DataFrame, pd.DataFrame, str, dict[str, Any]], list[Candidate]]


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - pc).abs(),
            (df["low"] - pc).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def _rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def _resample_complete(
    df: pd.DataFrame,
    rule: str,
    minimum_fraction: float = 0.80,
    *,
    base_minutes: int = 1,
) -> pd.DataFrame:
    minutes = int(pd.Timedelta(rule).total_seconds() // 60)
    counts = df["close"].resample(rule, label="left", closed="left").count()
    bars = df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    need = max(1, int(np.ceil((minutes / max(1, base_minutes)) * minimum_fraction)))
    return bars.loc[counts >= need].dropna(subset=["open", "high", "low", "close"])


def _trade_day(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """CME trade date: the session beginning 18:00 ET belongs to the next date."""
    return (index + pd.Timedelta(hours=6)).normalize()


def freeze_split_lock(df_1m: pd.DataFrame) -> SplitLock:
    days = list(pd.DatetimeIndex(_trade_day(df_1m.index)).unique().sort_values())
    if len(days) < 20:
        raise ValueError("At least 20 CME trade dates are required")
    n_dev = max(10, int(len(days) * 0.50))
    n_val = max(5, int(len(days) * 0.25))
    if n_dev + n_val >= len(days):
        n_val = max(3, len(days) - n_dev - 3)
    hold = days[n_dev + n_val :]
    if not hold:
        raise ValueError("Chronological holdout is empty")
    return SplitLock(
        development_end=str(days[n_dev - 1]),
        validation_end=str(days[n_dev + n_val - 1]),
        holdout_start=str(hold[0]),
        n_days_development=n_dev,
        n_days_validation=n_val,
        n_days_holdout=len(hold),
    )


def period_for(ts: str | pd.Timestamp, split: SplitLock) -> str:
    day = pd.Timestamp(ts)
    if day.tzinfo is None:
        day = day.tz_localize("America/New_York")
    else:
        day = day.tz_convert("America/New_York")
    day = (day + pd.Timedelta(hours=6)).normalize()
    if day <= pd.Timestamp(split.development_end):
        return "development"
    if day <= pd.Timestamp(split.validation_end):
        return "validation"
    return "holdout"


def _entry_after(
    bars_1m: pd.DataFrame,
    signal_ts: pd.Timestamp,
    signal_minutes: int,
) -> tuple[pd.Timestamp, float] | None:
    ready = signal_ts + pd.Timedelta(minutes=signal_minutes)
    pos = int(bars_1m.index.searchsorted(ready, side="left"))
    if pos >= len(bars_1m):
        return None
    return pd.Timestamp(bars_1m.index[pos]), float(bars_1m["open"].iloc[pos])


def _candidate(
    *,
    bars_1m: pd.DataFrame,
    signal_ts: pd.Timestamp,
    signal_minutes: int,
    family: str,
    variant: str,
    source_id: str,
    symbol: str,
    side: str,
    stop: float,
    target_r: float,
    forced_exit_ts: pd.Timestamp | None = None,
    notes: str = "",
) -> Candidate | None:
    nxt = _entry_after(bars_1m, signal_ts, signal_minutes)
    if nxt is None:
        return None
    entry_ts, entry = nxt
    side = side.upper()
    if side == "BUY" and stop >= entry:
        return None
    if side == "SELL" and stop <= entry:
        return None
    return Candidate(
        family=family,
        variant=variant,
        source_id=source_id,
        symbol=symbol,
        side=side,
        signal_ts=str(signal_ts),
        entry_ts=str(entry_ts),
        entry=entry,
        stop=float(stop),
        target_r=float(target_r),
        forced_exit_ts=str(forced_exit_ts) if forced_exit_ts is not None else None,
        notes=notes,
    )


def _session_vwap_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    groups = pd.Series(_trade_day(out.index), index=out.index)
    typical = (out["high"] + out["low"] + out["close"]) / 3.0
    volume = out["volume"].clip(lower=0).replace(0, 1.0)
    cum_v = volume.groupby(groups).cumsum()
    cum_pv = (typical * volume).groupby(groups).cumsum()
    cum_p2v = ((typical**2) * volume).groupby(groups).cumsum()
    out["vwap"] = cum_pv / cum_v
    variance = (cum_p2v / cum_v - out["vwap"] ** 2).clip(lower=0)
    out["vwap_std"] = np.sqrt(variance).replace(0, np.nan)
    out["vwap_z"] = (out["close"] - out["vwap"]) / out["vwap_std"]
    out["atr"] = _atr(out)
    out["rsi5"] = _rsi(out["close"], 5)
    out["atr_fast"] = _atr(out, 5)
    out["atr_slow"] = _atr(out, 50)
    return out


_MICRO_PROXY_CACHE: dict[
    int, tuple[weakref.ReferenceType[pd.DataFrame], pd.DataFrame]
] = {}


def _microstructure_proxy_5m(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """Build completed-bar BVC/VPIN-style proxies from one-minute OHLCV.

    These fields are deliberately named proxies. OHLCV cannot reconstruct true
    bid/ask delta, cancellations, queue imbalance, or order-book depth. The
    completed one-minute price change is classified with a prior-only volatility
    estimate, then aggregated into completed five-minute decision bars.
    """
    cache_key = id(bars_1m)
    cached = _MICRO_PROXY_CACHE.get(cache_key)
    if cached is not None and cached[0]() is bars_1m:
        return cached[1]

    from scipy.special import ndtr

    raw = bars_1m[["open", "high", "low", "close", "volume"]].copy().sort_index()
    if len(raw.index) >= 3:
        median_minutes = float(
            pd.Series(raw.index[1:] - raw.index[:-1]).median().total_seconds() / 60.0
        )
    else:
        median_minutes = 1.0
    base_is_five_minute = median_minutes >= 4.0
    sigma_lookback = 24 if base_is_five_minute else 120
    sigma_minimum = 12 if base_is_five_minute else 60
    change = raw["close"].diff()
    prior_sigma = (
        change.shift(1)
        .rolling(sigma_lookback, min_periods=sigma_minimum)
        .std(ddof=0)
        .replace(0, np.nan)
    )
    standardized = (change / prior_sigma).clip(-6.0, 6.0)
    signed_fraction = pd.Series(2.0 * ndtr(standardized.to_numpy()) - 1.0, index=raw.index)
    raw["signed_volume_proxy"] = raw["volume"].clip(lower=0) * signed_fraction.fillna(0.0)
    raw["absolute_signed_volume_proxy"] = raw["signed_volume_proxy"].abs()

    if base_is_five_minute:
        agg = raw.dropna(subset=["open", "high", "low", "close"])
    else:
        counts = raw["close"].resample("5min", label="left", closed="left").count()
        agg = raw.resample("5min", label="left", closed="left").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "signed_volume_proxy": "sum",
                "absolute_signed_volume_proxy": "sum",
            }
        )
        agg = agg.loc[counts >= 4].dropna(subset=["open", "high", "low", "close"])
    f = _session_vwap_features(agg)
    volume = f["volume"].replace(0, np.nan)
    f["signed_pressure_proxy"] = f["signed_volume_proxy"] / volume
    pressure_mean = f["signed_pressure_proxy"].shift(1).rolling(100, min_periods=50).mean()
    pressure_std = (
        f["signed_pressure_proxy"].shift(1).rolling(100, min_periods=50).std(ddof=0).replace(0, np.nan)
    )
    f["pressure_z_proxy"] = (f["signed_pressure_proxy"] - pressure_mean) / pressure_std
    volume_mean = f["volume"].shift(1).rolling(100, min_periods=50).mean()
    volume_std = f["volume"].shift(1).rolling(100, min_periods=50).std(ddof=0).replace(0, np.nan)
    f["volume_z_proxy"] = (f["volume"] - volume_mean) / volume_std
    range_ = (f["high"] - f["low"]).replace(0, np.nan)
    f["efficiency_proxy"] = (f["close"] - f["open"]).abs() / range_
    f["close_location_proxy"] = (f["close"] - f["low"]) / range_
    f["range_atr_proxy"] = range_ / f["atr"].replace(0, np.nan)
    f["vwap_distance_atr_proxy"] = (f["close"] - f["vwap"]) / f["atr"].replace(0, np.nan)
    flow_volume = f["volume"].rolling(6, min_periods=6).sum().replace(0, np.nan)
    f["flow6_proxy"] = f["signed_volume_proxy"].rolling(6, min_periods=6).sum() / flow_volume
    f["price6_atr_proxy"] = (f["close"] - f["close"].shift(6)) / f["atr"].replace(0, np.nan)
    toxicity_volume = f["volume"].rolling(12, min_periods=12).sum().replace(0, np.nan)
    f["toxicity_proxy"] = (
        f["absolute_signed_volume_proxy"].rolling(12, min_periods=12).sum()
        / toxicity_volume
    )
    f["toxicity_q90_proxy"] = (
        f["toxicity_proxy"].shift(1).rolling(500, min_periods=200).quantile(0.90)
    )
    relative_volume = f["volume"] / volume_mean.replace(0, np.nan)
    raw_impact = f["range_atr_proxy"] / relative_volume.replace(0, np.nan)
    impact_mean = raw_impact.shift(1).rolling(100, min_periods=50).mean()
    impact_std = raw_impact.shift(1).rolling(100, min_periods=50).std(ddof=0).replace(0, np.nan)
    f["impact_z_proxy"] = (raw_impact - impact_mean) / impact_std
    f["prior_high12_proxy"] = f["high"].shift(1).rolling(12, min_periods=12).max()
    f["prior_low12_proxy"] = f["low"].shift(1).rolling(12, min_periods=12).min()

    def _drop_cache(_reference: weakref.ReferenceType[pd.DataFrame], key: int = cache_key) -> None:
        _MICRO_PROXY_CACHE.pop(key, None)

    _MICRO_PROXY_CACHE[cache_key] = (weakref.ref(bars_1m, _drop_cache), f)
    return f


def _micro_session_mask(frame: pd.DataFrame, symbol: str) -> pd.Series:
    minutes = frame.index.hour * 60 + frame.index.minute
    end_minute = 13 * 60 if symbol == "CL" else 15 * 60
    return pd.Series((minutes >= 10 * 60) & (minutes <= end_minute), index=frame.index)


def generate_vwap_band_reentry(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    f = _session_vwap_features(bars_5m)
    z_extreme = float(spec["z_extreme"])
    reentry_z = float(spec["reentry_z"])
    slope_atr = float(spec["slope_atr"])
    out: list[Candidate] = []
    for i in range(8, len(f)):
        ts = pd.Timestamp(f.index[i])
        minute = ts.hour * 60 + ts.minute
        end_minute = 13 * 60 + 30 if symbol == "CL" else 15 * 60 + 15
        if minute < 10 * 60 + 30 or minute > end_minute:
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        std = float(row["vwap_std"])
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(std) or std <= 0:
            continue
        slope = abs(float(row["vwap"] - f["vwap"].iloc[i - 6])) / atr
        if slope > slope_atr:
            continue
        recent_z = pd.to_numeric(f["vwap_z"].iloc[max(0, i - 6) : i], errors="coerce")
        open_z = (float(row["open"]) - float(row["vwap"])) / std
        close_z = float(row["vwap_z"])
        side: str | None = None
        if float(recent_z.min()) <= -z_extreme and -reentry_z <= open_z <= 0 and -reentry_z <= close_z <= 0:
            if float(row["close"]) > float(row["open"]):
                side = "BUY"
                stop = float(min(f["low"].iloc[i - 2 : i + 1])) - 0.10 * atr
        elif float(recent_z.max()) >= z_extreme and 0 <= open_z <= reentry_z and 0 <= close_z <= reentry_z:
            if float(row["close"]) < float(row["open"]):
                side = "SELL"
                stop = float(max(f["high"].iloc[i - 2 : i + 1])) + 0.10 * atr
        else:
            continue
        if side is None:
            continue
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="vwap_band_reentry",
            variant=str(spec["id"]),
            source_id="vwap_reversion",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.5,
            notes="ETH-session VWAP deviation stretch, completed-bar re-entry, flat-VWAP gate",
        )
        if cand:
            out.append(cand)
    return out


def generate_atr_rsi_failure(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    f = _session_vwap_features(bars_5m)
    stretch = float(spec["stretch_atr"])
    out: list[Candidate] = []
    for i in range(3, len(f)):
        ts = pd.Timestamp(f.index[i])
        minute = ts.hour * 60 + ts.minute
        end_minute = 13 * 60 + 30 if symbol == "CL" else 15 * 60 + 30
        if minute < 9 * 60 + 50 or minute > end_minute:
            continue
        row, prev = f.iloc[i], f.iloc[i - 1]
        atr = float(row["atr"])
        slow = float(row["atr_slow"])
        fast = float(row["atr_fast"])
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(slow) or slow <= 0:
            continue
        if fast / slow > 1.5:
            continue
        prev_dist = (float(prev["close"]) - float(prev["vwap"])) / atr
        side: str | None = None
        if prev_dist <= -stretch and float(prev["rsi5"]) <= 28:
            if float(row["close"]) > float(prev["close"]) and float(row["close"]) > float(row["open"]):
                side = "BUY"
                stop = float(min(f["low"].iloc[i - 2 : i + 1])) - 0.15 * atr
        elif prev_dist >= stretch and float(prev["rsi5"]) >= 72:
            if float(row["close"]) < float(prev["close"]) and float(row["close"]) < float(row["open"]):
                side = "SELL"
                stop = float(max(f["high"].iloc[i - 2 : i + 1])) + 0.15 * atr
        else:
            continue
        if side is None:
            continue
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="atr_rsi_failure_reversion",
            variant=str(spec["id"]),
            source_id="atr_rsi_reversion",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.5,
            notes="ATR-normalized VWAP stretch plus RSI and failed-continuation trigger",
        )
        if cand:
            out.append(cand)
    return out


def generate_capitulation_reversal(
    bars_1m: pd.DataFrame,
    bars_15m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    if symbol != "NQ":
        return []
    f = bars_15m.copy()
    f["atr"] = _atr(f)
    f["ema20"] = f["close"].ewm(span=20, adjust=False).mean()
    f["ema50"] = f["close"].ewm(span=50, adjust=False).mean()
    f["rsi2"] = _rsi(f["close"], 2)
    mean20 = f["close"].rolling(20).mean()
    std20 = f["close"].rolling(20).std(ddof=0)
    f["lower"] = mean20 - float(spec["band_std"]) * std20
    f["ibs"] = (f["close"] - f["low"]) / (f["high"] - f["low"]).replace(0, np.nan)
    out: list[Candidate] = []
    used_days: set[pd.Timestamp] = set()
    for i in range(55, len(f)):
        ts = pd.Timestamp(f.index[i])
        minute = ts.hour * 60 + ts.minute
        if minute < 9 * 60 + 45 or minute > 14 * 60 + 45:
            continue
        day = ts.normalize()
        if day in used_days:
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0:
            continue
        uptrend = float(row["ema20"]) > float(row["ema50"]) and float(row["ema50"]) > float(f["ema50"].iloc[i - 4])
        capitulation = (
            float(row["close"]) < float(row["lower"])
            and float(row["ibs"]) < 0.25
            and float(row["rsi2"]) < 8.0
            and float(row["open"] - row["close"]) > 0.8 * atr
        )
        if not (uptrend and capitulation):
            continue
        nxt = _entry_after(bars_1m, ts, 15)
        if nxt is None:
            continue
        _entry_ts, entry = nxt
        stop = entry * (1.0 - 0.003)
        forced = ts.normalize() + pd.Timedelta(hours=16)
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=15,
            family="intraday_capitulation_reversal",
            variant=str(spec["id"]),
            source_id="capitulation",
            symbol=symbol,
            side="BUY",
            stop=stop,
            target_r=2.5,
            forced_exit_ts=forced,
            notes="Long-only RTH completed 15m capitulation in a rising trend; 0.30% stop; EOD flat",
        )
        if cand:
            out.append(cand)
            used_days.add(day)
    return out


def generate_trend_capitulation_reclaim(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Completed 5m capitulation followed by a separate structure-reclaim bar."""
    f = _session_vwap_features(bars_5m)
    f["ema20"] = f["close"].ewm(span=20, adjust=False).mean()
    f["ema50"] = f["close"].ewm(span=50, adjust=False).mean()
    f["rsi2"] = _rsi(f["close"], 2)
    mean20 = f["close"].rolling(20).mean()
    std20 = f["close"].rolling(20).std(ddof=0)
    f["upper"] = mean20 + float(spec["band_std"]) * std20
    f["lower"] = mean20 - float(spec["band_std"]) * std20
    f["ibs"] = (f["close"] - f["low"]) / (f["high"] - f["low"]).replace(0, np.nan)
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in range(55, len(f)):
        ts = pd.Timestamp(f.index[i])
        minute = ts.hour * 60 + ts.minute
        end_minute = 13 * 60 + 15 if symbol == "CL" else 15 * 60
        if minute < 10 * 60 or minute > end_minute:
            continue
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=2):
            continue
        row, prior = f.iloc[i], f.iloc[i - 1]
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0:
            continue
        trend_up = float(prior["ema20"]) > float(prior["ema50"]) and float(prior["ema50"]) > float(f["ema50"].iloc[i - 7])
        trend_down = float(prior["ema20"]) < float(prior["ema50"]) and float(prior["ema50"]) < float(f["ema50"].iloc[i - 7])
        side: str | None = None
        long_flush = float(prior["close"]) < float(prior["lower"]) and float(prior["ibs"]) < 0.25 and float(prior["rsi2"]) < 10
        short_flush = float(prior["close"]) > float(prior["upper"]) and float(prior["ibs"]) > 0.75 and float(prior["rsi2"]) > 90
        if trend_up and long_flush and float(row["close"]) > float(prior["high"]) and float(row["close"]) > float(row["open"]):
            side = "BUY"
            stop = float(min(prior["low"], row["low"])) - 0.10 * atr
        elif trend_down and short_flush and float(row["close"]) < float(prior["low"]) and float(row["close"]) < float(row["open"]):
            side = "SELL"
            stop = float(max(prior["high"], row["high"])) + 0.10 * atr
        if side is None:
            continue
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="trend_capitulation_reclaim",
            variant=str(spec["id"]),
            source_id="capitulation",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.5,
            notes="5m volatility-band capitulation in established trend, then separate-bar structural reclaim",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_opening_drive_pullback(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Trade the first completed VWAP pullback after a directional opening drive."""
    f = _session_vwap_features(bars_5m)
    f["ema20"] = f["close"].ewm(span=20, adjust=False).mean()
    f["ema50"] = f["close"].ewm(span=50, adjust=False).mean()
    open_h, open_m = (9, 0) if symbol == "CL" else (9, 30)
    out: list[Candidate] = []
    for day, d in f.groupby(f.index.normalize()):
        opening_start = day + pd.Timedelta(hours=open_h, minutes=open_m)
        opening_end = opening_start + pd.Timedelta(minutes=30)
        opening = d[(d.index >= opening_start) & (d.index < opening_end)]
        search_end = day + pd.Timedelta(hours=12 if symbol == "NQ" else 13)
        post = d[(d.index >= opening_end) & (d.index < search_end)]
        if len(opening) < 5 or post.empty:
            continue
        impulse = float(opening["close"].iloc[-1] - opening["open"].iloc[0])
        atr = float(opening["atr"].iloc[-1])
        if not np.isfinite(atr) or atr <= 0 or abs(impulse) < float(spec["impulse_atr"]) * atr:
            continue
        side = "BUY" if impulse > 0 else "SELL"
        for ts, row in post.iterrows():
            row_atr = float(row["atr"])
            if not np.isfinite(row_atr) or row_atr <= 0:
                continue
            near_vwap = abs(float(row["low" if side == "BUY" else "high"]) - float(row["vwap"])) <= 0.30 * row_atr
            if side == "BUY":
                confirms = (
                    near_vwap
                    and float(row["close"]) > float(row["vwap"])
                    and float(row["close"]) > float(row["open"])
                    and float(row["ema20"]) > float(row["ema50"])
                )
                stop = float(row["low"]) - 0.15 * row_atr
            else:
                confirms = (
                    near_vwap
                    and float(row["close"]) < float(row["vwap"])
                    and float(row["close"]) < float(row["open"])
                    and float(row["ema20"]) < float(row["ema50"])
                )
                stop = float(row["high"]) + 0.15 * row_atr
            if not confirms:
                continue
            cand = _candidate(
                bars_1m=bars_1m,
                signal_ts=pd.Timestamp(ts),
                signal_minutes=5,
                family="opening_drive_pullback",
                variant=str(spec["id"]),
                source_id="regime_selector",
                symbol=symbol,
                side=side,
                stop=stop,
                target_r=1.5,
                notes="Session-specific opening impulse followed by first completed VWAP pullback and trend-aligned reclaim",
            )
            if cand:
                out.append(cand)
            break
    return out


def generate_balanced_value_area_reversion(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade a failed value-area/IB edge only in a demonstrably balanced regime.

    The public idea uses rolling volume-profile value area and order-flow
    absorption. Our paid OHLCV bars do not expose aggressor-side delta, so a
    completed break-and-close-back-inside is the predeclared price-based
    absorption proxy. No unfinished bar or future profile data is used.
    """
    f = _session_vwap_features(bars_5m)
    open_h, open_m = (9, 0) if symbol == "CL" else (9, 30)
    forced_h = 14 if symbol == "CL" else 16
    rth_by_day: dict[pd.Timestamp, pd.DataFrame] = {}
    for day, day_frame in f.groupby(f.index.normalize()):
        rth = day_frame[
            (day_frame.index >= day + pd.Timedelta(hours=open_h, minutes=open_m))
            & (day_frame.index < day + pd.Timedelta(hours=forced_h))
        ]
        if len(rth) >= 50:
            rth_by_day[pd.Timestamp(day)] = rth
    days = sorted(rth_by_day)
    lookback = int(spec["lookback_days"])
    out: list[Candidate] = []
    for day_index in range(lookback, len(days)):
        day = days[day_index]
        history_days = days[day_index - lookback : day_index]
        history = pd.concat([rth_by_day[d] for d in history_days])
        current = rth_by_day[day]
        closes = pd.to_numeric(history["close"], errors="coerce")
        path = float(closes.diff().abs().sum())
        efficiency = abs(float(closes.iloc[-1] - closes.iloc[0])) / path if path > 0 else 1.0
        day_highs = [float(rth_by_day[d]["high"].max()) for d in history_days]
        day_lows = [float(rth_by_day[d]["low"].min()) for d in history_days]
        union = max(day_highs) - min(day_lows)
        overlap = max(0.0, min(day_highs) - max(day_lows)) / union if union > 0 else 0.0
        if efficiency > float(spec["max_efficiency"]) or overlap < float(spec["min_overlap"]):
            continue

        typical = (history["high"] + history["low"] + history["close"]) / 3.0
        weights = history["volume"].clip(lower=0).replace(0, 1.0)
        profile_mean = float((typical * weights).sum() / weights.sum())
        profile_variance = float((((typical - profile_mean) ** 2) * weights).sum() / weights.sum())
        profile_std = sqrt(max(0.0, profile_variance))
        if not np.isfinite(profile_std) or profile_std <= 0:
            continue
        value_high = profile_mean + profile_std
        value_low = profile_mean - profile_std

        ib_end = day + pd.Timedelta(hours=open_h + 1, minutes=open_m)
        initial_balance = current[current.index < ib_end]
        search = current[
            (current.index >= ib_end)
            & (current.index < day + pd.Timedelta(hours=forced_h - 1))
        ]
        if len(initial_balance) < 10 or search.empty:
            continue
        ib_high = float(initial_balance["high"].max())
        ib_low = float(initial_balance["low"].min())
        atr = float(initial_balance["atr"].iloc[-1])
        if not np.isfinite(atr) or atr <= 0:
            continue
        proximity = float(spec["profile_proximity_atr"]) * atr
        upper_aligned = abs(ib_high - value_high) <= proximity
        lower_aligned = abs(ib_low - value_low) <= proximity
        if not (upper_aligned or lower_aligned):
            continue
        upper = max(ib_high, value_high)
        lower = min(ib_low, value_low)

        for ts, row in search.iterrows():
            row_atr = float(row["atr"])
            if not np.isfinite(row_atr) or row_atr <= 0:
                continue
            location = int(f.index.get_loc(ts))
            if location < 6:
                continue
            vwap_slope = abs(float(row["vwap"] - f["vwap"].iloc[location - 6])) / row_atr
            if vwap_slope > float(spec["max_vwap_slope_atr"]):
                continue
            pierce = float(spec["pierce_atr"]) * row_atr
            side: str | None = None
            if (
                upper_aligned
                and float(row["high"]) > upper + pierce
                and float(row["close"]) < upper
                and float(row["close"]) < float(row["open"])
            ):
                side = "SELL"
                stop = float(row["high"]) + 0.10 * row_atr
                reward = float(row["close"] - row["vwap"])
            elif (
                lower_aligned
                and float(row["low"]) < lower - pierce
                and float(row["close"]) > lower
                and float(row["close"]) > float(row["open"])
            ):
                side = "BUY"
                stop = float(row["low"]) - 0.10 * row_atr
                reward = float(row["vwap"] - row["close"])
            if side is None:
                continue
            nxt = _entry_after(bars_1m, pd.Timestamp(ts), 5)
            if nxt is None:
                continue
            entry_ts, entry = nxt
            trade_risk = abs(entry - stop)
            if trade_risk <= 0 or reward / trade_risk < float(spec["min_reward_r"]):
                continue
            out.append(
                Candidate(
                    family="balanced_value_area_reversion",
                    variant=str(spec["id"]),
                    source_id="volume_profile_balance",
                    symbol=symbol,
                    side=side,
                    signal_ts=str(ts),
                    entry_ts=str(entry_ts),
                    entry=entry,
                    stop=stop,
                    target_r=min(1.6, reward / trade_risk),
                    forced_exit_ts=str(day + pd.Timedelta(hours=forced_h)),
                    notes="Prior-only rolling value area + overlapping balanced ranges + completed IB-edge failed continuation",
                )
            )
            break
    return out


def generate_daily_ibs_capitulation_reversion(
    bars_1m: pd.DataFrame,
    _bars_15m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Adapt the public daily IBS setup to stopped, executable NQ futures trades.

    The source tests SPY without the hard futures stop the user requires. This
    research-only adaptation enters the next NQ RTH open, places a fixed-percent
    hard stop, takes profit at the signal day's high, and caps holding at ten RTH
    sessions. Signal-day OHLC is complete before the next-session entry.
    """
    if symbol != "NQ":
        return []
    rth_days: list[tuple[pd.Timestamp, pd.DataFrame]] = []
    median_step = bars_1m.index.to_series().diff().dropna().dt.total_seconds().median()
    minimum_rth_rows = 300 if not np.isfinite(median_step) or median_step <= 90 else 60
    for day, day_frame in bars_1m.groupby(bars_1m.index.normalize()):
        rth = day_frame[
            (day_frame.index >= day + pd.Timedelta(hours=9, minutes=30))
            & (day_frame.index < day + pd.Timedelta(hours=16))
        ]
        if len(rth) >= minimum_rth_rows:
            rth_days.append((pd.Timestamp(day), rth))
    if len(rth_days) < 30:
        return []
    daily = pd.DataFrame(
        {
            "open": [float(frame["open"].iloc[0]) for _day, frame in rth_days],
            "high": [float(frame["high"].max()) for _day, frame in rth_days],
            "low": [float(frame["low"].min()) for _day, frame in rth_days],
            "close": [float(frame["close"].iloc[-1]) for _day, frame in rth_days],
        },
        index=pd.DatetimeIndex([day for day, _frame in rth_days]),
    )
    daily["range25"] = (daily["high"] - daily["low"]).rolling(25).mean()
    daily["high10"] = daily["high"].rolling(10).max()
    daily["ibs"] = (daily["close"] - daily["low"]) / (
        daily["high"] - daily["low"]
    ).replace(0, np.nan)
    daily["sma200"] = daily["close"].rolling(200).mean()
    out: list[Candidate] = []
    stop_pct = float(spec["stop_pct"])
    for i in range(25, len(rth_days) - 1):
        row = daily.iloc[i]
        if not all(
            np.isfinite(float(row[key]))
            for key in ("range25", "high10", "ibs", "close")
        ):
            continue
        threshold = float(row["high10"]) - float(spec["excursion_factor"]) * float(
            row["range25"]
        )
        if float(row["close"]) >= threshold or float(row["ibs"]) >= float(spec["ibs_max"]):
            continue
        if bool(spec.get("above_sma200")):
            if not np.isfinite(float(row["sma200"])) or float(row["close"]) <= float(row["sma200"]):
                continue
        _entry_day, entry_frame = rth_days[i + 1]
        entry_ts = pd.Timestamp(entry_frame.index[0])
        entry = float(entry_frame["open"].iloc[0])
        stop = entry * (1.0 - stop_pct)
        target = float(row["high"])
        trade_risk = entry - stop
        if target <= entry or trade_risk <= 0:
            continue
        target_r = (target - entry) / trade_risk
        if target_r < float(spec["min_target_r"]):
            continue
        force_index = min(len(rth_days) - 1, i + 10)
        force_day, force_frame = rth_days[force_index]
        out.append(
            Candidate(
                family="daily_ibs_capitulation_reversion",
                variant=str(spec["id"]),
                source_id="daily_ibs_reversion",
                symbol="NQ",
                side="BUY",
                signal_ts=str(rth_days[i][1].index[-1]),
                entry_ts=str(entry_ts),
                entry=entry,
                stop=stop,
                target_r=target_r,
                forced_exit_ts=str(force_frame.index[-1]),
                notes=(
                    "Completed RTH daily IBS capitulation; next-session open; hard stop; "
                    "signal-day-high target; maximum ten RTH sessions"
                ),
            )
        )
    return out


def _rth_times(symbol: str) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    if symbol == "CL":
        return (9, 0), (9, 30), (13, 30)
    return (9, 30), (10, 0), (15, 30)


def generate_intraday_momentum(
    bars_1m: pd.DataFrame,
    _bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    open_t, opening_end_t, entry_t = _rth_times(symbol)
    daily = bars_1m.groupby(bars_1m.index.normalize()).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("volume", "sum")
    )
    daily_atr = (daily["high"] - daily["low"]).rolling(20).mean().shift(1)
    opening_volumes: list[float] = []
    out: list[Candidate] = []
    for day, d in bars_1m.groupby(bars_1m.index.normalize()):
        start = day + pd.Timedelta(hours=open_t[0], minutes=open_t[1])
        opening_end = day + pd.Timedelta(hours=opening_end_t[0], minutes=opening_end_t[1])
        entry_clock = day + pd.Timedelta(hours=entry_t[0], minutes=entry_t[1])
        close_clock = day + pd.Timedelta(hours=14 if symbol == "CL" else 16)
        opening = d[(d.index >= start) & (d.index < opening_end)]
        if len(opening) < 20 or day not in daily_atr.index:
            continue
        atr = float(daily_atr.loc[day])
        open_volume = float(opening["volume"].sum())
        volume_ref = float(np.median(opening_volumes[-10:])) if len(opening_volumes) >= 5 else np.nan
        opening_volumes.append(open_volume)
        if not np.isfinite(atr) or atr <= 0:
            continue
        impulse = float(opening["close"].iloc[-1] - opening["open"].iloc[0])
        if abs(impulse) < float(spec["min_impulse_atr"]) * atr:
            continue
        if bool(spec.get("high_volume")) and (not np.isfinite(volume_ref) or open_volume <= volume_ref):
            continue
        entry_rows = d[d.index >= entry_clock]
        if entry_rows.empty:
            continue
        entry_ts = pd.Timestamp(entry_rows.index[0])
        entry = float(entry_rows["open"].iloc[0])
        stop_distance = max(0.30 * atr, abs(impulse) * 0.50)
        side = "BUY" if impulse > 0 else "SELL"
        stop = entry - stop_distance if side == "BUY" else entry + stop_distance
        # Signal at entry clock and enter immediately at that minute open.
        cand = Candidate(
            family="intraday_open_to_close_momentum",
            variant=str(spec["id"]),
            source_id="intraday_momentum",
            symbol=symbol,
            side=side,
            signal_ts=str(entry_ts),
            entry_ts=str(entry_ts),
            entry=entry,
            stop=stop,
            target_r=1.5,
            forced_exit_ts=str(close_clock),
            notes="Opening-half-hour direction predicts final-half-hour direction; optional opening-volume gate",
        )
        out.append(cand)
    return out


def _london_range_by_day(bars_5m: pd.DataFrame) -> dict[pd.Timestamp, tuple[float, float]]:
    out: dict[pd.Timestamp, tuple[float, float]] = {}
    for day, d in bars_5m.groupby(bars_5m.index.normalize()):
        part = d[(d.index >= day + pd.Timedelta(hours=3)) & (d.index < day + pd.Timedelta(hours=9, minutes=30))]
        if len(part) >= 30:
            out[day] = (float(part["high"].max()), float(part["low"].min()))
    return out


def generate_london_sweep_reversal(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    f = bars_5m.copy()
    f["atr"] = _atr(f)
    ranges = _london_range_by_day(f)
    out: list[Candidate] = []
    for day, (london_high, london_low) in ranges.items():
        ny = f[(f.index >= day + pd.Timedelta(hours=9, minutes=30)) & (f.index < day + pd.Timedelta(hours=11, minutes=30))]
        taken = False
        for ts, row in ny.iterrows():
            if taken:
                break
            atr = float(row["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue
            side: str | None = None
            if float(row["high"]) > london_high + float(spec["pierce_atr"]) * atr and float(row["close"]) < london_high:
                side = "SELL"
                stop = float(row["high"]) + 0.15 * atr
            elif float(row["low"]) < london_low - float(spec["pierce_atr"]) * atr and float(row["close"]) > london_low:
                side = "BUY"
                stop = float(row["low"]) - 0.15 * atr
            else:
                continue
            cand = _candidate(
                bars_1m=bars_1m,
                signal_ts=pd.Timestamp(ts),
                signal_minutes=5,
                family="london_range_sweep_reversal",
                variant=str(spec["id"]),
                source_id="session_range",
                symbol=symbol,
                side=side,
                stop=stop,
                target_r=1.5,
                forced_exit_ts=(
                    day + pd.Timedelta(hours=13, minutes=30)
                    if symbol == "CL"
                    else day + pd.Timedelta(hours=16)
                ),
                notes="NY pierces a London extreme then closes back inside; fade the failed break",
            )
            if cand:
                out.append(cand)
                taken = True
    return out


def generate_initial_balance_failed_break(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade a failed first-hour range break back toward session VWAP."""
    f = _session_vwap_features(bars_5m)
    open_h, open_m = (9, 0) if symbol == "CL" else (9, 30)
    forced_h = 14 if symbol == "CL" else 16
    out: list[Candidate] = []
    for day, d in f.groupby(f.index.normalize()):
        ib_start = day + pd.Timedelta(hours=open_h, minutes=open_m)
        ib_end = ib_start + pd.Timedelta(hours=1)
        ib = d[(d.index >= ib_start) & (d.index < ib_end)]
        post = d[(d.index >= ib_end) & (d.index < day + pd.Timedelta(hours=forced_h - 1))]
        if len(ib) < 10 or post.empty:
            continue
        ib_high, ib_low = float(ib["high"].max()), float(ib["low"].min())
        for ts, row in post.iterrows():
            atr = float(row["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue
            pierce = float(spec["pierce_atr"]) * atr
            side: str | None = None
            if float(row["high"]) > ib_high + pierce and float(row["close"]) < ib_high:
                side = "SELL"
                stop = float(row["high"]) + 0.15 * atr
            elif float(row["low"]) < ib_low - pierce and float(row["close"]) > ib_low:
                side = "BUY"
                stop = float(row["low"]) - 0.15 * atr
            if side is None:
                continue
            if bool(spec.get("flat_vwap")):
                loc = f.index.get_loc(ts)
                if isinstance(loc, slice) or int(loc) < 6:
                    continue
                slope = abs(float(row["vwap"] - f["vwap"].iloc[int(loc) - 6])) / atr
                if slope > 0.50:
                    continue
            nxt = _entry_after(bars_1m, pd.Timestamp(ts), 5)
            if nxt is None:
                continue
            entry_ts, entry = nxt
            risk = abs(entry - stop)
            reward_to_vwap = (entry - float(row["vwap"])) if side == "SELL" else (float(row["vwap"]) - entry)
            if risk <= 0 or reward_to_vwap / risk < 1.0:
                continue
            target_r = min(2.0, reward_to_vwap / risk)
            out.append(
                Candidate(
                    family="initial_balance_failed_break",
                    variant=str(spec["id"]),
                    source_id="initial_balance",
                    symbol=symbol,
                    side=side,
                    signal_ts=str(ts),
                    entry_ts=str(entry_ts),
                    entry=entry,
                    stop=stop,
                    target_r=target_r,
                    forced_exit_ts=str(day + pd.Timedelta(hours=forced_h)),
                    notes="First-hour IB break fails to hold; enter after completed 5m reclaim and target session VWAP",
                )
            )
            break
    return out


def generate_overnight_gap_reversion(
    bars_1m: pd.DataFrame,
    bars_15m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    open_h, open_m = (9, 0) if symbol == "CL" else (9, 30)
    close_h = 14 if symbol == "CL" else 16
    daily_ranges: list[float] = []
    prior_close: float | None = None
    out: list[Candidate] = []
    for day, d in bars_1m.groupby(bars_1m.index.normalize()):
        rth = d[(d.index >= day + pd.Timedelta(hours=open_h, minutes=open_m)) & (d.index < day + pd.Timedelta(hours=close_h))]
        if len(rth) < 100:
            continue
        current_open = float(rth["open"].iloc[0])
        day_range = float(rth["high"].max() - rth["low"].min())
        atr_ref = float(np.mean(daily_ranges[-20:])) if len(daily_ranges) >= 10 else np.nan
        if prior_close is not None and np.isfinite(atr_ref) and atr_ref > 0:
            gap = current_open - prior_close
            if abs(gap) >= float(spec["gap_atr"]) * atr_ref:
                first_end = day + pd.Timedelta(hours=open_h, minutes=open_m + 15)
                first = rth[rth.index < first_end]
                if len(first) >= 10:
                    close15 = float(first["close"].iloc[-1])
                    rejected = (gap > 0 and close15 < current_open) or (gap < 0 and close15 > current_open)
                    if rejected:
                        signal_ts = day + pd.Timedelta(hours=open_h, minutes=open_m)
                        side = "SELL" if gap > 0 else "BUY"
                        stop = (
                            float(first["high"].max()) + 0.10 * atr_ref
                            if side == "SELL"
                            else float(first["low"].min()) - 0.10 * atr_ref
                        )
                        cand = _candidate(
                            bars_1m=bars_1m,
                            signal_ts=signal_ts,
                            signal_minutes=15,
                            family="overnight_gap_reversion",
                            variant=str(spec["id"]),
                            source_id="atr_rsi_reversion",
                            symbol=symbol,
                            side=side,
                            stop=stop,
                            target_r=1.5,
                            forced_exit_ts=day + pd.Timedelta(hours=close_h),
                            notes="Large RTH opening gap plus first-15m rejection; fade overnight inventory toward prior close",
                        )
                        if cand:
                            out.append(cand)
        prior_close = float(rth["close"].iloc[-1])
        daily_ranges.append(day_range)
    return out


def generate_compression_breakout(
    bars_1m: pd.DataFrame,
    bars_15m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    f = bars_15m.copy()
    f["atr"] = _atr(f)
    mid = f["close"].rolling(20).mean()
    std = f["close"].rolling(20).std(ddof=0)
    width = (4.0 * std / mid.replace(0, np.nan))
    f["compression"] = width.shift(1) <= width.shift(1).rolling(int(spec["lookback"])).quantile(0.20)
    f["prior_high"] = f["high"].shift(1).rolling(20).max()
    f["prior_low"] = f["low"].shift(1).rolling(20).min()
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in range(55, len(f)):
        ts = pd.Timestamp(f.index[i])
        minute = ts.hour * 60 + ts.minute
        if minute < 3 * 60 or minute > 15 * 60:
            continue
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=6):
            continue
        row = f.iloc[i]
        if not bool(row["compression"]):
            continue
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0:
            continue
        if float(row["close"]) > float(row["prior_high"]):
            side, stop = "BUY", float(row["close"]) - 1.0 * atr
        elif float(row["close"]) < float(row["prior_low"]):
            side, stop = "SELL", float(row["close"]) + 1.0 * atr
        else:
            continue
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=15,
            family="volatility_compression_breakout",
            variant=str(spec["id"]),
            source_id="time_series_momentum",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=2.0,
            notes="20-bar channel break after Bollinger-width compression; point-in-time 15m bars",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_donchian_trend(
    bars_1m: pd.DataFrame,
    bars_15m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    f = bars_15m.copy()
    lookback = int(spec["lookback"])
    f["atr"] = _atr(f)
    f["ema50"] = f["close"].ewm(span=50, adjust=False).mean()
    f["prior_high"] = f["high"].shift(1).rolling(lookback).max()
    f["prior_low"] = f["low"].shift(1).rolling(lookback).min()
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in range(max(55, lookback + 2), len(f)):
        ts = pd.Timestamp(f.index[i])
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=8):
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        if not np.isfinite(atr) or atr <= 0:
            continue
        ema_rising = float(row["ema50"]) > float(f["ema50"].iloc[i - 4])
        if float(row["close"]) > float(row["prior_high"]) and ema_rising:
            side, stop = "BUY", float(row["close"]) - float(spec["stop_atr"]) * atr
        elif float(row["close"]) < float(row["prior_low"]) and not ema_rising:
            side, stop = "SELL", float(row["close"]) + float(spec["stop_atr"]) * atr
        else:
            continue
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=15,
            family="donchian_trend_breakout",
            variant=str(spec["id"]),
            source_id="donchian",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=3.0,
            notes="Donchian-style breakout with fixed ATR stop; expected low WR/high payoff",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def _session_clock(symbol: str) -> tuple[tuple[int, int], tuple[int, int]]:
    return ((9, 0), (14, 0)) if symbol == "CL" else ((9, 30), (16, 0))


def _clock(day: pd.Timestamp, value: tuple[int, int]) -> pd.Timestamp:
    return day + pd.Timedelta(hours=value[0], minutes=value[1])


def _rth_day_frames(
    bars: pd.DataFrame, symbol: str, *, minimum_rows: int = 40
) -> dict[pd.Timestamp, pd.DataFrame]:
    open_clock, close_clock = _session_clock(symbol)
    result: dict[pd.Timestamp, pd.DataFrame] = {}
    for day, day_frame in bars.groupby(bars.index.normalize()):
        day = pd.Timestamp(day)
        rth = day_frame[
            (day_frame.index >= _clock(day, open_clock))
            & (day_frame.index < _clock(day, close_clock))
        ]
        if len(rth) >= minimum_rows:
            result[day] = rth
    return result


def _volume_profile_mean_std(frame: pd.DataFrame) -> tuple[float, float] | None:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    weights = frame["volume"].clip(lower=0).replace(0, 1.0)
    total = float(weights.sum())
    if not np.isfinite(total) or total <= 0:
        return None
    mean = float((typical * weights).sum() / total)
    variance = float((((typical - mean) ** 2) * weights).sum() / total)
    std = sqrt(max(0.0, variance))
    if not np.isfinite(mean) or not np.isfinite(std) or std <= 0:
        return None
    return mean, std


def _volume_profile_value_area(
    frame: pd.DataFrame, symbol: str, fraction: float = 0.70
) -> tuple[float, float, float] | None:
    """Approximate a 70% volume-profile VA from point-in-time OHLCV bars.

    Bar volume is assigned to its typical-price bin because OHLCV does not
    expose volume-at-price. The POC bin is expanded toward the higher-volume
    adjacent bin until the requested cumulative fraction is covered.
    """
    low = float(frame["low"].min())
    high = float(frame["high"].max())
    span = high - low
    if not np.isfinite(span) or span <= 0:
        return None
    tick = 0.01 if symbol == "CL" else 0.25
    width = max(tick, span / 50.0)
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    volume = frame["volume"].clip(lower=0).replace(0, 1.0)
    bins = np.floor((typical - low) / width).astype(int)
    profile = volume.groupby(bins).sum().sort_index()
    if profile.empty or float(profile.sum()) <= 0:
        return None
    poc_bin = int(profile.idxmax())
    selected = {poc_bin}
    cumulative = float(profile.loc[poc_bin])
    target = float(profile.sum()) * float(fraction)
    lower = upper = poc_bin
    while cumulative < target:
        lower_volume = float(profile.get(lower - 1, 0.0))
        upper_volume = float(profile.get(upper + 1, 0.0))
        if lower_volume <= 0 and upper_volume <= 0:
            remaining = [int(value) for value in profile.index if int(value) not in selected]
            if not remaining:
                break
            nearest = min(remaining, key=lambda value: abs(value - poc_bin))
            selected.add(nearest)
            cumulative += float(profile.loc[nearest])
            lower, upper = min(lower, nearest), max(upper, nearest)
            continue
        if upper_volume >= lower_volume:
            upper += 1
            selected.add(upper)
            cumulative += upper_volume
        else:
            lower -= 1
            selected.add(lower)
            cumulative += lower_volume
    value_low = low + min(selected) * width
    value_high = low + (max(selected) + 1) * width
    poc = low + (poc_bin + 0.5) * width
    if not (value_low < value_high):
        return None
    return float(value_low), float(value_high), float(poc)


def generate_prior_day_level_failure(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade a completed rejection of the prior RTH high or low toward VWAP."""
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    days = sorted(rth_days)
    out: list[Candidate] = []
    open_clock, close_clock = _session_clock(symbol)
    for i in range(1, len(days)):
        day = days[i]
        prior = rth_days[days[i - 1]]
        current = rth_days[day]
        prior_high = float(prior["high"].max())
        prior_low = float(prior["low"].min())
        search = current[
            (current.index >= _clock(day, open_clock) + pd.Timedelta(minutes=30))
            & (current.index < _clock(day, close_clock) - pd.Timedelta(minutes=45))
        ]
        for ts, row in search.iterrows():
            atr = float(row["atr"])
            candle_range = float(row["high"] - row["low"])
            if not np.isfinite(atr) or atr <= 0 or candle_range <= 0:
                continue
            close_location = float(row["close"] - row["low"]) / candle_range
            pierce = float(spec["pierce_atr"]) * atr
            side: str | None = None
            if (
                float(row["high"]) >= prior_high + pierce
                and float(row["close"]) < prior_high
                and close_location <= float(spec["max_close_location"])
                and float(row["close"]) < float(row["open"])
            ):
                side = "SELL"
                stop = float(row["high"]) + 0.10 * atr
            elif (
                float(row["low"]) <= prior_low - pierce
                and float(row["close"]) > prior_low
                and close_location >= 1.0 - float(spec["max_close_location"])
                and float(row["close"]) > float(row["open"])
            ):
                side = "BUY"
                stop = float(row["low"]) - 0.10 * atr
            if side is None:
                continue
            nxt = _entry_after(bars_1m, pd.Timestamp(ts), 5)
            if nxt is None:
                continue
            entry_ts, entry = nxt
            risk = abs(entry - stop)
            reward = (
                entry - float(row["vwap"])
                if side == "SELL"
                else float(row["vwap"]) - entry
            )
            if risk <= 0 or reward / risk < float(spec["min_reward_r"]):
                continue
            out.append(
                Candidate(
                    family="prior_day_level_failure",
                    variant=str(spec["id"]),
                    source_id="nq_first_pullback",
                    symbol=symbol,
                    side=side,
                    signal_ts=str(ts),
                    entry_ts=str(entry_ts),
                    entry=entry,
                    stop=stop,
                    target_r=min(1.6, reward / risk),
                    forced_exit_ts=str(_clock(day, close_clock)),
                    notes="Prior RTH extreme pierced and rejected on a completed bar; fixed signal-time VWAP objective",
                )
            )
            break
    return out


def generate_opening_range_retest_continuation(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Enter only after an opening-range breakout survives a separate-bar retest."""
    f = _session_vwap_features(bars_5m)
    f["prior_volume_median"] = f["volume"].shift(1).rolling(20).median()
    rth_days = _rth_day_frames(f, symbol)
    out: list[Candidate] = []
    open_clock, close_clock = _session_clock(symbol)
    duration = int(spec["range_minutes"])
    for day, rth in rth_days.items():
        start = _clock(day, open_clock)
        range_end = start + pd.Timedelta(minutes=duration)
        opening = rth[(rth.index >= start) & (rth.index < range_end)]
        post = rth[
            (rth.index >= range_end)
            & (rth.index < _clock(day, close_clock) - pd.Timedelta(minutes=60))
        ]
        if len(opening) < max(4, int(duration / 5 * 0.8)) or len(post) < 2:
            continue
        range_high = float(opening["high"].max())
        range_low = float(opening["low"].min())
        post_rows = list(post.iterrows())
        for j, (break_ts, break_row) in enumerate(post_rows[:-1]):
            atr = float(break_row["atr"])
            volume_ref = float(break_row["prior_volume_median"])
            if not np.isfinite(atr) or atr <= 0 or not np.isfinite(volume_ref):
                continue
            threshold = float(spec["break_atr"]) * atr
            enough_volume = float(break_row["volume"]) >= float(spec["min_rvol"]) * volume_ref
            if (
                float(break_row["close"]) > range_high + threshold
                and float(break_row["close"]) > float(break_row["vwap"])
                and enough_volume
            ):
                side, boundary = "BUY", range_high
            elif (
                float(break_row["close"]) < range_low - threshold
                and float(break_row["close"]) < float(break_row["vwap"])
                and enough_volume
            ):
                side, boundary = "SELL", range_low
            else:
                continue
            for retest_ts, row in post_rows[j + 1 : j + 1 + int(spec["max_retest_bars"])]:
                row_atr = float(row["atr"])
                if not np.isfinite(row_atr) or row_atr <= 0:
                    continue
                depth = float(spec["max_depth_atr"]) * row_atr
                if side == "BUY":
                    confirms = (
                        float(row["low"]) <= boundary + 0.10 * row_atr
                        and float(row["low"]) >= boundary - depth
                        and float(row["close"]) > boundary
                        and float(row["close"]) > float(row["open"])
                    )
                    stop = min(float(row["low"]), boundary - depth) - 0.05 * row_atr
                else:
                    confirms = (
                        float(row["high"]) >= boundary - 0.10 * row_atr
                        and float(row["high"]) <= boundary + depth
                        and float(row["close"]) < boundary
                        and float(row["close"]) < float(row["open"])
                    )
                    stop = max(float(row["high"]), boundary + depth) + 0.05 * row_atr
                if not confirms:
                    continue
                cand = _candidate(
                    bars_1m=bars_1m,
                    signal_ts=pd.Timestamp(retest_ts),
                    signal_minutes=5,
                    family="opening_range_retest_continuation",
                    variant=str(spec["id"]),
                    source_id="opening_range_research",
                    symbol=symbol,
                    side=side,
                    stop=stop,
                    target_r=1.6,
                    forced_exit_ts=_clock(day, close_clock),
                    notes="Completed opening-range break, volume confirmation, then a separate shallow retest",
                )
                if cand:
                    out.append(cand)
                break
            break
    return out


def generate_opening_range_midpoint_continuation(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Trade the first directional rejection of an opening-range midpoint."""
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    out: list[Candidate] = []
    open_clock, close_clock = _session_clock(symbol)
    duration = int(spec["range_minutes"])
    for day, rth in rth_days.items():
        start = _clock(day, open_clock)
        range_end = start + pd.Timedelta(minutes=duration)
        opening = rth[(rth.index >= start) & (rth.index < range_end)]
        search = rth[
            (rth.index >= range_end)
            & (rth.index < _clock(day, close_clock) - pd.Timedelta(minutes=90))
        ]
        if len(opening) < max(4, int(duration / 5 * 0.8)) or search.empty:
            continue
        atr = float(opening["atr"].iloc[-1])
        if not np.isfinite(atr) or atr <= 0:
            continue
        impulse = float(opening["close"].iloc[-1] - opening["open"].iloc[0])
        if abs(impulse) < float(spec["impulse_atr"]) * atr:
            continue
        side = "BUY" if impulse > 0 else "SELL"
        high = float(opening["high"].max())
        low = float(opening["low"].min())
        midpoint = (high + low) / 2.0
        for ts, row in search.iterrows():
            row_atr = float(row["atr"])
            if not np.isfinite(row_atr) or row_atr <= 0:
                continue
            if side == "BUY":
                confirms = (
                    float(row["low"]) <= midpoint + 0.10 * row_atr
                    and float(row["low"]) >= midpoint - float(spec["max_depth_atr"]) * row_atr
                    and float(row["close"]) > midpoint
                    and float(row["close"]) > float(row["open"])
                    and float(row["close"]) > float(row["vwap"])
                )
                stop = float(row["low"]) - 0.10 * row_atr
                objective = high
            else:
                confirms = (
                    float(row["high"]) >= midpoint - 0.10 * row_atr
                    and float(row["high"]) <= midpoint + float(spec["max_depth_atr"]) * row_atr
                    and float(row["close"]) < midpoint
                    and float(row["close"]) < float(row["open"])
                    and float(row["close"]) < float(row["vwap"])
                )
                stop = float(row["high"]) + 0.10 * row_atr
                objective = low
            if not confirms:
                continue
            nxt = _entry_after(bars_1m, pd.Timestamp(ts), 5)
            if nxt is None:
                continue
            entry_ts, entry = nxt
            risk = abs(entry - stop)
            reward = objective - entry if side == "BUY" else entry - objective
            if risk <= 0 or reward / risk < float(spec["min_reward_r"]):
                continue
            out.append(
                Candidate(
                    family="opening_range_midpoint_continuation",
                    variant=str(spec["id"]),
                    source_id="nq_first_pullback",
                    symbol=symbol,
                    side=side,
                    signal_ts=str(ts),
                    entry_ts=str(entry_ts),
                    entry=entry,
                    stop=stop,
                    target_r=min(1.6, reward / risk),
                    forced_exit_ts=str(_clock(day, close_clock)),
                    notes="Directional opening impulse followed by the first completed midpoint rejection",
                )
            )
            break
    return out


def generate_conditional_overnight_reversal(
    bars_1m: pd.DataFrame,
    _bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade overnight inventory only after same-direction prior-day extension and rejection."""
    open_clock, close_clock = _session_clock(symbol)
    median_step = bars_1m.index.to_series().diff().dropna().dt.total_seconds().median()
    minimum_rows = 300 if not np.isfinite(median_step) or median_step <= 90 else 60
    first_window_rows = 10 if minimum_rows == 300 else 3
    rth_days = _rth_day_frames(bars_1m, symbol, minimum_rows=minimum_rows)
    days = sorted(rth_days)
    prior_ranges: list[float] = []
    out: list[Candidate] = []
    for i in range(1, len(days)):
        day = days[i]
        prior = rth_days[days[i - 1]]
        current = rth_days[day]
        if bool(spec.get("exclude_monday")) and day.dayofweek == 0:
            prior_ranges.append(float(prior["high"].max() - prior["low"].min()))
            continue
        atr_ref = float(np.mean(prior_ranges[-20:])) if len(prior_ranges) >= 10 else np.nan
        prior_ranges.append(float(prior["high"].max() - prior["low"].min()))
        if not np.isfinite(atr_ref) or atr_ref <= 0:
            continue
        prior_return = float(prior["close"].iloc[-1] - prior["open"].iloc[0])
        prior_close = float(prior["close"].iloc[-1])
        current_open = float(current["open"].iloc[0])
        gap = current_open - prior_close
        if (
            abs(gap) < float(spec["gap_atr"]) * atr_ref
            or abs(prior_return) < float(spec["prior_return_atr"]) * atr_ref
            or np.sign(gap) != np.sign(prior_return)
        ):
            continue
        first = current[current.index < _clock(day, open_clock) + pd.Timedelta(minutes=15)]
        if len(first) < first_window_rows:
            continue
        rejected = (gap > 0 and float(first["close"].iloc[-1]) < current_open) or (
            gap < 0 and float(first["close"].iloc[-1]) > current_open
        )
        if not rejected:
            continue
        side = "SELL" if gap > 0 else "BUY"
        stop = (
            float(first["high"].max()) + 0.10 * atr_ref
            if side == "SELL"
            else float(first["low"].min()) - 0.10 * atr_ref
        )
        signal_ts = pd.Timestamp(first.index[-1])
        nxt = _entry_after(bars_1m, signal_ts, int(round(median_step / 60.0)))
        if nxt is None:
            continue
        entry_ts, entry = nxt
        risk = abs(entry - stop)
        reward = entry - prior_close if side == "SELL" else prior_close - entry
        if risk <= 0 or reward / risk < float(spec["min_reward_r"]):
            continue
        out.append(
            Candidate(
                family="conditional_overnight_reversal",
                variant=str(spec["id"]),
                source_id="nq_intraday_conditional",
                symbol=symbol,
                side=side,
                signal_ts=str(signal_ts),
                entry_ts=str(entry_ts),
                entry=entry,
                stop=stop,
                target_r=min(1.6, reward / risk),
                forced_exit_ts=str(_clock(day, close_clock)),
                notes="Prior RTH return and overnight gap share a sign; first 15 minutes reject the gap",
            )
        )
    return out


def generate_value_area_breakout_continuation(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Follow a prior-value-area break only after a shallow, completed retest."""
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    days = sorted(rth_days)
    out: list[Candidate] = []
    open_clock, close_clock = _session_clock(symbol)
    for i in range(1, len(days)):
        day = days[i]
        profile = _volume_profile_mean_std(rth_days[days[i - 1]])
        if profile is None:
            continue
        poc, profile_std = profile
        value_high, value_low = poc + profile_std, poc - profile_std
        current = rth_days[day]
        search = current[
            (current.index >= _clock(day, open_clock) + pd.Timedelta(minutes=30))
            & (current.index < _clock(day, close_clock) - pd.Timedelta(minutes=60))
        ]
        rows = list(search.iterrows())
        for j, (_break_ts, break_row) in enumerate(rows[:-1]):
            atr = float(break_row["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue
            threshold = float(spec["break_atr"]) * atr
            if (
                float(break_row["close"]) > value_high + threshold
                and float(break_row["close"]) > float(break_row["vwap"])
            ):
                side, boundary = "BUY", value_high
            elif (
                float(break_row["close"]) < value_low - threshold
                and float(break_row["close"]) < float(break_row["vwap"])
            ):
                side, boundary = "SELL", value_low
            else:
                continue
            for retest_ts, row in rows[j + 1 : j + 1 + int(spec["max_retest_bars"])]:
                row_atr = float(row["atr"])
                if not np.isfinite(row_atr) or row_atr <= 0:
                    continue
                max_depth = float(spec["max_depth_atr"]) * row_atr
                if side == "BUY":
                    confirms = (
                        boundary - max_depth <= float(row["low"]) <= boundary + 0.10 * row_atr
                        and float(row["close"]) > boundary
                        and float(row["close"]) > float(row["open"])
                    )
                    stop = min(float(row["low"]), boundary - max_depth) - 0.05 * row_atr
                else:
                    confirms = (
                        boundary - 0.10 * row_atr <= float(row["high"]) <= boundary + max_depth
                        and float(row["close"]) < boundary
                        and float(row["close"]) < float(row["open"])
                    )
                    stop = max(float(row["high"]), boundary + max_depth) + 0.05 * row_atr
                if not confirms:
                    continue
                cand = _candidate(
                    bars_1m=bars_1m,
                    signal_ts=pd.Timestamp(retest_ts),
                    signal_minutes=5,
                    family="value_area_breakout_continuation",
                    variant=str(spec["id"]),
                    source_id="value_area_breakout",
                    symbol=symbol,
                    side=side,
                    stop=stop,
                    target_r=1.6,
                    forced_exit_ts=_clock(day, close_clock),
                    notes="Prior-day volume-weighted value boundary break; skip first 30 minutes; shallow retest",
                )
                if cand:
                    out.append(cand)
                break
            break
    return out


def generate_overnight_range_break_retest(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Follow a NY/pit break of the completed overnight range after a retest."""
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    out: list[Candidate] = []
    open_clock, close_clock = _session_clock(symbol)
    for day, rth in rth_days.items():
        start = _clock(day, open_clock)
        overnight = f[
            (f.index >= day - pd.Timedelta(days=1) + pd.Timedelta(hours=18))
            & (f.index < start)
        ]
        search = rth[(rth.index >= start) & (rth.index < start + pd.Timedelta(hours=2))]
        if len(overnight) < 60 or len(search) < 2:
            continue
        overnight_high = float(overnight["high"].max())
        overnight_low = float(overnight["low"].min())
        rows = list(search.iterrows())
        for j, (_break_ts, break_row) in enumerate(rows[:-1]):
            atr = float(break_row["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue
            threshold = float(spec["break_atr"]) * atr
            if (
                float(break_row["close"]) > overnight_high + threshold
                and float(break_row["close"]) > float(break_row["vwap"])
            ):
                side, boundary = "BUY", overnight_high
            elif (
                float(break_row["close"]) < overnight_low - threshold
                and float(break_row["close"]) < float(break_row["vwap"])
            ):
                side, boundary = "SELL", overnight_low
            else:
                continue
            for retest_ts, row in rows[j + 1 : j + 1 + int(spec["max_retest_bars"])]:
                row_atr = float(row["atr"])
                depth = float(spec["max_depth_atr"]) * row_atr
                if not np.isfinite(row_atr) or row_atr <= 0:
                    continue
                if side == "BUY":
                    confirms = (
                        boundary - depth <= float(row["low"]) <= boundary + 0.10 * row_atr
                        and float(row["close"]) > boundary
                        and float(row["close"]) > float(row["open"])
                    )
                    stop = min(float(row["low"]), boundary - depth) - 0.05 * row_atr
                else:
                    confirms = (
                        boundary - 0.10 * row_atr <= float(row["high"]) <= boundary + depth
                        and float(row["close"]) < boundary
                        and float(row["close"]) < float(row["open"])
                    )
                    stop = max(float(row["high"]), boundary + depth) + 0.05 * row_atr
                if not confirms:
                    continue
                cand = _candidate(
                    bars_1m=bars_1m,
                    signal_ts=pd.Timestamp(retest_ts),
                    signal_minutes=5,
                    family="overnight_range_break_retest",
                    variant=str(spec["id"]),
                    source_id="nq_first_pullback",
                    symbol=symbol,
                    side=side,
                    stop=stop,
                    target_r=1.6,
                    forced_exit_ts=_clock(day, close_clock),
                    notes="Completed overnight range, RTH breakout, and separate shallow retest",
                )
                if cand:
                    out.append(cand)
                break
            break
    return out


def generate_session_extreme_two_bar_reversal(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade a new session extreme only after a separate two-bar rejection."""
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    out: list[Candidate] = []
    open_clock, close_clock = _session_clock(symbol)
    for day, rth in rth_days.items():
        search_start = _clock(day, open_clock) + pd.Timedelta(minutes=60)
        search_end = _clock(day, close_clock) - pd.Timedelta(minutes=60)
        for i in range(13, len(rth)):
            ts = pd.Timestamp(rth.index[i])
            if ts < search_start or ts >= search_end:
                continue
            prior_history = rth.iloc[: i - 1]
            prior = rth.iloc[i - 1]
            row = rth.iloc[i]
            atr = float(row["atr"])
            prior_range = float(prior["high"] - prior["low"])
            if not np.isfinite(atr) or atr <= 0 or prior_range <= 0:
                continue
            upper_extreme = (
                float(prior["high"]) > float(prior_history["high"].max())
                and (float(prior["high"]) - float(prior["vwap"])) / atr
                >= float(spec["min_vwap_distance_atr"])
            )
            lower_extreme = (
                float(prior["low"]) < float(prior_history["low"].min())
                and (float(prior["vwap"]) - float(prior["low"])) / atr
                >= float(spec["min_vwap_distance_atr"])
            )
            confirm_fraction = float(spec["confirm_fraction"])
            if (
                upper_extreme
                and float(row["close"]) <= float(prior["low"]) + confirm_fraction * prior_range
                and float(row["close"]) < float(row["open"])
            ):
                side = "SELL"
                stop = max(float(prior["high"]), float(row["high"])) + 0.10 * atr
            elif (
                lower_extreme
                and float(row["close"]) >= float(prior["high"]) - confirm_fraction * prior_range
                and float(row["close"]) > float(row["open"])
            ):
                side = "BUY"
                stop = min(float(prior["low"]), float(row["low"])) - 0.10 * atr
            else:
                continue
            nxt = _entry_after(bars_1m, ts, 5)
            if nxt is None:
                continue
            entry_ts, entry = nxt
            risk = abs(entry - stop)
            reward = (
                entry - float(row["vwap"])
                if side == "SELL"
                else float(row["vwap"]) - entry
            )
            if risk <= 0 or reward / risk < float(spec["min_reward_r"]):
                continue
            out.append(
                Candidate(
                    family="session_extreme_two_bar_reversal",
                    variant=str(spec["id"]),
                    source_id="vwap_rejection",
                    symbol=symbol,
                    side=side,
                    signal_ts=str(ts),
                    entry_ts=str(entry_ts),
                    entry=entry,
                    stop=stop,
                    target_r=min(1.6, reward / risk),
                    forced_exit_ts=str(_clock(day, close_clock)),
                    notes="New session extreme far from VWAP, followed by a separate completed reversal bar",
                )
            )
            break
    return out


def generate_weekly_value_area_failed_auction(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Encode the pre-registered outside/reentry/retest weekly auction sequence."""
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    weekly_parts: dict[tuple[int, int], list[pd.DataFrame]] = {}
    for day, rth in rth_days.items():
        iso = day.date().isocalendar()
        weekly_parts.setdefault((iso.year, iso.week), []).append(rth)
    weeks = sorted(weekly_parts)
    out: list[Candidate] = []
    _open_clock, close_clock = _session_clock(symbol)
    for i in range(1, len(weeks)):
        prior_week = pd.concat(weekly_parts[weeks[i - 1]]).sort_index()
        current = pd.concat(weekly_parts[weeks[i]]).sort_index()
        profile = _volume_profile_mean_std(prior_week)
        if profile is None:
            continue
        poc, profile_std = profile
        value_high, value_low = poc + profile_std, poc - profile_std
        side: str | None = None
        extreme: float | None = None
        reentered = False
        for ts, row in current.iterrows():
            atr = float(row["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue
            if side is None:
                if float(row["close"]) > value_high + float(spec["outside_atr"]) * atr:
                    side, extreme = "SELL", float(row["high"])
                elif float(row["close"]) < value_low - float(spec["outside_atr"]) * atr:
                    side, extreme = "BUY", float(row["low"])
                continue
            if side == "SELL":
                extreme = max(float(extreme), float(row["high"]))
                if not reentered:
                    reentered = float(row["close"]) < value_high
                    continue
                touches = float(row["high"]) >= value_high - float(spec["retest_atr"]) * atr
                confirms = touches and float(row["close"]) < value_high and float(row["close"]) < float(row["open"])
                stop = float(extreme) + 0.10 * atr
            else:
                extreme = min(float(extreme), float(row["low"]))
                if not reentered:
                    reentered = float(row["close"]) > value_low
                    continue
                touches = float(row["low"]) <= value_low + float(spec["retest_atr"]) * atr
                confirms = touches and float(row["close"]) > value_low and float(row["close"]) > float(row["open"])
                stop = float(extreme) - 0.10 * atr
            if not confirms:
                continue
            nxt = _entry_after(bars_1m, pd.Timestamp(ts), 5)
            if nxt is None:
                break
            entry_ts, entry = nxt
            risk = abs(entry - stop)
            reward = entry - poc if side == "SELL" else poc - entry
            if risk <= 0 or reward / risk < float(spec["min_reward_r"]):
                break
            force_day = pd.Timestamp(current.index[-1]).normalize()
            out.append(
                Candidate(
                    family="weekly_value_area_failed_auction",
                    variant=str(spec["id"]),
                    source_id="weekly_failed_auction",
                    symbol=symbol,
                    side=side,
                    signal_ts=str(ts),
                    entry_ts=str(entry_ts),
                    entry=entry,
                    stop=stop,
                    target_r=min(1.6, reward / risk),
                    forced_exit_ts=str(_clock(force_day, close_clock)),
                    notes="Prior-week value area; outside close, reentry, then separate boundary retest toward POC",
                )
            )
            break
    return out


def generate_value_area_80_rule_rotation(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Test the classic outside-open, two-bracket value-area rotation rule."""
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    days = sorted(rth_days)
    out: list[Candidate] = []
    _open_clock, close_clock = _session_clock(symbol)
    for i in range(1, len(days)):
        day = days[i]
        profile = _volume_profile_value_area(rth_days[days[i - 1]], symbol)
        if profile is None:
            continue
        value_low, value_high, poc = profile
        current = rth_days[day]
        first_atr = float(current["atr"].iloc[0])
        current_open = float(current["open"].iloc[0])
        if not np.isfinite(first_atr) or first_atr <= 0:
            continue
        outside = float(spec["minimum_outside_atr"]) * first_atr
        if current_open > value_high + outside:
            side, entry_edge, objective = "SELL", value_high, value_low
        elif current_open < value_low - outside:
            side, entry_edge, objective = "BUY", value_low, value_high
        else:
            continue
        brackets = _resample_complete(current, "30min", base_minutes=5)
        if len(brackets) < 3:
            continue
        accepted: list[tuple[pd.Timestamp, pd.Series]] = []
        for ts, row in brackets.iterrows():
            if str(spec["acceptance"]) == "close":
                inside = value_low < float(row["close"]) < value_high
            else:
                inside = float(row["high"]) > value_low and float(row["low"]) < value_high
            if inside:
                accepted.append((pd.Timestamp(ts), row))
            else:
                accepted = []
            if len(accepted) < 2:
                continue
            first_ts, first_row = accepted[-2]
            second_ts, second_row = accepted[-1]
            if second_ts - first_ts != pd.Timedelta(minutes=30):
                continue
            completed_underlying = current[
                (current.index >= second_ts)
                & (current.index < second_ts + pd.Timedelta(minutes=30))
            ]
            if completed_underlying.empty:
                continue
            atr = float(completed_underlying["atr"].iloc[-1])
            if not np.isfinite(atr) or atr <= 0:
                continue
            nxt = _entry_after(bars_1m, second_ts, 30)
            if nxt is None:
                continue
            entry_ts, entry = nxt
            if side == "SELL":
                stop = max(
                    entry_edge + float(spec["stop_atr"]) * atr,
                    float(first_row["high"]),
                    float(second_row["high"]),
                )
                reward = entry - objective
            else:
                stop = min(
                    entry_edge - float(spec["stop_atr"]) * atr,
                    float(first_row["low"]),
                    float(second_row["low"]),
                )
                reward = objective - entry
            risk = abs(entry - stop)
            if risk <= 0 or reward / risk < float(spec["min_reward_r"]):
                break
            out.append(
                Candidate(
                    family="value_area_80_rule_rotation",
                    variant=str(spec["id"]),
                    source_id="value_area_80_rule",
                    symbol=symbol,
                    side=side,
                    signal_ts=str(second_ts),
                    entry_ts=str(entry_ts),
                    entry=entry,
                    stop=stop,
                    target_r=min(1.6, reward / risk),
                    forced_exit_ts=str(_clock(day, close_clock)),
                    notes=(
                        "Outside RTH open; two consecutive completed 30m brackets accepted "
                        f"inside prior 70% VA; fixed far-edge objective; prior POC={poc:.4f}"
                    ),
                )
            )
            break
    return out


def generate_ny_open_three_bar_continuation(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Conservative 5m adaptation of the public 2m drive/pause/continuation setup."""
    if symbol != "NQ":
        return []
    f = bars_5m.copy()
    rth_days = _rth_day_frames(f, symbol)
    if not rth_days:
        return []
    rth_all = pd.concat([rth_days[day] for day in sorted(rth_days)]).sort_index()
    rth_all["ema9_rth"] = rth_all["close"].ewm(span=9, adjust=False).mean()
    out: list[Candidate] = []
    tick = 0.25
    for day in sorted(rth_days):
        d = rth_all[rth_all.index.normalize() == day]
        start = day + pd.Timedelta(hours=9, minutes=30)
        cutoff = start + pd.Timedelta(minutes=40)
        pattern_bars = d[(d.index >= start) & (d.index < cutoff)]
        if len(pattern_bars) < 3:
            continue
        for i in range(2, len(pattern_bars)):
            previous = pattern_bars.iloc[i - 2]
            strength = pattern_bars.iloc[i - 1]
            pullback = pattern_bars.iloc[i]
            pullback_ts = pd.Timestamp(pattern_bars.index[i])
            long_pattern = (
                float(strength["close"]) > float(previous["high"])
                and float(strength["close"]) > float(strength["ema9_rth"])
                and float(pullback["close"]) < float(pullback["open"])
            )
            short_pattern = (
                float(strength["close"]) < float(previous["low"])
                and float(strength["close"]) < float(strength["ema9_rth"])
                and float(pullback["close"]) > float(pullback["open"])
            )
            if bool(spec.get("pullback_holds_ema")):
                long_pattern = long_pattern and float(pullback["close"]) > float(pullback["ema9_rth"])
                short_pattern = short_pattern and float(pullback["close"]) < float(pullback["ema9_rth"])
            if not long_pattern and not short_pattern:
                continue
            side = "BUY" if long_pattern else "SELL"
            stop_entry = (
                float(pullback["high"]) + tick
                if side == "BUY"
                else float(pullback["low"]) - tick
            )
            stop = (
                float(pullback["low"]) - tick
                if side == "BUY"
                else float(pullback["high"]) + tick
            )
            trigger_start = pullback_ts + pd.Timedelta(minutes=5)
            trigger_end = min(cutoff, trigger_start + pd.Timedelta(minutes=15))
            triggers = bars_1m[(bars_1m.index >= trigger_start) & (bars_1m.index < trigger_end)]
            for trigger_ts, trigger in triggers.iterrows():
                crossed = (
                    float(trigger["high"]) >= stop_entry
                    if side == "BUY"
                    else float(trigger["low"]) <= stop_entry
                )
                if not crossed:
                    continue
                entry = (
                    max(stop_entry, float(trigger["open"]))
                    if side == "BUY"
                    else min(stop_entry, float(trigger["open"]))
                )
                if (side == "BUY" and stop >= entry) or (side == "SELL" and stop <= entry):
                    break
                out.append(
                    Candidate(
                        family="ny_open_three_bar_continuation",
                        variant=str(spec["id"]),
                        source_id="ny_open_three_bar",
                        symbol="NQ",
                        side=side,
                        signal_ts=str(pullback_ts),
                        entry_ts=str(trigger_ts),
                        entry=entry,
                        stop=stop,
                        target_r=1.6,
                        forced_exit_ts=str(day + pd.Timedelta(hours=16)),
                        notes=(
                            "RTH-only EMA9 direction; completed strength bar; opposite-color "
                            "pause; stop-entry on a later bar; same-bar stop-first replay"
                        ),
                    )
                )
                break
    return out


def generate_nq_15m_opening_range_retest(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Encode the published 09:30-09:45 range, break, retest, 11:00 exit."""
    if symbol != "NQ":
        return []
    f = _session_vwap_features(bars_5m)
    rth_days = _rth_day_frames(f, symbol)
    out: list[Candidate] = []
    for day, rth in rth_days.items():
        start = day + pd.Timedelta(hours=9, minutes=30)
        opening_end = day + pd.Timedelta(hours=9, minutes=45)
        search_end = day + pd.Timedelta(hours=10, minutes=45)
        forced_exit = day + pd.Timedelta(hours=11)
        opening = rth[(rth.index >= start) & (rth.index < opening_end)]
        search = rth[(rth.index >= opening_end) & (rth.index < search_end)]
        if len(opening) < 3 or len(search) < 2:
            continue
        range_high = float(opening["high"].max())
        range_low = float(opening["low"].min())
        rows = list(search.iterrows())
        for i, (_break_ts, break_row) in enumerate(rows[:-1]):
            if float(break_row["close"]) > range_high:
                side, boundary = "BUY", range_high
                if bool(spec.get("require_vwap")) and float(break_row["close"]) <= float(break_row["vwap"]):
                    continue
            elif float(break_row["close"]) < range_low:
                side, boundary = "SELL", range_low
                if bool(spec.get("require_vwap")) and float(break_row["close"]) >= float(break_row["vwap"]):
                    continue
            else:
                continue
            for retest_ts, row in rows[i + 1 :]:
                atr = float(row["atr"])
                if not np.isfinite(atr) or atr <= 0:
                    continue
                if side == "BUY":
                    confirms = (
                        float(row["low"]) <= boundary + 0.10 * atr
                        and float(row["close"]) > boundary
                        and float(row["close"]) > float(row["open"])
                    )
                    stop = range_low - 0.10 * atr
                else:
                    confirms = (
                        float(row["high"]) >= boundary - 0.10 * atr
                        and float(row["close"]) < boundary
                        and float(row["close"]) < float(row["open"])
                    )
                    stop = range_high + 0.10 * atr
                if not confirms:
                    continue
                cand = _candidate(
                    bars_1m=bars_1m,
                    signal_ts=pd.Timestamp(retest_ts),
                    signal_minutes=5,
                    family="nq_15m_opening_range_retest",
                    variant=str(spec["id"]),
                    source_id="nq_15m_orb",
                    symbol="NQ",
                    side=side,
                    stop=stop,
                    target_r=1.6,
                    forced_exit_ts=forced_exit,
                    notes="09:30-09:45 wick range; completed close outside; separate retest; opposite-edge stop; 11:00 flat",
                )
                if cand:
                    out.append(cand)
                break
            break
    return out


def generate_nq_premarket_ema_engulfing(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Require 9/20 separation, EMA touch, engulfing confirmation, and volume."""
    if symbol != "NQ":
        return []
    f = bars_5m.copy()
    f["atr"] = _atr(f)
    f["ema9"] = f["close"].ewm(span=9, adjust=False).mean()
    f["ema20"] = f["close"].ewm(span=20, adjust=False).mean()
    out: list[Candidate] = []
    for day, d in f.groupby(f.index.normalize()):
        premarket = d[
            (d.index >= day + pd.Timedelta(hours=7))
            & (d.index < day + pd.Timedelta(hours=9, minutes=25))
        ]
        if len(premarket) < 8:
            continue
        for i in range(5, len(premarket)):
            prior = premarket.iloc[i - 1]
            row = premarket.iloc[i]
            ts = pd.Timestamp(premarket.index[i])
            atr = float(row["atr"])
            if not np.isfinite(atr) or atr <= 0 or float(row["volume"]) <= float(prior["volume"]):
                continue
            separation = abs(float(row["ema9"] - row["ema20"])) / atr
            if separation < float(spec["minimum_separation_atr"]):
                continue
            ema9_slope = float(row["ema9"] - premarket["ema9"].iloc[i - 4])
            bullish_engulf = (
                float(row["close"]) > float(row["open"])
                and float(row["open"]) <= float(prior["close"])
                and float(row["close"]) >= float(prior["open"])
            )
            bearish_engulf = (
                float(row["close"]) < float(row["open"])
                and float(row["open"]) >= float(prior["close"])
                and float(row["close"]) <= float(prior["open"])
            )
            if (
                float(row["ema9"]) > float(row["ema20"])
                and ema9_slope > 0
                and float(prior["low"]) <= float(prior["ema9"]) + 0.10 * atr
                and float(prior["close"]) >= float(prior["ema20"]) - 0.10 * atr
                and bullish_engulf
            ):
                side = "BUY"
                stop = min(float(prior["low"]), float(row["low"])) - 0.10 * atr
            elif (
                float(row["ema9"]) < float(row["ema20"])
                and ema9_slope < 0
                and float(prior["high"]) >= float(prior["ema9"]) - 0.10 * atr
                and float(prior["close"]) <= float(prior["ema20"]) + 0.10 * atr
                and bearish_engulf
            ):
                side = "SELL"
                stop = max(float(prior["high"]), float(row["high"])) + 0.10 * atr
            else:
                continue
            cand = _candidate(
                bars_1m=bars_1m,
                signal_ts=ts,
                signal_minutes=5,
                family="nq_premarket_ema_engulfing",
                variant=str(spec["id"]),
                source_id="premarket_ema_pullback",
                symbol="NQ",
                side=side,
                stop=stop,
                target_r=1.6,
                forced_exit_ts=day + pd.Timedelta(hours=9, minutes=25),
                notes="Research-only dual-EMA trend separation, pullback touch, engulfing confirmation, and higher volume",
            )
            if cand:
                out.append(cand)
    return out


def generate_nq_opening_shock_reversal(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade an unusually large first-30m NQ move only after a completed failure bar."""
    if symbol != "NQ":
        return []
    f = bars_5m.copy()
    f["atr"] = _atr(f)
    day_frames = _rth_day_frames(f, "NQ", minimum_rows=60)
    prior_ranges: list[float] = []
    out: list[Candidate] = []
    for day, rth in day_frames.items():
        range_ref = float(np.median(prior_ranges[-20:])) if len(prior_ranges) >= 10 else np.nan
        prior_ranges.append(float(rth["high"].max() - rth["low"].min()))
        opening = rth.iloc[:6]
        if len(opening) < 6 or not np.isfinite(range_ref) or range_ref <= 0:
            continue
        impulse = float(opening["close"].iloc[-1] - opening["open"].iloc[0])
        if abs(impulse) < float(spec["shock_daily_range"]) * range_ref:
            continue
        opening_high = float(opening["high"].max())
        opening_low = float(opening["low"].min())
        midpoint = (opening_high + opening_low) / 2.0
        for ts, row in rth.iloc[6 : 6 + int(spec["confirmation_bars"])].iterrows():
            atr = float(row["atr"])
            if not np.isfinite(atr) or atr <= 0:
                continue
            if impulse > 0 and float(row["close"]) < midpoint and float(row["close"]) < float(row["open"]):
                side = "SELL"
                stop = opening_high + float(spec["stop_buffer_atr"]) * atr
            elif impulse < 0 and float(row["close"]) > midpoint and float(row["close"]) > float(row["open"]):
                side = "BUY"
                stop = opening_low - float(spec["stop_buffer_atr"]) * atr
            else:
                continue
            cand = _candidate(
                bars_1m=bars_1m,
                signal_ts=pd.Timestamp(ts),
                signal_minutes=5,
                family="nq_opening_shock_reversal",
                variant=str(spec["id"]),
                source_id="opening_shock_reversal",
                symbol="NQ",
                side=side,
                stop=stop,
                target_r=1.6,
                forced_exit_ts=day + pd.Timedelta(hours=12),
                notes="Large first-30m index-futures shock followed by a completed midpoint failure",
            )
            if cand:
                out.append(cand)
            break
    return out


def generate_gap_reject_then_go(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Trade a gap-and-go only after an initial fill attempt fails and reverses."""
    f = bars_5m.copy()
    f["atr"] = _atr(f)
    day_frames = _rth_day_frames(f, symbol, minimum_rows=40)
    prior_close: float | None = None
    prior_ranges: list[float] = []
    out: list[Candidate] = []
    for day, rth in day_frames.items():
        range_ref = float(np.median(prior_ranges[-20:])) if len(prior_ranges) >= 10 else np.nan
        current_open = float(rth["open"].iloc[0])
        if prior_close is not None and np.isfinite(range_ref) and range_ref > 0 and len(rth) >= 6:
            gap = current_open - prior_close
            if abs(gap) >= float(spec["gap_daily_range"]) * range_ref:
                first = rth.iloc[:3]
                confirm = rth.iloc[3:6]
                first_close = float(first["close"].iloc[-1])
                confirm_close = float(confirm["close"].iloc[-1])
                fill = float(spec["minimum_fill_fraction"]) * abs(gap)
                if gap > 0 and first_close <= current_open - fill and confirm_close > current_open:
                    side = "BUY"
                    stop = float(pd.concat([first["low"], confirm["low"]]).min()) - 0.10 * float(confirm["atr"].iloc[-1])
                elif gap < 0 and first_close >= current_open + fill and confirm_close < current_open:
                    side = "SELL"
                    stop = float(pd.concat([first["high"], confirm["high"]]).max()) + 0.10 * float(confirm["atr"].iloc[-1])
                else:
                    side = ""
                    stop = np.nan
                if side and np.isfinite(stop):
                    cand = _candidate(
                        bars_1m=bars_1m,
                        signal_ts=pd.Timestamp(confirm.index[-1]),
                        signal_minutes=5,
                        family="gap_reject_then_go",
                        variant=str(spec["id"]),
                        source_id="gap_regime",
                        symbol=symbol,
                        side=side,
                        stop=float(stop),
                        target_r=1.6,
                        forced_exit_ts=_clock(day, _session_clock(symbol)[1]),
                        notes="Large RTH gap, initial fill attempt, then completed-bar reversal back in gap direction",
                    )
                    if cand:
                        out.append(cand)
        prior_close = float(rth["close"].iloc[-1])
        prior_ranges.append(float(rth["high"].max() - rth["low"].min()))
    return out


def generate_initial_balance_vwap_retest(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Require a compressed one-hour IB, VWAP-aligned break, and successful retest."""
    f = _session_vwap_features(bars_5m)
    f["volume_ref"] = f["volume"].shift(1).rolling(50, min_periods=20).median()
    day_frames = _rth_day_frames(f, symbol, minimum_rows=40)
    prior_ranges: list[float] = []
    out: list[Candidate] = []
    for day, rth in day_frames.items():
        range_ref = float(np.median(prior_ranges[-20:])) if len(prior_ranges) >= 10 else np.nan
        prior_ranges.append(float(rth["high"].max() - rth["low"].min()))
        if len(rth) < 20 or not np.isfinite(range_ref) or range_ref <= 0:
            continue
        initial = rth.iloc[:12]
        ib_high = float(initial["high"].max())
        ib_low = float(initial["low"].min())
        if ib_high - ib_low > float(spec["maximum_ib_daily_range"]) * range_ref:
            continue
        post = rth.iloc[12:36]
        break_side: str | None = None
        break_level = np.nan
        remaining = 0
        for ts, row in post.iterrows():
            atr = float(row["atr"])
            volume_ref = float(row["volume_ref"])
            if not np.isfinite(atr) or atr <= 0 or not np.isfinite(volume_ref) or volume_ref <= 0:
                continue
            if break_side is None:
                enough_volume = float(row["volume"]) >= float(spec["minimum_relative_volume"]) * volume_ref
                if enough_volume and float(row["close"]) > ib_high and float(row["close"]) > float(row["vwap"]):
                    break_side, break_level, remaining = "BUY", ib_high, int(spec["maximum_retest_bars"])
                elif enough_volume and float(row["close"]) < ib_low and float(row["close"]) < float(row["vwap"]):
                    break_side, break_level, remaining = "SELL", ib_low, int(spec["maximum_retest_bars"])
                continue
            remaining -= 1
            depth = float(spec["maximum_retest_depth_atr"]) * atr
            if break_side == "BUY" and float(row["low"]) <= break_level + depth and float(row["close"]) > break_level and float(row["close"]) > float(row["vwap"]):
                stop = min(float(row["low"]), break_level - 0.20 * atr)
            elif break_side == "SELL" and float(row["high"]) >= break_level - depth and float(row["close"]) < break_level and float(row["close"]) < float(row["vwap"]):
                stop = max(float(row["high"]), break_level + 0.20 * atr)
            else:
                if remaining <= 0:
                    break_side = None
                continue
            cand = _candidate(
                bars_1m=bars_1m,
                signal_ts=pd.Timestamp(ts),
                signal_minutes=5,
                family="initial_balance_vwap_retest",
                variant=str(spec["id"]),
                source_id="initial_balance_vwap",
                symbol=symbol,
                side=break_side,
                stop=stop,
                target_r=1.6,
                forced_exit_ts=_clock(day, _session_clock(symbol)[1]),
                notes="Compressed one-hour initial balance; volume/VWAP break; completed successful retest",
            )
            if cand:
                out.append(cand)
            break
    return out


def generate_volume_climax_rejection(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade only wide, extreme-volume bars that close with a strong rejection wick."""
    f = _session_vwap_features(bars_5m)
    f["volume_ref"] = f["volume"].shift(1).rolling(50, min_periods=25).median()
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for ts, row in f.iterrows():
        ts = pd.Timestamp(ts)
        minute = ts.hour * 60 + ts.minute
        end_minute = 13 * 60 if symbol == "CL" else 15 * 60
        if minute < 10 * 60 or minute > end_minute:
            continue
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=2):
            continue
        atr = float(row["atr"])
        volume_ref = float(row["volume_ref"])
        bar_range = float(row["high"] - row["low"])
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(volume_ref) or volume_ref <= 0 or bar_range <= 0:
            continue
        if float(row["volume"]) < float(spec["volume_multiple"]) * volume_ref or bar_range < float(spec["range_atr"]) * atr:
            continue
        close_location = float((row["close"] - row["low"]) / bar_range)
        distance = float(row["close"] - row["vwap"])
        if close_location <= float(spec["edge_fraction"]) and distance >= float(spec["minimum_vwap_atr"]) * atr:
            side, stop = "SELL", float(row["high"]) + 0.10 * atr
        elif close_location >= 1.0 - float(spec["edge_fraction"]) and distance <= -float(spec["minimum_vwap_atr"]) * atr:
            side, stop = "BUY", float(row["low"]) - 0.10 * atr
        else:
            continue
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="volume_climax_rejection",
            variant=str(spec["id"]),
            source_id="volume_rejection",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.6,
            notes="Completed 5m extreme-volume/range bar with rejection close away from session VWAP",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_lunch_vwap_reclaim(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Time-box a morning inventory stretch and require a lunch reversal toward VWAP."""
    f = _session_vwap_features(bars_5m)
    day_frames = _rth_day_frames(f, symbol, minimum_rows=40)
    out: list[Candidate] = []
    for day, rth in day_frames.items():
        lunch_start = day + pd.Timedelta(hours=11 if symbol == "CL" else 11, minutes=30 if symbol != "CL" else 0)
        lunch_end = day + pd.Timedelta(hours=13)
        morning = rth[rth.index < lunch_start]
        lunch = rth[(rth.index >= lunch_start) & (rth.index < lunch_end)]
        if len(morning) < 20 or lunch.empty:
            continue
        morning_z_min = float(pd.to_numeric(morning["vwap_z"], errors="coerce").min())
        morning_z_max = float(pd.to_numeric(morning["vwap_z"], errors="coerce").max())
        for ts, row in lunch.iterrows():
            atr = float(row["atr"])
            z = float(row["vwap_z"])
            if not np.isfinite(atr) or atr <= 0 or not np.isfinite(z):
                continue
            recent = rth.loc[:ts].tail(4)
            if morning_z_min <= -float(spec["morning_stretch_z"]) and z >= -float(spec["reclaim_z"]) and float(row["close"]) > float(row["open"]):
                side = "BUY"
                stop = float(recent["low"].min()) - 0.10 * atr
            elif morning_z_max >= float(spec["morning_stretch_z"]) and z <= float(spec["reclaim_z"]) and float(row["close"]) < float(row["open"]):
                side = "SELL"
                stop = float(recent["high"].max()) + 0.10 * atr
            else:
                continue
            cand = _candidate(
                bars_1m=bars_1m,
                signal_ts=pd.Timestamp(ts),
                signal_minutes=5,
                family="lunch_vwap_reclaim",
                variant=str(spec["id"]),
                source_id="vwap_reversion",
                symbol=symbol,
                side=side,
                stop=stop,
                target_r=1.6,
                forced_exit_ts=_clock(day, _session_clock(symbol)[1]),
                notes="Morning VWAP inventory stretch followed by a completed lunch-session reclaim",
            )
            if cand:
                out.append(cand)
            break
    return out


def generate_two_test_range_breakout(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Break a compact rolling range only after the level was tested at least twice."""
    f = _session_vwap_features(bars_5m)
    f["volume_ref"] = f["volume"].shift(1).rolling(50, min_periods=25).median()
    lookback = int(spec["lookback_bars"])
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in range(max(55, lookback + 1), len(f)):
        ts = pd.Timestamp(f.index[i])
        minute = ts.hour * 60 + ts.minute
        end_minute = 13 * 60 if symbol == "CL" else 15 * 60
        if minute < 10 * 60 or minute > end_minute:
            continue
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=4):
            continue
        row = f.iloc[i]
        prior = f.iloc[i - lookback : i]
        atr = float(row["atr"])
        volume_ref = float(row["volume_ref"])
        if not np.isfinite(atr) or atr <= 0 or not np.isfinite(volume_ref) or volume_ref <= 0:
            continue
        upper = float(prior["high"].max())
        lower = float(prior["low"].min())
        if upper - lower > float(spec["maximum_range_atr"]) * atr:
            continue
        tolerance = float(spec["test_tolerance_atr"]) * atr
        upper_tests = np.flatnonzero(pd.to_numeric(prior["high"], errors="coerce").to_numpy() >= upper - tolerance)
        lower_tests = np.flatnonzero(pd.to_numeric(prior["low"], errors="coerce").to_numpy() <= lower + tolerance)
        enough_volume = float(row["volume"]) >= float(spec["minimum_relative_volume"]) * volume_ref
        break_distance = float(spec["break_atr"]) * atr
        upper_separated = len(upper_tests) >= 2 and int(upper_tests[-1] - upper_tests[0]) >= 3
        lower_separated = len(lower_tests) >= 2 and int(lower_tests[-1] - lower_tests[0]) >= 3
        if upper_separated and enough_volume and float(row["close"]) > upper + break_distance and float(row["close"]) > float(row["vwap"]):
            side, stop = "BUY", upper - 0.50 * atr
        elif lower_separated and enough_volume and float(row["close"]) < lower - break_distance and float(row["close"]) < float(row["vwap"]):
            side, stop = "SELL", lower + 0.50 * atr
        else:
            continue
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="two_test_range_breakout",
            variant=str(spec["id"]),
            source_id="tested_level_break",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.6,
            notes="Compact 5m range, two separated tests, relative-volume break, and VWAP alignment",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_nq_post_settlement_alignment(
    bars_1m: pd.DataFrame,
    bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Test whether a post-settlement distortion plus aligned gap/first-15m persists."""
    if symbol != "NQ":
        return []
    f = bars_5m.copy()
    day_groups = {pd.Timestamp(day): frame for day, frame in f.groupby(f.index.normalize())}
    out: list[Candidate] = []
    previous: dict[str, float] | None = None
    for day in sorted(day_groups):
        frame = day_groups[day]
        rth = frame[(frame.index >= day + pd.Timedelta(hours=9, minutes=30)) & (frame.index < day + pd.Timedelta(hours=16))]
        post = frame[(frame.index >= day + pd.Timedelta(hours=16)) & (frame.index < day + pd.Timedelta(hours=17))]
        if previous is not None and len(rth) >= 3:
            drift = float(previous["post_drift"])
            prior_range = float(previous["rth_range"])
            gap = float(rth["open"].iloc[0] - previous["rth_close"])
            first = rth.iloc[:3]
            first_move = float(first["close"].iloc[-1] - first["open"].iloc[0])
            aligned = np.sign(drift) == np.sign(gap) == np.sign(first_move) and np.sign(drift) != 0
            if (
                aligned
                and prior_range > 0
                and abs(drift) >= float(spec["minimum_post_drift_range"]) * prior_range
                and abs(gap) >= float(spec["minimum_gap_range"]) * prior_range
            ):
                side = "BUY" if drift > 0 else "SELL"
                stop = float(first["low"].min()) if side == "BUY" else float(first["high"].max())
                cand = _candidate(
                    bars_1m=bars_1m,
                    signal_ts=pd.Timestamp(first.index[-1]),
                    signal_minutes=5,
                    family="nq_post_settlement_alignment",
                    variant=str(spec["id"]),
                    source_id="post_settlement_gap",
                    symbol="NQ",
                    side=side,
                    stop=stop,
                    target_r=1.6,
                    forced_exit_ts=day + pd.Timedelta(hours=12),
                    notes="Prior post-settlement distortion, next RTH gap, and first-15m move all aligned",
                )
                if cand:
                    out.append(cand)
        if len(rth) >= 60 and len(post) >= 6:
            previous = {
                "rth_close": float(rth["close"].iloc[-1]),
                "rth_range": float(rth["high"].max() - rth["low"].min()),
                "post_drift": float(post["close"].iloc[-1] - post["open"].iloc[0]),
            }
    return out


def generate_bvc_cvd_divergence(
    bars_1m: pd.DataFrame,
    _bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade a six-bar price/estimated-flow disagreement at a VWAP stretch."""
    f = _microstructure_proxy_5m(bars_1m)
    price_move = f["price6_atr_proxy"]
    flow = f["flow6_proxy"]
    distance = f["vwap_distance_atr_proxy"]
    valid = f[["atr", "price6_atr_proxy", "flow6_proxy", "vwap_distance_atr_proxy"]].notna().all(axis=1) & (f["atr"] > 0)
    up = (
        (price_move >= float(spec["minimum_price_atr"]))
        & (flow <= -float(spec["minimum_opposite_flow"]))
        & (distance >= float(spec["minimum_vwap_atr"]))
    )
    down = (
        (price_move <= -float(spec["minimum_price_atr"]))
        & (flow >= float(spec["minimum_opposite_flow"]))
        & (distance <= -float(spec["minimum_vwap_atr"]))
    )
    mask = valid & _micro_session_mask(f, symbol) & (up | down)
    mask.iloc[:500] = False
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in np.flatnonzero(mask.to_numpy()):
        ts = pd.Timestamp(f.index[i])
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=2):
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        recent = f.iloc[i - 5 : i + 1]
        if bool(up.iloc[i]):
            side = "SELL"
            stop = float(recent["high"].max()) + 0.10 * atr
        else:
            side = "BUY"
            stop = float(recent["low"].min()) - 0.10 * atr
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="bvc_cvd_divergence",
            variant=str(spec["id"]),
            source_id="cvd_absorption",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.6,
            notes="OHLCV-derived six-bar BVC pressure diverges from price at a session-VWAP stretch",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_bvc_absorption_reversal(
    bars_1m: pd.DataFrame,
    _bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade estimated aggressive pressure that produces little directional progress."""
    f = _microstructure_proxy_5m(bars_1m)
    valid = f[
        [
            "atr",
            "pressure_z_proxy",
            "volume_z_proxy",
            "efficiency_proxy",
            "close_location_proxy",
            "vwap_distance_atr_proxy",
        ]
    ].notna().all(axis=1) & (f["atr"] > 0)
    common = (
        (f["volume_z_proxy"] >= float(spec["minimum_volume_z"]))
        & (f["efficiency_proxy"] <= float(spec["maximum_efficiency"]))
    )
    up = (
        (f["pressure_z_proxy"] >= float(spec["minimum_pressure_z"]))
        & (f["close_location_proxy"] <= float(spec["maximum_rejection_location"]))
        & (f["vwap_distance_atr_proxy"] >= float(spec["minimum_vwap_atr"]))
    )
    down = (
        (f["pressure_z_proxy"] <= -float(spec["minimum_pressure_z"]))
        & (f["close_location_proxy"] >= 1.0 - float(spec["maximum_rejection_location"]))
        & (f["vwap_distance_atr_proxy"] <= -float(spec["minimum_vwap_atr"]))
    )
    mask = valid & common & _micro_session_mask(f, symbol) & (up | down)
    mask.iloc[:500] = False
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in np.flatnonzero(mask.to_numpy()):
        ts = pd.Timestamp(f.index[i])
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=2):
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        if bool(up.iloc[i]):
            side, stop = "SELL", float(row["high"]) + 0.10 * atr
        else:
            side, stop = "BUY", float(row["low"]) - 0.10 * atr
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="bvc_absorption_reversal",
            variant=str(spec["id"]),
            source_id="bulk_volume_classification",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.6,
            notes="BVC pressure/volume extreme with low efficiency and rejection away from VWAP; proxy, not true delta",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_bvc_pressure_breakout(
    bars_1m: pd.DataFrame,
    _bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Follow an efficient range break when estimated pressure and volume agree."""
    f = _microstructure_proxy_5m(bars_1m)
    valid = f[
        [
            "atr",
            "pressure_z_proxy",
            "volume_z_proxy",
            "efficiency_proxy",
            "prior_high12_proxy",
            "prior_low12_proxy",
            "vwap_distance_atr_proxy",
        ]
    ].notna().all(axis=1) & (f["atr"] > 0)
    common = (
        (f["volume_z_proxy"] >= float(spec["minimum_volume_z"]))
        & (f["efficiency_proxy"] >= float(spec["minimum_efficiency"]))
    )
    up = (
        (f["pressure_z_proxy"] >= float(spec["minimum_pressure_z"]))
        & (f["close"] > f["prior_high12_proxy"])
        & (f["vwap_distance_atr_proxy"] > 0)
    )
    down = (
        (f["pressure_z_proxy"] <= -float(spec["minimum_pressure_z"]))
        & (f["close"] < f["prior_low12_proxy"])
        & (f["vwap_distance_atr_proxy"] < 0)
    )
    mask = valid & common & _micro_session_mask(f, symbol) & (up | down)
    mask.iloc[:500] = False
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in np.flatnonzero(mask.to_numpy()):
        ts = pd.Timestamp(f.index[i])
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=3):
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        prior_high = float(row["prior_high12_proxy"])
        prior_low = float(row["prior_low12_proxy"])
        if bool(up.iloc[i]):
            side, stop = "BUY", max(prior_high - 0.50 * atr, float(row["low"]) - 0.10 * atr)
        else:
            side, stop = "SELL", min(prior_low + 0.50 * atr, float(row["high"]) + 0.10 * atr)
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="bvc_pressure_breakout",
            variant=str(spec["id"]),
            source_id="order_flow_price_impact",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.6,
            notes="Efficient 12-bar break with aligned BVC pressure, relative volume, and session VWAP",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_vpin_failed_extension(
    bars_1m: pd.DataFrame,
    _bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade a failed range extension only during an unusually toxic proxy state."""
    f = _microstructure_proxy_5m(bars_1m)
    valid = f[
        [
            "atr",
            "toxicity_proxy",
            "toxicity_q90_proxy",
            "prior_high12_proxy",
            "prior_low12_proxy",
            "close_location_proxy",
        ]
    ].notna().all(axis=1) & (f["atr"] > 0)
    toxic = f["toxicity_proxy"] >= float(spec["toxicity_quantile_multiplier"]) * f["toxicity_q90_proxy"]
    up = (
        (f["high"] > f["prior_high12_proxy"])
        & (f["close"] < f["prior_high12_proxy"])
        & (f["close_location_proxy"] <= float(spec["edge_fraction"]))
    )
    down = (
        (f["low"] < f["prior_low12_proxy"])
        & (f["close"] > f["prior_low12_proxy"])
        & (f["close_location_proxy"] >= 1.0 - float(spec["edge_fraction"]))
    )
    mask = valid & toxic & _micro_session_mask(f, symbol) & (up | down)
    mask.iloc[:500] = False
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in np.flatnonzero(mask.to_numpy()):
        ts = pd.Timestamp(f.index[i])
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=3):
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        if bool(up.iloc[i]):
            side, stop = "SELL", float(row["high"]) + 0.10 * atr
        else:
            side, stop = "BUY", float(row["low"]) - 0.10 * atr
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="vpin_failed_extension",
            variant=str(spec["id"]),
            source_id="vpin_futures",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.6,
            notes="VPIN-style OHLCV toxicity proxy plus completed failed 12-bar extension",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


def generate_impact_shock_reversal(
    bars_1m: pd.DataFrame,
    _bars_5m: pd.DataFrame,
    symbol: str,
    spec: dict[str, Any],
) -> list[Candidate]:
    """Fade a high price-impact liquidity shock only after an extreme rejection."""
    f = _microstructure_proxy_5m(bars_1m)
    valid = f[
        [
            "atr",
            "impact_z_proxy",
            "range_atr_proxy",
            "close_location_proxy",
            "prior_high12_proxy",
            "prior_low12_proxy",
        ]
    ].notna().all(axis=1) & (f["atr"] > 0)
    common = (
        (f["impact_z_proxy"] >= float(spec["minimum_impact_z"]))
        & (f["range_atr_proxy"] >= float(spec["minimum_range_atr"]))
    )
    up = (
        (f["high"] > f["prior_high12_proxy"])
        & (f["close_location_proxy"] <= float(spec["edge_fraction"]))
    )
    down = (
        (f["low"] < f["prior_low12_proxy"])
        & (f["close_location_proxy"] >= 1.0 - float(spec["edge_fraction"]))
    )
    mask = valid & common & _micro_session_mask(f, symbol) & (up | down)
    mask.iloc[:500] = False
    out: list[Candidate] = []
    last_signal: pd.Timestamp | None = None
    for i in np.flatnonzero(mask.to_numpy()):
        ts = pd.Timestamp(f.index[i])
        if last_signal is not None and ts - last_signal < pd.Timedelta(hours=3):
            continue
        row = f.iloc[i]
        atr = float(row["atr"])
        if bool(up.iloc[i]):
            side, stop = "SELL", float(row["high"]) + 0.10 * atr
        else:
            side, stop = "BUY", float(row["low"]) - 0.10 * atr
        cand = _candidate(
            bars_1m=bars_1m,
            signal_ts=ts,
            signal_minutes=5,
            family="impact_shock_reversal",
            variant=str(spec["id"]),
            source_id="order_flow_practice",
            symbol=symbol,
            side=side,
            stop=stop,
            target_r=1.6,
            notes="High OHLCV price-impact proxy, wide bar, and completed rejection beyond a 12-bar extreme",
        )
        if cand:
            out.append(cand)
            last_signal = ts
    return out


FAMILY_SPECS: tuple[tuple[str, Generator, tuple[dict[str, Any], ...]], ...] = (
    (
        "vwap_band_reentry",
        generate_vwap_band_reentry,
        (
            {"id": "z2_re1_flat035", "z_extreme": 2.0, "reentry_z": 1.0, "slope_atr": 0.35},
            {"id": "z25_re125_flat025", "z_extreme": 2.5, "reentry_z": 1.25, "slope_atr": 0.25},
        ),
    ),
    (
        "atr_rsi_failure_reversion",
        generate_atr_rsi_failure,
        (
            {"id": "stretch15", "stretch_atr": 1.5},
            {"id": "stretch20", "stretch_atr": 2.0},
        ),
    ),
    (
        "intraday_capitulation_reversal",
        generate_capitulation_reversal,
        (
            {"id": "bb20_20_rsi2", "band_std": 2.0},
            {"id": "bb20_25_rsi2", "band_std": 2.5},
        ),
    ),
    (
        "trend_capitulation_reclaim",
        generate_trend_capitulation_reclaim,
        (
            {"id": "bb20_20", "band_std": 2.0},
            {"id": "bb20_25", "band_std": 2.5},
        ),
    ),
    (
        "opening_drive_pullback",
        generate_opening_drive_pullback,
        (
            {"id": "impulse050", "impulse_atr": 0.50},
            {"id": "impulse075", "impulse_atr": 0.75},
        ),
    ),
    (
        "balanced_value_area_reversion",
        generate_balanced_value_area_reversion,
        (
            {
                "id": "value3_balance35",
                "lookback_days": 3,
                "max_efficiency": 0.35,
                "min_overlap": 0.20,
                "profile_proximity_atr": 0.75,
                "max_vwap_slope_atr": 0.40,
                "pierce_atr": 0.0,
                "min_reward_r": 1.0,
            },
            {
                "id": "value5_balance25",
                "lookback_days": 5,
                "max_efficiency": 0.25,
                "min_overlap": 0.30,
                "profile_proximity_atr": 0.60,
                "max_vwap_slope_atr": 0.30,
                "pierce_atr": 0.10,
                "min_reward_r": 1.2,
            },
        ),
    ),
    (
        "daily_ibs_capitulation_reversion",
        generate_daily_ibs_capitulation_reversion,
        (
            {
                "id": "ibs30_excursion25_stop050",
                "excursion_factor": 2.5,
                "ibs_max": 0.30,
                "stop_pct": 0.005,
                "min_target_r": 1.0,
                "above_sma200": False,
            },
            {
                "id": "ibs25_excursion25_trend_stop050",
                "excursion_factor": 2.5,
                "ibs_max": 0.25,
                "stop_pct": 0.005,
                "min_target_r": 1.0,
                "above_sma200": True,
            },
        ),
    ),
    (
        "intraday_open_to_close_momentum",
        generate_intraday_momentum,
        (
            {"id": "impulse010", "min_impulse_atr": 0.10, "high_volume": False},
            {"id": "impulse010_highvol", "min_impulse_atr": 0.10, "high_volume": True},
            {"id": "impulse020_highvol", "min_impulse_atr": 0.20, "high_volume": True},
        ),
    ),
    (
        "london_range_sweep_reversal",
        generate_london_sweep_reversal,
        (
            {"id": "pierce000", "pierce_atr": 0.0},
            {"id": "pierce010", "pierce_atr": 0.10},
        ),
    ),
    (
        "initial_balance_failed_break",
        generate_initial_balance_failed_break,
        (
            {"id": "pierce000", "pierce_atr": 0.0, "flat_vwap": False},
            {"id": "pierce010_flat", "pierce_atr": 0.10, "flat_vwap": True},
        ),
    ),
    (
        "overnight_gap_reversion",
        generate_overnight_gap_reversion,
        (
            {"id": "gap030", "gap_atr": 0.30},
            {"id": "gap050", "gap_atr": 0.50},
        ),
    ),
    (
        "volatility_compression_breakout",
        generate_compression_breakout,
        (
            {"id": "compress40", "lookback": 40},
            {"id": "compress80", "lookback": 80},
        ),
    ),
    (
        "donchian_trend_breakout",
        generate_donchian_trend,
        (
            {"id": "donchian20_stop10", "lookback": 20, "stop_atr": 1.0},
            {"id": "donchian40_stop15", "lookback": 40, "stop_atr": 1.5},
        ),
    ),
    (
        "prior_day_level_failure",
        generate_prior_day_level_failure,
        (
            {
                "id": "pierce000_close40",
                "pierce_atr": 0.0,
                "max_close_location": 0.40,
                "min_reward_r": 1.0,
            },
            {
                "id": "pierce010_close35",
                "pierce_atr": 0.10,
                "max_close_location": 0.35,
                "min_reward_r": 1.1,
            },
        ),
    ),
    (
        "opening_range_retest_continuation",
        generate_opening_range_retest_continuation,
        (
            {
                "id": "or30_break05_depth35",
                "range_minutes": 30,
                "break_atr": 0.05,
                "min_rvol": 1.0,
                "max_retest_bars": 6,
                "max_depth_atr": 0.35,
            },
            {
                "id": "or60_break05_depth35",
                "range_minutes": 60,
                "break_atr": 0.05,
                "min_rvol": 1.0,
                "max_retest_bars": 6,
                "max_depth_atr": 0.35,
            },
        ),
    ),
    (
        "opening_range_midpoint_continuation",
        generate_opening_range_midpoint_continuation,
        (
            {
                "id": "or30_impulse50_depth25",
                "range_minutes": 30,
                "impulse_atr": 0.50,
                "max_depth_atr": 0.25,
                "min_reward_r": 1.0,
            },
            {
                "id": "or60_impulse50_depth25",
                "range_minutes": 60,
                "impulse_atr": 0.50,
                "max_depth_atr": 0.25,
                "min_reward_r": 1.0,
            },
        ),
    ),
    (
        "conditional_overnight_reversal",
        generate_conditional_overnight_reversal,
        (
            {
                "id": "same_sign_gap030_prior015",
                "gap_atr": 0.30,
                "prior_return_atr": 0.15,
                "exclude_monday": False,
                "min_reward_r": 1.0,
            },
            {
                "id": "same_sign_gap050_prior025_exmon",
                "gap_atr": 0.50,
                "prior_return_atr": 0.25,
                "exclude_monday": True,
                "min_reward_r": 1.1,
            },
        ),
    ),
    (
        "value_area_breakout_continuation",
        generate_value_area_breakout_continuation,
        (
            {
                "id": "break05_depth25",
                "break_atr": 0.05,
                "max_retest_bars": 6,
                "max_depth_atr": 0.25,
            },
            {
                "id": "break10_depth50",
                "break_atr": 0.10,
                "max_retest_bars": 6,
                "max_depth_atr": 0.50,
            },
        ),
    ),
    (
        "overnight_range_break_retest",
        generate_overnight_range_break_retest,
        (
            {
                "id": "break05_depth35",
                "break_atr": 0.05,
                "max_retest_bars": 6,
                "max_depth_atr": 0.35,
            },
            {
                "id": "break10_depth25",
                "break_atr": 0.10,
                "max_retest_bars": 4,
                "max_depth_atr": 0.25,
            },
        ),
    ),
    (
        "session_extreme_two_bar_reversal",
        generate_session_extreme_two_bar_reversal,
        (
            {
                "id": "vwap10_confirm35",
                "min_vwap_distance_atr": 1.0,
                "confirm_fraction": 0.35,
                "min_reward_r": 1.0,
            },
            {
                "id": "vwap15_confirm25",
                "min_vwap_distance_atr": 1.5,
                "confirm_fraction": 0.25,
                "min_reward_r": 1.1,
            },
        ),
    ),
    (
        "weekly_value_area_failed_auction",
        generate_weekly_value_area_failed_auction,
        (
            {
                "id": "outside00_retest10",
                "outside_atr": 0.0,
                "retest_atr": 0.10,
                "min_reward_r": 1.0,
            },
            {
                "id": "outside10_retest05",
                "outside_atr": 0.10,
                "retest_atr": 0.05,
                "min_reward_r": 1.1,
            },
        ),
    ),
    (
        "value_area_80_rule_rotation",
        generate_value_area_80_rule_rotation,
        (
            {
                "id": "two_closes_stop025",
                "acceptance": "close",
                "minimum_outside_atr": 0.0,
                "stop_atr": 0.25,
                "min_reward_r": 1.0,
            },
            {
                "id": "two_overlaps_outside010",
                "acceptance": "overlap",
                "minimum_outside_atr": 0.10,
                "stop_atr": 0.25,
                "min_reward_r": 1.0,
            },
        ),
    ),
    (
        "ny_open_three_bar_continuation",
        generate_ny_open_three_bar_continuation,
        (
            {"id": "drive_pause_break", "pullback_holds_ema": False},
            {"id": "drive_pause_break_hold9", "pullback_holds_ema": True},
        ),
    ),
    (
        "nq_15m_opening_range_retest",
        generate_nq_15m_opening_range_retest,
        (
            {"id": "opposite_edge_stop", "require_vwap": False},
            {"id": "opposite_edge_stop_vwap", "require_vwap": True},
        ),
    ),
    (
        "nq_premarket_ema_engulfing",
        generate_nq_premarket_ema_engulfing,
        (
            {"id": "sep010", "minimum_separation_atr": 0.10},
            {"id": "sep020", "minimum_separation_atr": 0.20},
        ),
    ),
    (
        "nq_opening_shock_reversal",
        generate_nq_opening_shock_reversal,
        (
            {"id": "shock40_confirm4", "shock_daily_range": 0.40, "confirmation_bars": 4, "stop_buffer_atr": 0.10},
            {"id": "shock60_confirm3", "shock_daily_range": 0.60, "confirmation_bars": 3, "stop_buffer_atr": 0.15},
        ),
    ),
    (
        "gap_reject_then_go",
        generate_gap_reject_then_go,
        (
            {"id": "gap25_fill20", "gap_daily_range": 0.25, "minimum_fill_fraction": 0.20},
            {"id": "gap40_fill30", "gap_daily_range": 0.40, "minimum_fill_fraction": 0.30},
        ),
    ),
    (
        "initial_balance_vwap_retest",
        generate_initial_balance_vwap_retest,
        (
            {
                "id": "ib80_rvol10_depth25",
                "maximum_ib_daily_range": 0.80,
                "minimum_relative_volume": 1.0,
                "maximum_retest_bars": 4,
                "maximum_retest_depth_atr": 0.25,
            },
            {
                "id": "ib60_rvol12_depth20",
                "maximum_ib_daily_range": 0.60,
                "minimum_relative_volume": 1.2,
                "maximum_retest_bars": 3,
                "maximum_retest_depth_atr": 0.20,
            },
        ),
    ),
    (
        "volume_climax_rejection",
        generate_volume_climax_rejection,
        (
            {"id": "vol20_range15_edge25", "volume_multiple": 2.0, "range_atr": 1.5, "edge_fraction": 0.25, "minimum_vwap_atr": 0.50},
            {"id": "vol30_range20_edge20", "volume_multiple": 3.0, "range_atr": 2.0, "edge_fraction": 0.20, "minimum_vwap_atr": 0.75},
        ),
    ),
    (
        "lunch_vwap_reclaim",
        generate_lunch_vwap_reclaim,
        (
            {"id": "stretch20_reclaim075", "morning_stretch_z": 2.0, "reclaim_z": 0.75},
            {"id": "stretch25_reclaim050", "morning_stretch_z": 2.5, "reclaim_z": 0.50},
        ),
    ),
    (
        "two_test_range_breakout",
        generate_two_test_range_breakout,
        (
            {
                "id": "look24_range40_rvol12",
                "lookback_bars": 24,
                "maximum_range_atr": 4.0,
                "test_tolerance_atr": 0.15,
                "minimum_relative_volume": 1.2,
                "break_atr": 0.05,
            },
            {
                "id": "look36_range50_rvol15",
                "lookback_bars": 36,
                "maximum_range_atr": 5.0,
                "test_tolerance_atr": 0.10,
                "minimum_relative_volume": 1.5,
                "break_atr": 0.10,
            },
        ),
    ),
    (
        "nq_post_settlement_alignment",
        generate_nq_post_settlement_alignment,
        (
            {"id": "drift05_gap10", "minimum_post_drift_range": 0.05, "minimum_gap_range": 0.10},
            {"id": "drift10_gap20", "minimum_post_drift_range": 0.10, "minimum_gap_range": 0.20},
        ),
    ),
    (
        "bvc_cvd_divergence",
        generate_bvc_cvd_divergence,
        (
            {"id": "price050_flow15_vwap050", "minimum_price_atr": 0.50, "minimum_opposite_flow": 0.15, "minimum_vwap_atr": 0.50},
            {"id": "price075_flow20_vwap075", "minimum_price_atr": 0.75, "minimum_opposite_flow": 0.20, "minimum_vwap_atr": 0.75},
        ),
    ),
    (
        "bvc_absorption_reversal",
        generate_bvc_absorption_reversal,
        (
            {
                "id": "pressure20_volume10_eff35",
                "minimum_pressure_z": 2.0,
                "minimum_volume_z": 1.0,
                "maximum_efficiency": 0.35,
                "maximum_rejection_location": 0.55,
                "minimum_vwap_atr": 0.50,
            },
            {
                "id": "pressure25_volume15_eff25",
                "minimum_pressure_z": 2.5,
                "minimum_volume_z": 1.5,
                "maximum_efficiency": 0.25,
                "maximum_rejection_location": 0.50,
                "minimum_vwap_atr": 0.75,
            },
        ),
    ),
    (
        "bvc_pressure_breakout",
        generate_bvc_pressure_breakout,
        (
            {"id": "pressure20_volume10_eff60", "minimum_pressure_z": 2.0, "minimum_volume_z": 1.0, "minimum_efficiency": 0.60},
            {"id": "pressure25_volume15_eff70", "minimum_pressure_z": 2.5, "minimum_volume_z": 1.5, "minimum_efficiency": 0.70},
        ),
    ),
    (
        "vpin_failed_extension",
        generate_vpin_failed_extension,
        (
            {"id": "toxicity_q90_edge35", "toxicity_quantile_multiplier": 1.0, "edge_fraction": 0.35},
            {"id": "toxicity_q90x105_edge25", "toxicity_quantile_multiplier": 1.05, "edge_fraction": 0.25},
        ),
    ),
    (
        "impact_shock_reversal",
        generate_impact_shock_reversal,
        (
            {"id": "impact20_range15_edge30", "minimum_impact_z": 2.0, "minimum_range_atr": 1.5, "edge_fraction": 0.30},
            {"id": "impact30_range20_edge20", "minimum_impact_z": 3.0, "minimum_range_atr": 2.0, "edge_fraction": 0.20},
        ),
    ),
)


def _simulate_candidate(
    cand: Candidate,
    bars_1m: pd.DataFrame,
    *,
    maximum_hold_minutes: int = 24 * 60,
) -> dict[str, Any] | None:
    idx = bars_1m.index
    entry_ts = pd.Timestamp(cand.entry_ts)
    if entry_ts.tzinfo is None:
        entry_ts = entry_ts.tz_localize(idx.tz)
    else:
        entry_ts = entry_ts.tz_convert(idx.tz)
    start = int(idx.searchsorted(entry_ts, side="left"))
    if start >= len(idx):
        return None
    forced = pd.Timestamp(cand.forced_exit_ts) if cand.forced_exit_ts else entry_ts + pd.Timedelta(minutes=maximum_hold_minutes)
    if forced.tzinfo is None:
        forced = forced.tz_localize(idx.tz)
    else:
        forced = forced.tz_convert(idx.tz)
    end = min(len(idx), max(start + 1, int(idx.searchsorted(forced, side="right"))))
    entry = float(cand.entry)
    initial_stop = float(cand.stop)
    side = cand.side.upper()
    risk = abs(entry - initial_stop)
    if risk <= 1e-12:
        return None
    target = entry + cand.target_r * risk if side == "BUY" else entry - cand.target_r * risk
    tp1 = entry + risk if side == "BUY" else entry - risk
    stop = initial_stop
    banked_r = 0.0
    remaining = 1.0
    tp1_done = False
    peak_r = 0.0
    raw_r: float | None = None
    exit_ts = entry_ts
    exit_reason = "forced_exit"
    for j in range(start, end):
        row = bars_1m.iloc[j]
        o, h, l, c = map(float, (row["open"], row["high"], row["low"], row["close"]))
        stop_hit = l <= stop if side == "BUY" else h >= stop
        target_hit = h >= target if side == "BUY" else l <= target
        if stop_hit:
            fill = min(stop, o) if side == "BUY" else max(stop, o)
            runner = (fill - entry) / risk if side == "BUY" else (entry - fill) / risk
            raw_r = banked_r + remaining * runner
            exit_ts = pd.Timestamp(idx[j])
            exit_reason = "stop"
            break
        if target_hit:
            raw_r = banked_r + remaining * cand.target_r
            exit_ts = pd.Timestamp(idx[j])
            exit_reason = "target"
            break
        if not tp1_done:
            tp1_hit = h >= tp1 if side == "BUY" else l <= tp1
            if tp1_hit:
                banked_r = 0.5
                remaining = 0.5
                tp1_done = True
                stop = entry
                continue
        favorable_r = (h - entry) / risk if side == "BUY" else (entry - l) / risk
        peak_r = max(peak_r, favorable_r)
        stop_r = (stop - entry) / risk if side == "BUY" else (entry - stop) / risk
        new_stop_r = stop_r
        if favorable_r >= 0.75:
            new_stop_r = max(new_stop_r, 0.0)
        if favorable_r / cand.target_r >= 0.70:
            new_stop_r = max(new_stop_r, cand.target_r * 0.50)
        if peak_r >= 1.0:
            new_stop_r = max(new_stop_r, peak_r - 0.35)
        if new_stop_r > stop_r:
            stop = entry + new_stop_r * risk if side == "BUY" else entry - new_stop_r * risk
        held = (pd.Timestamp(idx[j]) - entry_ts).total_seconds() / 60.0
        mark_r = (c - entry) / risk if side == "BUY" else (entry - c) / risk
        if held >= 120 and mark_r < 0:
            raw_r = banked_r + remaining * mark_r
            exit_ts = pd.Timestamp(idx[j])
            exit_reason = "losing_time_stop"
            break
    if raw_r is None:
        j = max(start, end - 1)
        c = float(bars_1m["close"].iloc[j])
        runner = (c - entry) / risk if side == "BUY" else (entry - c) / risk
        raw_r = banked_r + remaining * runner
        exit_ts = pd.Timestamp(idx[j])
    friction_r = (0.75 / risk) if cand.symbol == "NQ" else 0.07
    return {
        **asdict(cand),
        "exit_ts": str(exit_ts),
        "exit_reason": exit_reason,
        "tp1_done": tp1_done,
        "initial_risk_points": risk,
        "friction_r": friction_r,
        "pnl_r": float(raw_r - friction_r),
    }


def simulate_candidates(candidates: Iterable[Candidate], bars_1m: pd.DataFrame) -> list[dict[str, Any]]:
    """Replay one position per strategy/symbol at a time, matching portfolio reality."""
    out: list[dict[str, Any]] = []
    unavailable_until: pd.Timestamp | None = None
    for cand in sorted(candidates, key=lambda c: c.entry_ts):
        entry_ts = pd.Timestamp(cand.entry_ts)
        if unavailable_until is not None and entry_ts <= unavailable_until:
            continue
        row = _simulate_candidate(cand, bars_1m)
        if row is None:
            continue
        out.append(row)
        unavailable_until = pd.Timestamp(row["exit_ts"])
    return out


def _binomial_upper_tail(wins: int, n: int, p: float = 0.50) -> float:
    if n <= 0:
        return 1.0
    # Directly summing ``comb(n, k)`` overflows once long-history validation
    # produces thousands of trades. scipy's survival function evaluates the
    # same exact binomial tail in stable floating-point arithmetic.
    try:
        from scipy.stats import binom

        return float(binom.sf(wins - 1, n, p))
    except ImportError:
        # The small-sample path remains dependency-free for minimal installs.
        if n > 500:
            raise RuntimeError("scipy is required for binomial tails with n > 500")
        return min(
            1.0,
            sum(comb(n, k) * p**k * (1.0 - p) ** (n - k) for k in range(wins, n + 1)),
        )


def _wilson(wins: int, n: int, z: float = 1.96) -> list[float]:
    if n <= 0:
        return [0.0, 0.0]
    phat = wins / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    margin = z * sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    st = trade_stats([float(r["pnl_r"]) for r in rows], [str(r["entry_ts"]) for r in rows])
    wins = int(sum(float(r["pnl_r"]) > 0 for r in rows))
    st["wr_wilson_95"] = [round(x, 4) for x in _wilson(wins, len(rows))]
    st["p_wr_gt_50"] = round(_binomial_upper_tail(wins, len(rows)), 6)
    return st


def _slice(rows: list[dict[str, Any]], split: SplitLock, period: str) -> list[dict[str, Any]]:
    return [r for r in rows if period_for(r["entry_ts"], split) == period]


def _selection_score(validation: dict[str, Any]) -> tuple[int, float, float, float, int]:
    qualifies = int(
        validation["n"] >= 8
        and validation["pf"] >= 1.0
        and validation["expectancy_r"] > 0
        and validation["anti_cheat_ok"]
    )
    return (
        qualifies,
        float(validation["wr"]),
        float(validation["expectancy_r"]),
        float(validation["pf"]),
        int(validation["n"]),
    )


def _four_block_stability(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: r["entry_ts"])
    blocks = np.array_split(np.arange(len(ordered)), 4)
    return [_stats([ordered[int(i)] for i in block]) for block in blocks if len(block)]


def _desired_gate(all_st: dict[str, Any], val: dict[str, Any], hold: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    checks = (
        (all_st["n"] >= 40, "all_n<40"),
        (all_st["wr"] >= 0.70, "all_WR<70%"),
        (all_st["pf"] >= 1.30, "all_PF<1.30"),
        (all_st["expectancy_r"] >= 0.15, "all_E<0.15R"),
        (val["n"] >= 8, "validation_n<8"),
        (val["pf"] >= 1.0 and val["expectancy_r"] > 0, "validation_edge<=0"),
        (hold["n"] >= 10, "holdout_n<10"),
        (hold["wr"] >= 0.70, "holdout_WR<70%"),
        (hold["pf"] >= 1.20, "holdout_PF<1.20"),
        (hold["expectancy_r"] >= 0.10, "holdout_E<0.10R"),
        (bool(all_st["anti_cheat_ok"]), "anti_cheat_fail"),
    )
    for ok, label in checks:
        if not ok:
            failures.append(label)
    return not failures, failures


def _entry_feature_frame(bars_5m: pd.DataFrame) -> pd.DataFrame:
    f = _session_vwap_features(bars_5m)
    f["ema20"] = f["close"].ewm(span=20, adjust=False).mean()
    f["ema50"] = f["close"].ewm(span=50, adjust=False).mean()
    f["ret_1"] = f["close"].pct_change(1)
    f["ret_3"] = f["close"].pct_change(3)
    f["ret_12"] = f["close"].pct_change(12)
    vol_mean = f["volume"].rolling(50).mean()
    vol_std = f["volume"].rolling(50).std(ddof=0).replace(0, np.nan)
    f["volume_z"] = (f["volume"] - vol_mean) / vol_std
    f["trend_atr"] = (f["ema20"] - f["ema50"]) / f["atr"].replace(0, np.nan)
    f["vwap_dist_atr"] = (f["close"] - f["vwap"]) / f["atr"].replace(0, np.nan)
    f["atr_ratio"] = f["atr_fast"] / f["atr_slow"].replace(0, np.nan)
    return f


def _completed_feature_position(index: pd.DatetimeIndex, entry_ts: pd.Timestamp) -> int:
    """Return the latest 5m feature row completed before the entry instant."""
    asof = entry_ts - pd.Timedelta(minutes=5)
    return int(index.searchsorted(asof, side="right")) - 1


def _meta_rows(
    rows: list[dict[str, Any]],
    feature_frame: pd.DataFrame,
    split: SplitLock,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    idx = feature_frame.index
    for row in rows:
        entry_ts = pd.Timestamp(row["entry_ts"])
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.tz_localize(idx.tz)
        else:
            entry_ts = entry_ts.tz_convert(idx.tz)
        pos = _completed_feature_position(idx, entry_ts)
        if pos < 55:
            continue
        feat = feature_frame.iloc[pos]
        period = period_for(entry_ts, split)
        # One-day label embargo: a trade is usable for model selection only if
        # its exit belongs to the same chronological partition as its entry.
        if period_for(row["exit_ts"], split) != period:
            continue
        side_sign = 1.0 if str(row["side"]).upper() == "BUY" else -1.0
        values = {
            "ret_1": float(feat["ret_1"]) * side_sign,
            "ret_3": float(feat["ret_3"]) * side_sign,
            "ret_12": float(feat["ret_12"]) * side_sign,
            "volume_z": float(feat["volume_z"]),
            "trend_atr": float(feat["trend_atr"]) * side_sign,
            "vwap_dist_atr": float(feat["vwap_dist_atr"]) * side_sign,
            "atr_ratio": float(feat["atr_ratio"]),
            "rsi5_side": (float(feat["rsi5"]) - 50.0) / 50.0 * side_sign,
        }
        if not all(np.isfinite(v) for v in values.values()):
            continue
        records.append(
            {
                **values,
                "family": str(row["family"]),
                "hour": int(entry_ts.hour),
                "weekday": int(entry_ts.dayofweek),
                "period": period,
                "won": int(float(row["pnl_r"]) > 0),
                "pnl_r": float(row["pnl_r"]),
                "entry_ts": str(entry_ts),
                "exit_ts": str(row["exit_ts"]),
            }
        )
    return pd.DataFrame(records)


def _external_meta_rows(
    rows: list[dict[str, Any]],
    feature_frame: pd.DataFrame,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    idx = feature_frame.index
    for row in rows:
        entry_ts = pd.Timestamp(row["entry_ts"])
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.tz_localize(idx.tz)
        else:
            entry_ts = entry_ts.tz_convert(idx.tz)
        pos = _completed_feature_position(idx, entry_ts)
        if pos < 55:
            continue
        feat = feature_frame.iloc[pos]
        side_sign = 1.0 if str(row["side"]).upper() == "BUY" else -1.0
        values = {
            "ret_1": float(feat["ret_1"]) * side_sign,
            "ret_3": float(feat["ret_3"]) * side_sign,
            "ret_12": float(feat["ret_12"]) * side_sign,
            "volume_z": float(feat["volume_z"]),
            "trend_atr": float(feat["trend_atr"]) * side_sign,
            "vwap_dist_atr": float(feat["vwap_dist_atr"]) * side_sign,
            "atr_ratio": float(feat["atr_ratio"]),
            "rsi5_side": (float(feat["rsi5"]) - 50.0) / 50.0 * side_sign,
        }
        if not all(np.isfinite(v) for v in values.values()):
            continue
        records.append(
            {
                **values,
                "family": str(row["family"]),
                "hour": int(entry_ts.hour),
                "weekday": int(entry_ts.dayofweek),
                "won": int(float(row["pnl_r"]) > 0),
                "pnl_r": float(row["pnl_r"]),
                "entry_ts": str(entry_ts),
                "exit_ts": str(row["exit_ts"]),
            }
        )
    return pd.DataFrame(records)


def _run_regime_meta_selector(
    *,
    symbol: str,
    generated_rows: dict[tuple[str, str, str], list[dict[str, Any]]],
    variant_rows: list[dict[str, Any]],
    feature_frame: pd.DataFrame,
    split: SplitLock,
    independent_frames: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Fit one regularized, entry-time-only regime selector per symbol."""
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    # Meta-model base variants are frozen from DEVELOPMENT only. Validation is
    # reserved for the probability threshold; holdout remains final-only.
    picked: list[dict[str, Any]] = []
    for family in sorted({r["family"] for r in variant_rows if r["symbol"] == symbol}):
        pool = [r for r in variant_rows if r["family"] == family and r["symbol"] == symbol]
        picked.append(max(pool, key=lambda r: _selection_score(r["development"])))
    base_rows: list[dict[str, Any]] = []
    for row in picked:
        base_rows.extend(generated_rows[(row["family"], row["variant"], symbol)])
    data = _meta_rows(base_rows, feature_frame, split)
    if data.empty:
        return {"symbol": symbol, "status": "INSUFFICIENT", "reason": "no_feature_rows"}
    train = data[data["period"] == "development"].copy()
    validation = data[data["period"] == "validation"].copy()
    holdout = data[data["period"] == "holdout"].copy()
    if len(train) < 100 or train["won"].nunique() < 2 or len(validation) < 20:
        return {
            "symbol": symbol,
            "status": "INSUFFICIENT",
            "reason": "minimum development/validation rows not met",
            "counts": {"development": len(train), "validation": len(validation), "holdout": len(holdout)},
        }
    numeric = [
        "ret_1",
        "ret_3",
        "ret_12",
        "volume_z",
        "trend_atr",
        "vwap_dist_atr",
        "atr_ratio",
        "rsi5_side",
    ]
    categorical = ["family", "hour", "weekday"]
    model = Pipeline(
        [
            (
                "features",
                ColumnTransformer(
                    [
                        ("numeric", StandardScaler(), numeric),
                        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
                    ]
                ),
            ),
            ("model", LogisticRegression(C=0.50, max_iter=2000, solver="lbfgs")),
        ]
    )
    model.fit(train[numeric + categorical], train["won"])
    validation["probability"] = model.predict_proba(validation[numeric + categorical])[:, 1]
    holdout["probability"] = model.predict_proba(holdout[numeric + categorical])[:, 1] if len(holdout) else []
    train["probability"] = model.predict_proba(train[numeric + categorical])[:, 1]

    def nonoverlap(part: pd.DataFrame, threshold: float) -> pd.DataFrame:
        eligible = part[part["probability"] >= threshold].copy()
        if eligible.empty:
            return eligible
        eligible["_entry"] = pd.to_datetime(eligible["entry_ts"], utc=True)
        eligible["_exit"] = pd.to_datetime(eligible["exit_ts"], utc=True)
        eligible = eligible.sort_values(["_entry", "probability"], ascending=[True, False])
        kept: list[int] = []
        unavailable_until: pd.Timestamp | None = None
        for idx_value, row in eligible.iterrows():
            entry = pd.Timestamp(row["_entry"])
            if unavailable_until is not None and entry <= unavailable_until:
                continue
            kept.append(idx_value)
            unavailable_until = pd.Timestamp(row["_exit"])
        return eligible.loc[kept].drop(columns=["_entry", "_exit"])

    threshold_rows: list[dict[str, Any]] = []
    for threshold in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80):
        part = nonoverlap(validation, threshold)
        st = trade_stats(part["pnl_r"].tolist(), part["entry_ts"].tolist())
        threshold_rows.append({"threshold": threshold, "validation": st})
    viable = [
        row
        for row in threshold_rows
        if row["validation"]["n"] >= 20
        and row["validation"]["pf"] >= 1.0
        and row["validation"]["expectancy_r"] > 0
    ]
    chosen = max(
        viable or threshold_rows,
        key=lambda row: (
            row["validation"]["n"] >= 20,
            row["validation"]["wr"],
            row["validation"]["expectancy_r"],
            row["threshold"],
        ),
    )
    threshold = float(chosen["threshold"])

    def filtered_stats(part: pd.DataFrame) -> dict[str, Any]:
        filt = nonoverlap(part, threshold)
        return _stats(
            [
                {"pnl_r": float(row.pnl_r), "entry_ts": str(row.entry_ts)}
                for row in filt.itertuples()
            ]
        )

    train_st = filtered_stats(train)
    validation_st = filtered_stats(validation)
    holdout_st = filtered_stats(holdout)
    independent: dict[str, Any] = {
        "source": "Yahoo 5m, 60d; frozen Databento model and threshold; no refit",
        "status": "NOT_RUN",
        "stats": _stats([]),
    }
    if independent_frames and len(independent_frames.get("5m", pd.DataFrame())):
        external_rows: list[dict[str, Any]] = []
        family_lookup = {family: (generator, specs) for family, generator, specs in FAMILY_SPECS}
        for picked_row in picked:
            family = str(picked_row["family"])
            variant = str(picked_row["variant"])
            generator, specs = family_lookup[family]
            spec = next(s for s in specs if str(s["id"]) == variant)
            interval = "15m" if family in {
                "intraday_capitulation_reversal",
                "overnight_gap_reversion",
                "volatility_compression_breakout",
                "donchian_trend_breakout",
            } else "5m"
            candidates = generator(
                independent_frames["5m"],
                independent_frames[interval],
                symbol,
                spec,
            )
            external_rows.extend(simulate_candidates(candidates, independent_frames["5m"]))
        external = _external_meta_rows(external_rows, _entry_feature_frame(independent_frames["5m"]))
        if len(external):
            external["probability"] = model.predict_proba(external[numeric + categorical])[:, 1]
            external_filtered = nonoverlap(external, threshold)
            independent = {
                "source": "Yahoo 5m, 60d; frozen Databento model and threshold; no refit",
                "status": "PASS" if len(external_filtered) else "NO_SIGNALS",
                "rows_before_filter": len(external),
                "stats": _stats(
                    [
                        {"pnl_r": float(row.pnl_r), "entry_ts": str(row.entry_ts)}
                        for row in external_filtered.itertuples()
                    ]
                ),
            }
    failures: list[str] = []
    for ok, label in (
        (validation_st["n"] >= 20, "validation_n<20"),
        (validation_st["wr"] >= 0.70, "validation_WR<70%"),
        (validation_st["pf"] >= 1.30, "validation_PF<1.30"),
        (validation_st["expectancy_r"] >= 0.15, "validation_E<0.15R"),
        (holdout_st["n"] >= 20, "holdout_n<20"),
        (holdout_st["wr"] >= 0.70, "holdout_WR<70%"),
        (holdout_st["pf"] >= 1.30, "holdout_PF<1.30"),
        (holdout_st["expectancy_r"] >= 0.15, "holdout_E<0.15R"),
        (independent["stats"]["n"] >= 40, "independent_n<40"),
        (independent["stats"]["wr"] >= 0.70, "independent_WR<70%"),
        (independent["stats"]["pf"] >= 1.30, "independent_PF<1.30"),
        (independent["stats"]["expectancy_r"] >= 0.15, "independent_E<0.15R"),
    ):
        if not ok:
            failures.append(label)
    return {
        "symbol": symbol,
        "status": "PASS" if not failures else "FAIL",
        "source_id": "regime_selector",
        "model": "L2 logistic regression, C=0.50; fixed entry-time features only",
        "base_variants_selected_on_development": [
            {"family": row["family"], "variant": row["variant"]} for row in picked
        ],
        "threshold": threshold,
        "threshold_search_validation_only": threshold_rows,
        "development": train_st,
        "validation": validation_st,
        "holdout": holdout_st,
        "independent_yahoo": independent,
        "gate_failures": failures,
        "counts_before_filter": {
            "development": len(train),
            "validation": len(validation),
            "holdout": len(holdout),
        },
    }


def run_discovery(cache_dir: Path) -> dict[str, Any]:
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    cache_meta: dict[str, Any] = {}
    split_locks: dict[str, SplitLock] = {}
    for symbol in ("NQ", "CL"):
        one, meta = _verified_continuous_cache(cache_dir, symbol)
        one = one.sort_index()
        frames[symbol] = {
            "1m": one,
            "5m": _resample_complete(one, "5min"),
            "15m": _resample_complete(one, "15min"),
        }
        cache_meta[symbol] = {
            "identity": meta.get("databento"),
            "quality": meta.get("quality_audit"),
            "rows_1m": len(one),
            "window": [str(one.index.min()), str(one.index.max())],
        }
        split_locks[symbol] = freeze_split_lock(one)

    yahoo_frames: dict[str, dict[str, pd.DataFrame]] = {}
    for symbol, ticker in (("NQ", "NQ=F"), ("CL", "CL=F")):
        try:
            five = fetch_yahoo(ticker, "5m", "60d").sort_index()
        except Exception:
            five = pd.DataFrame()
        yahoo_frames[symbol] = {
            "5m": five,
            "15m": _resample_complete(five, "15min", base_minutes=5) if len(five) else pd.DataFrame(),
        }

    all_variants: list[dict[str, Any]] = []
    generated_rows: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for family, generator, specs in FAMILY_SPECS:
        for spec in specs:
            for symbol in ("NQ", "CL"):
                interval = "15m" if family in {
                    "intraday_capitulation_reversal",
                    "overnight_gap_reversion",
                    "volatility_compression_breakout",
                    "donchian_trend_breakout",
                } else "5m"
                candidates = generator(frames[symbol]["1m"], frames[symbol][interval], symbol, spec)
                rows = simulate_candidates(candidates, frames[symbol]["1m"])
                generated_rows[(family, str(spec["id"]), symbol)] = rows
                split = split_locks[symbol]
                development = _stats(_slice(rows, split, "development"))
                validation = _stats(_slice(rows, split, "validation"))
                all_variants.append(
                    {
                        "family": family,
                        "variant": str(spec["id"]),
                        "symbol": symbol,
                        "spec": spec,
                        "source_id": FAMILY_SOURCE[family],
                        "development": development,
                        "validation": validation,
                        "selected": False,
                    }
                )

    selected: list[dict[str, Any]] = []
    for family in sorted({r["family"] for r in all_variants}):
        for symbol in ("NQ", "CL"):
            pool = [r for r in all_variants if r["family"] == family and r["symbol"] == symbol]
            best = max(pool, key=lambda r: _selection_score(r["validation"]))
            best["selected"] = True
            rows = generated_rows[(family, best["variant"], symbol)]
            split = split_locks[symbol]
            hold_rows = _slice(rows, split, "holdout")
            all_st = _stats(rows)
            holdout = _stats(hold_rows)
            passes, failures = _desired_gate(all_st, best["validation"], holdout)
            selected.append(
                {
                    **best,
                    "all": all_st,
                    "holdout": holdout,
                    "stability_4_blocks": _four_block_stability(rows),
                    "passes_desired_70_gate": passes,
                    "gate_failures": failures,
                    "trade_rows": rows,
                }
            )

    # Holm adjustment is applied only to the sixteen pre-declared family×symbol
    # finalists, never to every discarded parameter variant.
    ordered = sorted(enumerate(selected), key=lambda x: x[1]["holdout"]["p_wr_gt_50"])
    running = 0.0
    m = len(ordered)
    for rank, (idx, row) in enumerate(ordered):
        adjusted = min(1.0, (m - rank) * float(row["holdout"]["p_wr_gt_50"]))
        running = max(running, adjusted)
        selected[idx]["holdout_p_holm"] = round(running, 6)

    meta_selectors = [
        _run_regime_meta_selector(
            symbol=symbol,
            generated_rows=generated_rows,
            variant_rows=all_variants,
            feature_frame=_entry_feature_frame(frames[symbol]["5m"]),
            split=split_locks[symbol],
            independent_frames=yahoo_frames[symbol],
        )
        for symbol in ("NQ", "CL")
    ]

    compact_selected = []
    for row in selected:
        clean = dict(row)
        clean.pop("trade_rows", None)
        compact_selected.append(clean)

    passing = [r for r in compact_selected if r["passes_desired_70_gate"]]
    passing_meta = [r for r in meta_selectors if r.get("status") == "PASS"]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if (passing or passing_meta) else "NO_70_PERCENT_STRATEGY_VALIDATED",
        "purpose": "Broad strategy-family restart using corrected paid Databento NQ/CL and an untouched chronological holdout",
        "data_policy": {
            "api_called": False,
            "additional_databento_spend": 0.0,
            "primary_source": "audited local GLBX.MDP3 [ROOT].v.0 continuous one-minute caches",
            "friction": "NQ 0.75 points per completed trade; CL 0.07R; gap-through-stop fill at bar open",
            "position_management": "two contracts; half at +1R; runner target; next-bar BE/trailing; stop-first ambiguity; losing-only 120m time stop",
            "independent_check": "Yahoo 5m 60d, frozen model/threshold, no refit and no paid Databento call",
        },
        "protocol": {
            "split": "50% development / 25% validation / 25% final chronological holdout by CME trade date",
            "selection": "one variant per family and symbol selected on validation only; holdout opened afterward",
            "multiple_testing": "Holm-adjusted one-sided binomial p-values across family×symbol finalists",
            "desired_gate": {
                "all": {"n": 40, "wr": 0.70, "pf": 1.30, "expectancy_r": 0.15},
                "validation": {"n": 8, "pf": 1.0, "expectancy_r": ">0"},
                "holdout": {"n": 10, "wr": 0.70, "pf": 1.20, "expectancy_r": 0.10},
            },
        },
        "cache": cache_meta,
        "split_locks": {k: asdict(v) for k, v in split_locks.items()},
        "sources": SOURCE_CATALOG,
        "n_families": len(FAMILY_SPECS),
        "n_variants": len(all_variants),
        "variants_development_validation_only": all_variants,
        "selected_finalists": compact_selected,
        "regime_meta_selectors": meta_selectors,
        "passing": passing,
        "passing_meta_selectors": passing_meta,
    }


def write_discovery(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "BROAD_STRATEGY_DISCOVERY.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    ranked = sorted(
        payload["selected_finalists"],
        key=lambda r: (
            r["passes_desired_70_gate"],
            r["holdout"]["wr"],
            r["holdout"]["expectancy_r"],
            r["all"]["n"],
        ),
        reverse=True,
    )
    lines = [
        "# Broad Futures Strategy Discovery",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        f"**Verdict: {payload['status']}**",
        "",
        "Paid Databento API calls: **0**; additional spend: **$0.00**. The run used the audited local NQ.v.0 and CL.v.0 caches.",
        "",
        "## Finalists selected without seeing holdout",
        "",
        "| Family | Symbol | Variant | All n | All WR | All PF | All E | Holdout n | Holdout WR | Holdout PF | Holdout E | 70% gate |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in ranked:
        a, h = r["all"], r["holdout"]
        lines.append(
            f"| {r['family']} | {r['symbol']} | {r['variant']} | {a['n']} | {a['wr']:.1%} | {a['pf']:.2f} | {a['expectancy_r']:+.3f}R | "
            f"{h['n']} | {h['wr']:.1%} | {h['pf']:.2f} | {h['expectancy_r']:+.3f}R | {'PASS' if r['passes_desired_70_gate'] else 'FAIL'} |"
        )
    lines += [
        "",
        "## Why the holdout is protected",
        "",
        "Each family had only a small, pre-declared parameter set. One variant per family and symbol was chosen using validation metrics. The final 25% was evaluated only after that choice, and the finalist p-values were adjusted for the number of families examined.",
        "",
        "## Promotion rule",
        "",
        "A strategy is not enabled merely because one cell prints 70%. It must also have enough trades, positive validation and holdout expectancy, acceptable profit factor, realistic configured exits, and no anti-cheat failure.",
        "",
        "## Regime-aware meta-selector",
        "",
        "One regularized logistic selector per symbol was trained only on development rows. Its probability threshold was chosen only on validation rows, and its entry-time-only performance was then opened on holdout.",
        "",
        "| Symbol | Threshold | Development n/WR | Validation n/WR/PF/E | Holdout n/WR/PF/E | Yahoo n/WR/PF/E | Verdict |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in payload.get("regime_meta_selectors", []):
        if row.get("status") == "INSUFFICIENT":
            lines.append(f"| {row['symbol']} | — | — | — | — | — | INSUFFICIENT |")
            continue
        d, v, h = row["development"], row["validation"], row["holdout"]
        y = row["independent_yahoo"]["stats"]
        lines.append(
            f"| {row['symbol']} | {row['threshold']:.2f} | {d['n']}/{d['wr']:.1%} | "
            f"{v['n']}/{v['wr']:.1%}/{v['pf']:.2f}/{v['expectancy_r']:+.3f}R | "
            f"{h['n']}/{h['wr']:.1%}/{h['pf']:.2f}/{h['expectancy_r']:+.3f}R | "
            f"{y['n']}/{y['wr']:.1%}/{y['pf']:.2f}/{y['expectancy_r']:+.3f}R | {row['status']} |"
        )
    (output_dir / "BROAD_STRATEGY_DISCOVERY.md").write_text("\n".join(lines), encoding="utf-8")
