"""Data-quality audit for NQ 1-minute research feeds (Kaggle first)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _rth_mask(index: pd.DatetimeIndex) -> pd.Series:
    """CME equity index RTH approx 09:30–16:00 ET (excludes overnight Globex)."""
    minutes = index.hour * 60 + index.minute
    return pd.Series((minutes >= 9 * 60 + 30) & (minutes < 16 * 60), index=index)


def audit_nq_1m(df: pd.DataFrame, *, symbol: str = "NQ") -> dict[str, Any]:
    """Return structured quality report; does not mutate df."""
    issues: list[str] = []
    warnings: list[str] = []
    if df is None or df.empty:
        return {
            "symbol": symbol,
            "ok": False,
            "rows": 0,
            "issues": ["empty_frame"],
            "warnings": [],
        }

    idx = df.index
    tz = str(getattr(idx, "tz", None))
    if getattr(idx, "tz", None) is None:
        issues.append("timezone_naive")
    elif "New_York" not in tz and "Eastern" not in tz:
        warnings.append(f"unexpected_tz:{tz}")

    n = len(df)
    start, end = idx.min(), idx.max()
    dups = int(idx.duplicated().sum())
    if dups:
        issues.append(f"duplicate_timestamps:{dups}")

    # Expected 1-minute spacing within continuous segments
    deltas = idx.to_series().diff().dropna()
    median_delta = deltas.median()
    gap_gt_2m = int((deltas > pd.Timedelta(minutes=2)).sum())
    gap_gt_30m = int((deltas > pd.Timedelta(minutes=30)).sum())
    if median_delta != pd.Timedelta(minutes=1):
        warnings.append(f"median_bar_delta:{median_delta}")

    ohlc = df[["open", "high", "low", "close"]].astype(float)
    bad_hl = int((ohlc["high"] < ohlc["low"]).sum())
    bad_body = int(
        (
            (ohlc["high"] < ohlc[["open", "close"]].max(axis=1))
            | (ohlc["low"] > ohlc[["open", "close"]].min(axis=1))
        ).sum()
    )
    if bad_hl:
        issues.append(f"high_lt_low:{bad_hl}")
    if bad_body:
        issues.append(f"ohlc_integrity:{bad_body}")

    nulls = {c: int(df[c].isna().sum()) for c in ("open", "high", "low", "close", "volume") if c in df.columns}
    if any(nulls.values()):
        issues.append(f"nulls:{nulls}")

    # Outliers: |return| > 3% on 1m (extreme but flag)
    ret = ohlc["close"].pct_change().abs()
    outlier_n = int((ret > 0.03).sum())
    if outlier_n:
        warnings.append(f"abs_1m_return_gt_3pct:{outlier_n}")

    # Roll / gap jumps on overnight open (flag large gaps between sessions)
    day = idx.normalize()
    session_open_gap = []
    for d, g in df.groupby(day):
        if len(g) < 2:
            continue
        # first bar vs prior day last close
    prior_close = None
    large_rollish = 0
    for _, g in df.groupby(day):
        if prior_close is not None:
            gap = abs(float(g["open"].iloc[0]) - float(prior_close)) / max(float(prior_close), 1e-9)
            if gap > 0.015:
                large_rollish += 1
        prior_close = float(g["close"].iloc[-1])
    if large_rollish:
        warnings.append(f"day_open_gap_gt_1p5pct:{large_rollish}")

    rth = _rth_mask(idx)
    eth = ~rth
    vol = df["volume"].astype(float) if "volume" in df.columns else pd.Series(0.0, index=idx)
    zero_vol = int((vol <= 0).sum())
    if zero_vol > 0.05 * n:
        warnings.append(f"zero_volume_bars:{zero_vol}")

    has_vwap_rth = "vwap_rth" in df.columns
    has_vwap_eth = "vwap_eth" in df.columns
    vwap_rth_nonzero = int((df["vwap_rth"] > 0).sum()) if has_vwap_rth else 0
    vwap_eth_nonzero = int((df["vwap_eth"] > 0).sum()) if has_vwap_eth else 0
    if has_vwap_rth and vwap_rth_nonzero == 0:
        warnings.append("vwap_rth_all_zero")
    if has_vwap_eth and vwap_eth_nonzero < 0.5 * n:
        warnings.append("vwap_eth_sparse")

    # Excel-ish truncation heuristic
    if n == 1_048_575:
        warnings.append("row_count_equals_excel_max_possible_truncation")

    coverage_days = int(pd.Series(day.unique()).nunique())
    ok = len(issues) == 0
    return {
        "symbol": symbol,
        "ok": ok,
        "rows": n,
        "start": str(start),
        "end": str(end),
        "timezone": tz,
        "coverage_calendar_days": coverage_days,
        "duplicate_timestamps": dups,
        "median_bar_delta_seconds": float(median_delta.total_seconds()) if pd.notna(median_delta) else None,
        "gaps_gt_2m": gap_gt_2m,
        "gaps_gt_30m": gap_gt_30m,
        "ohlc_high_lt_low": bad_hl,
        "ohlc_integrity_failures": bad_body,
        "nulls": nulls,
        "outlier_abs_ret_gt_3pct": outlier_n,
        "day_open_gap_gt_1p5pct": large_rollish,
        "rth_bars": int(rth.sum()),
        "eth_bars": int(eth.sum()),
        "zero_volume_bars": zero_vol,
        "has_vwap_rth": has_vwap_rth,
        "has_vwap_eth": has_vwap_eth,
        "vwap_rth_nonzero": vwap_rth_nonzero,
        "vwap_eth_nonzero": vwap_eth_nonzero,
        "issues": issues,
        "warnings": warnings,
        "source_path": df.attrs.get("path"),
        "source": df.attrs.get("source", "unknown"),
    }


def audit_to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# NQ 1m data-quality report",
        "",
        f"- symbol: `{report.get('symbol')}`",
        f"- ok: **{report.get('ok')}**",
        f"- rows: `{report.get('rows')}`",
        f"- range: `{report.get('start')}` → `{report.get('end')}`",
        f"- timezone: `{report.get('timezone')}`",
        f"- RTH bars / ETH bars: `{report.get('rth_bars')}` / `{report.get('eth_bars')}`",
        f"- gaps >2m / >30m: `{report.get('gaps_gt_2m')}` / `{report.get('gaps_gt_30m')}`",
        f"- OHLC integrity failures: `{report.get('ohlc_integrity_failures')}`",
        f"- issues: `{report.get('issues')}`",
        f"- warnings: `{report.get('warnings')}`",
        "",
    ]
    return "\n".join(lines)
