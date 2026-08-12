"""Cross-check Kaggle NQ 1m against Databento GLBX.MDP3 ohlcv-1m."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd


def align_on_minute(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    common = a.index.intersection(b.index)
    return a.loc[common], b.loc[common]


def cross_check_ohlcv(
    kaggle: pd.DataFrame,
    databento: pd.DataFrame,
    *,
    price_tol: float = 0.50,
    max_sample_days: int = 5,
) -> dict[str, Any]:
    """Compare overlapping 1m bars. price_tol in NQ points (2 ticks = 0.50)."""
    if kaggle is None or kaggle.empty or databento is None or databento.empty:
        return {
            "ok": False,
            "reason": "empty_input",
            "overlap_bars": 0,
            "recommendation": "USE_DATABENTO_IF_AVAILABLE",
        }

    ka, db = align_on_minute(kaggle, databento)
    n = len(ka)
    if n < 50:
        return {
            "ok": False,
            "reason": "insufficient_overlap",
            "overlap_bars": n,
            "kaggle_range": [str(kaggle.index.min()), str(kaggle.index.max())],
            "databento_range": [str(databento.index.min()), str(databento.index.max())],
            "recommendation": "EXPAND_OVERLAP_OR_USE_DATABENTO",
        }

    diffs = {}
    for col in ("open", "high", "low", "close"):
        d = (ka[col].astype(float) - db[col].astype(float)).abs()
        diffs[col] = {
            "mean_abs": float(d.mean()),
            "median_abs": float(d.median()),
            "p95_abs": float(d.quantile(0.95)),
            "max_abs": float(d.max()),
            "frac_gt_tol": float((d > price_tol).mean()),
        }
    close_bad = diffs["close"]["frac_gt_tol"]
    material = close_bad > 0.05 or diffs["close"]["median_abs"] > price_tol
    recommendation = "USE_DATABENTO_AS_TRUTH" if material else "KAGGLE_OK_FOR_BROAD_RESEARCH"
    return {
        "ok": not material,
        "overlap_bars": n,
        "overlap_start": str(ka.index.min()),
        "overlap_end": str(ka.index.max()),
        "price_tol_points": price_tol,
        "diffs": diffs,
        "materially_inconsistent": material,
        "recommendation": recommendation,
        "note": (
            "If materially inconsistent, Databento GLBX.MDP3 is source of truth for finalists. "
            "Kaggle may still be used for cheap broad scans only when ok=True."
        ),
    }


def fetch_databento_overlap_sample(
    provider: Any,
    kaggle: pd.DataFrame,
    *,
    symbol: str = "NQ",
    days: int = 3,
) -> pd.DataFrame | None:
    """Pull a short Databento window overlapping the newest Kaggle days (cost control)."""
    if not getattr(provider, "api_key", None):
        return None
    end = kaggle.index.max().to_pydatetime()
    start = end - timedelta(days=days)
    try:
        return provider.fetch_ohlcv_df(symbol, start=start, end=end, schema="ohlcv-1m")
    except Exception:
        return None
