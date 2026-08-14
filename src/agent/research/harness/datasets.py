"""Historical data load + frozen chronological splits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SplitSpec:
    train_end: str
    val_end: str
    final_start: str
    n_days_train: int
    n_days_val: int
    n_days_final: int


def fetch_yahoo(symbol: str, interval: str, period: str) -> pd.DataFrame:
    """Reuse yfinance fetch pattern from research scripts (ET-localized)."""
    import yfinance as yf
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
    df = yf.download(
        symbol,
        interval=interval,
        period=period,
        auto_adjust=True,
        progress=False,
        threads=False,
        timeout=20,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [str(c).lower() for c in df.columns]
    df = df.dropna(subset=["open", "high", "low", "close"]).copy()
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize("UTC")
    df.index = idx.tz_convert(ET)
    return df


def freeze_splits(df: pd.DataFrame, train_frac: float = 0.60, val_frac: float = 0.20) -> SplitSpec:
    """Lock chronological 60/20/20 by trading days BEFORE any optimization."""
    days = sorted(df.index.normalize().unique())
    n = len(days)
    if n < 20:
        raise ValueError(f"insufficient days for freeze split: {n}")
    i1 = int(n * train_frac)
    i2 = int(n * (train_frac + val_frac))
    i1 = max(i1, 5)
    i2 = max(i2, i1 + 3)
    i2 = min(i2, n - 3)
    train_days, val_days, final_days = days[:i1], days[i1:i2], days[i2:]
    return SplitSpec(
        train_end=str(train_days[-1]),
        val_end=str(val_days[-1]),
        final_start=str(final_days[0]),
        n_days_train=len(train_days),
        n_days_val=len(val_days),
        n_days_final=len(final_days),
    )


def mask_period(df: pd.DataFrame, *, start: pd.Timestamp | None, end: pd.Timestamp | None) -> pd.DataFrame:
    out = df
    if start is not None:
        out = out[out.index >= start]
    if end is not None:
        out = out[out.index <= end]
    return out


def assign_period(ts: pd.Timestamp, split: SplitSpec) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("America/New_York").tz_localize(None)
    te = pd.Timestamp(split.train_end).tz_localize(None) if pd.Timestamp(split.train_end).tzinfo else pd.Timestamp(split.train_end)
    ve = pd.Timestamp(split.val_end).tz_localize(None) if pd.Timestamp(split.val_end).tzinfo else pd.Timestamp(split.val_end)
    # compare date-normalized
    td = t.normalize()
    if td <= pd.Timestamp(te).normalize():
        return "train"
    if td <= pd.Timestamp(ve).normalize():
        return "val"
    return "final"


def save_split_lock(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_split_lock(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
