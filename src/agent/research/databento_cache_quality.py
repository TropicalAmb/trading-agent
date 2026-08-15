"""Reusable quality checks for one-root Databento continuous OHLCV caches."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


def audit_continuous_cache(
    frame: pd.DataFrame,
    metadata: dict[str, Any],
    *,
    root: str,
    max_large_jump_fraction: float = 0.002,
) -> dict[str, Any]:
    root = str(root).upper()
    df = frame.copy().sort_index()
    columns = [str(c).lower() for c in df.columns]
    df.columns = columns
    missing_columns = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    failures: list[str] = []
    warnings: list[str] = []
    if missing_columns:
        failures.append(f"missing_columns:{','.join(missing_columns)}")
        return {
            "root": root,
            "status": "FAIL",
            "failures": failures,
            "warnings": warnings,
            "rows": int(len(df)),
            "columns": columns,
        }

    expected_symbol = f"{root}.v.0"
    if str(metadata.get("databento") or "").lower() != expected_symbol.lower():
        failures.append(f"metadata_symbol_not_{expected_symbol}")
    if str(metadata.get("stype_in") or "").lower() != "continuous":
        failures.append("metadata_stype_not_continuous")
    if str(metadata.get("cache_format_version") or "") != "databento_continuous_v1":
        failures.append("metadata_format_not_continuous_v1")

    duplicate_timestamps = int(df.index.duplicated(keep=False).sum())
    if duplicate_timestamps:
        failures.append(f"duplicate_timestamps:{duplicate_timestamps}")
    null_counts = {c: int(df[c].isna().sum()) for c in REQUIRED_COLUMNS}
    if any(null_counts.values()):
        failures.append("null_required_ohlcv")

    numeric = df.loc[:, REQUIRED_COLUMNS].apply(pd.to_numeric, errors="coerce")
    non_finite = int((~np.isfinite(numeric.to_numpy(dtype=float))).sum())
    invalid_ohlc = int(
        (
            (numeric["high"] < numeric[["open", "close"]].max(axis=1))
            | (numeric["low"] > numeric[["open", "close"]].min(axis=1))
            | (numeric["high"] < numeric["low"])
        ).sum()
    )
    nonpositive_price = int((numeric[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
    negative_volume = int((numeric["volume"] < 0).sum())
    if non_finite:
        failures.append(f"non_finite_values:{non_finite}")
    if invalid_ohlc:
        failures.append(f"invalid_ohlc_rows:{invalid_ohlc}")
    if nonpositive_price:
        failures.append(f"nonpositive_price_rows:{nonpositive_price}")
    if negative_volume:
        failures.append(f"negative_volume_rows:{negative_volume}")

    close = numeric["close"].astype(float)
    all_returns = close.pct_change().abs()
    gap_seconds = pd.Series(df.index, index=df.index).diff().dt.total_seconds()
    # Detect interleaved contracts only on truly adjacent minutes. Weekend,
    # maintenance, and missing-liquidity gaps can legitimately re-open far away.
    returns = all_returns.loc[gap_seconds == 60].dropna()
    large_jump_fraction = float((returns > 0.01).mean()) if len(returns) else 0.0
    half_pct_jump_fraction = float((returns > 0.005).mean()) if len(returns) else 0.0
    if large_jump_fraction > max_large_jump_fraction:
        failures.append(
            f"large_jump_fraction:{large_jump_fraction:.6f}>{max_large_jump_fraction:.6f}"
        )
    elif large_jump_fraction > max_large_jump_fraction / 2:
        warnings.append(f"elevated_large_jump_fraction:{large_jump_fraction:.6f}")

    top_jumps: list[dict[str, Any]] = []
    if len(returns):
        for ts, value in returns.nlargest(10).items():
            loc = int(df.index.get_loc(ts))
            top_jumps.append(
                {
                    "timestamp": str(ts),
                    "absolute_return": float(value),
                    "previous_close": float(close.iloc[loc - 1]) if loc > 0 else None,
                    "close": float(close.iloc[loc]),
                    "gap_minutes": 1.0,
                }
            )

    gap_returns = all_returns.loc[gap_seconds > 60].dropna()
    top_gap_jumps: list[dict[str, Any]] = []
    for ts, value in gap_returns.nlargest(10).items():
        loc = int(df.index.get_loc(ts))
        top_gap_jumps.append(
            {
                "timestamp": str(ts),
                "absolute_return": float(value),
                "previous_close": float(close.iloc[loc - 1]) if loc > 0 else None,
                "close": float(close.iloc[loc]),
                "gap_minutes": float(gap_seconds.loc[ts] / 60.0),
            }
        )

    gaps = gap_seconds.dropna()
    one_minute_share = float((gaps == 60).mean()) if len(gaps) else 0.0
    # Exclude the normal daily maintenance break and weekends; 2–30m holes are
    # the useful missing-bar signal for these CME one-minute caches.
    within_session_gaps = gaps[(gaps >= 120) & (gaps <= 1800)]
    within_session_gap_fraction = (
        float(len(within_session_gaps) / len(gaps)) if len(gaps) else 0.0
    )
    if within_session_gap_fraction > 0.005:
        warnings.append(
            f"elevated_2_to_30m_gap_fraction:{within_session_gap_fraction:.6f}"
        )

    daily = numeric["close"].groupby(df.index.normalize()).count()
    daily_summary = {
        "calendar_days": int(len(daily)),
        "min_rows": int(daily.min()) if len(daily) else 0,
        "median_rows": float(daily.median()) if len(daily) else 0.0,
        "p05_rows": float(daily.quantile(0.05)) if len(daily) else 0.0,
        "max_rows": int(daily.max()) if len(daily) else 0,
    }
    status = "FAIL" if failures else ("WARN" if warnings else "PASS")
    return {
        "root": root,
        "status": status,
        "failures": failures,
        "warnings": warnings,
        "expected_grain": "one row per available CME minute for one volume-continuous root",
        "rows": int(len(df)),
        "columns": columns,
        "dtypes": {c: str(df[c].dtype) for c in REQUIRED_COLUMNS},
        "start": str(df.index.min()) if len(df) else None,
        "end": str(df.index.max()) if len(df) else None,
        "timezone": str(getattr(df.index, "tz", None)),
        "duplicate_timestamps": duplicate_timestamps,
        "exact_duplicate_value_rows": int(numeric.duplicated(keep=False).sum()),
        "null_counts": null_counts,
        "non_finite_values": non_finite,
        "invalid_ohlc_rows": invalid_ohlc,
        "nonpositive_price_rows": nonpositive_price,
        "negative_volume_rows": negative_volume,
        "large_jump_fraction_gt_1pct": large_jump_fraction,
        "jump_fraction_gt_0_5pct": half_pct_jump_fraction,
        "max_absolute_minute_return": float(returns.max()) if len(returns) else 0.0,
        "top_jumps": top_jumps,
        "max_absolute_gap_return": float(gap_returns.max()) if len(gap_returns) else 0.0,
        "top_gap_jumps": top_gap_jumps,
        "one_minute_gap_share": one_minute_share,
        "within_session_2_to_30m_gap_count": int(len(within_session_gaps)),
        "within_session_2_to_30m_gap_fraction": within_session_gap_fraction,
        "max_gap_minutes": float(gaps.max() / 60.0) if len(gaps) else 0.0,
        "daily_row_summary": daily_summary,
        "metadata": {
            "databento": metadata.get("databento"),
            "stype_in": metadata.get("stype_in"),
            "roll_rule": metadata.get("roll_rule"),
            "cache_format_version": metadata.get("cache_format_version"),
            "dataset": metadata.get("dataset"),
            "schema": metadata.get("schema"),
            "saved_utc": metadata.get("saved_utc"),
        },
    }


def compare_with_yahoo_5m(
    databento_1m: pd.DataFrame,
    yahoo_5m: pd.DataFrame,
) -> dict[str, Any]:
    """Independent price/basis/return comparison on completed 5-minute bars."""
    if databento_1m.empty or yahoo_5m.empty:
        return {"status": "FAIL", "reason": "empty_source", "overlap_bars": 0}
    db = databento_1m.copy()
    yh = yahoo_5m.copy()
    for frame in (db, yh):
        frame.index = pd.to_datetime(frame.index)
        if frame.index.tz is None:
            frame.index = frame.index.tz_localize("America/New_York")
        else:
            frame.index = frame.index.tz_convert("America/New_York")
    counts = db["close"].resample("5min", label="left", closed="left").count()
    db5 = db.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    db5 = db5.loc[counts >= 4].dropna(subset=["close"])
    common = db5.index.intersection(yh.index)
    if len(common) < 100:
        return {
            "status": "FAIL",
            "reason": "insufficient_overlap",
            "overlap_bars": int(len(common)),
        }
    db_close = db5.loc[common, "close"].astype(float)
    yh_close = yh.loc[common, "close"].astype(float)
    relative = (db_close - yh_close).abs() / yh_close.abs().clip(lower=1e-9)
    db_ret = db_close.pct_change()
    yh_ret = yh_close.pct_change()
    return_corr = float(db_ret.corr(yh_ret))
    median_basis = float(relative.median())
    status = "PASS" if median_basis <= 0.02 and return_corr >= 0.90 else "WARN"
    return {
        "status": status,
        "overlap_bars": int(len(common)),
        "overlap_start": str(common.min()),
        "overlap_end": str(common.max()),
        "median_absolute_basis_points": float((db_close - yh_close).abs().median()),
        "median_relative_basis_gap": median_basis,
        "p95_relative_basis_gap": float(relative.quantile(0.95)),
        "max_relative_basis_gap": float(relative.max()),
        "five_minute_return_correlation": return_corr,
    }
