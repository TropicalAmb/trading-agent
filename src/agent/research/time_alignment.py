"""Point-in-time-safe higher-timeframe features for historical/live parity.

For a base bar inside an unfinished 15m/1h/4h bucket, only the bucket open and
the current base-bar close are knowable.  Resampling a full historical frame
and forward-filling the finished bucket close leaks future bars into earlier
rows and can manufacture backtest edge.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def partial_bar_direction(df: pd.DataFrame, rule: str) -> pd.Series:
    """Direction of each higher-timeframe candle as it was known at every row."""
    if df is None or df.empty:
        return pd.Series(dtype=int)
    buckets = df.index.floor(rule)
    bucket_open = df["open"].groupby(buckets).transform("first")
    close_asof = df["close"].astype(float)
    out = np.sign(close_asof - bucket_open.astype(float))
    return pd.Series(out, index=df.index).fillna(0).astype(int)


def partial_bar_trend(
    df: pd.DataFrame, rule: str, *, ema_n: int = 20
) -> pd.Series:
    """Close-vs-EMA trend using completed prior buckets plus current close.

    The EMA state before the active bucket uses only completed buckets.  The
    current base-bar close is then applied once, matching what a live scan sees
    when it resamples through that moment.
    """
    if df is None or df.empty:
        return pd.Series(dtype=int)
    buckets = pd.DatetimeIndex(df.index.floor(rule))
    close = df["close"].astype(float)
    completed_closes = close.groupby(buckets).last()
    prior_completed_ema = completed_closes.ewm(span=ema_n, adjust=False).mean().shift(1)
    prior = pd.Series(buckets, index=df.index).map(prior_completed_ema)
    alpha = 2.0 / (float(ema_n) + 1.0)
    current_ema = alpha * close + (1.0 - alpha) * prior
    current_ema = current_ema.where(prior.notna(), close)
    out = pd.Series(0, index=df.index, dtype=int)
    out = out.mask(close > current_ema, 1)
    out = out.mask(close < current_ema, -1)
    return out.fillna(0).astype(int)
