"""Quality audit for the public Reddit-linked NQ one-minute research file."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json

import numpy as np
import pandas as pd

from agent.research.harness.datasets import fetch_yahoo


EXPECTED_COLUMNS = ("Date", "Time", "Open", "High", "Low", "Close", "Volume")


def load_external_nq_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(
        path,
        usecols=list(EXPECTED_COLUMNS),
        dtype={
            "Date": "string",
            "Time": "string",
            "Open": "float64",
            "High": "float64",
            "Low": "float64",
            "Close": "float64",
            "Volume": "float64",
        },
    )
    naive = pd.to_datetime(raw.pop("Date") + " " + raw.pop("Time"), errors="coerce")
    raw.columns = [str(c).lower() for c in raw.columns]
    raw.index = pd.DatetimeIndex(naive, name="timestamp")
    return raw.sort_index()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _yahoo_daily_agreement(df: pd.DataFrame) -> dict[str, Any]:
    try:
        yahoo = fetch_yahoo("NQ=F", "1d", "10y")
    except Exception as exc:
        return {"status": "UNAVAILABLE", "reason": str(exc)}
    if yahoo.empty:
        return {"status": "UNAVAILABLE", "reason": "empty Yahoo response"}
    # Compare equivalent regular-session closes. Calendar-day ``last`` would
    # compare the futures overnight session with Yahoo's RTH-labelled close.
    close_window = df.between_time("15:45", "16:15")
    local_daily = close_window["close"].groupby(close_window.index.normalize()).last()
    y = yahoo["close"].copy()
    y.index = pd.DatetimeIndex(y.index.tz_localize(None)).normalize()
    joined = pd.concat(
        [local_daily.rename("external"), y.rename("yahoo")], axis=1, join="inner"
    ).dropna()
    if len(joined) < 100:
        return {"status": "INSUFFICIENT", "n_days": len(joined)}
    returns = joined.pct_change().dropna()
    return {
        "status": "PASS",
        "n_days": len(joined),
        "start": str(joined.index.min()),
        "end": str(joined.index.max()),
        "close_return_correlation": float(returns["external"].corr(returns["yahoo"])),
        "median_close_basis_pct": float(
            ((joined["external"] - joined["yahoo"]).abs() / joined["yahoo"].abs()).median()
        ),
    }


def _quarantine_scale_anomalies(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Exclude bounded decimal-scale episodes without rewriting their prices.

    A scale episode has a >50% discontinuity into the bad range and another
    >50% discontinuity back out.  Only paired, bounded episodes are quarantined;
    an unpaired discontinuity remains a hard failure.
    """
    returns = df["close"].pct_change().replace([np.inf, -np.inf], np.nan)
    jumps = returns[returns.abs() > 0.50]
    events = list(jumps.index)
    quarantined: list[dict[str, Any]] = []
    mask = pd.Series(False, index=df.index)
    for start, end in zip(events[0::2], events[1::2]):
        before = df["close"].shift(1).loc[start]
        inside = df.at[start, "close"]
        after = df.at[end, "close"]
        prior_to_end = df["close"].shift(1).loc[end]
        entered_scale = max(before, inside) / min(before, inside) >= 5.0
        exited_scale = max(prior_to_end, after) / min(prior_to_end, after) >= 5.0
        if not (entered_scale and exited_scale):
            continue
        episode_mask = (df.index >= start) & (df.index < end)
        mask |= episode_mask
        quarantined.append(
            {
                "start": str(start),
                "end_exclusive": str(end),
                "rows": int(episode_mask.sum()),
                "entry_scale_ratio": float(max(before, inside) / min(before, inside)),
                "exit_scale_ratio": float(max(prior_to_end, after) / min(prior_to_end, after)),
            }
        )
    return df.loc[~mask].copy(), quarantined


def audit_external_nq(path: Path, *, compare_yahoo: bool = True) -> tuple[pd.DataFrame, dict[str, Any]]:
    df = load_external_nq_csv(path)
    numeric = df[["open", "high", "low", "close", "volume"]]
    null_rows = int(numeric.isna().any(axis=1).sum())
    invalid_ohlc = int(
        (
            (df["high"] < df[["open", "close", "low"]].max(axis=1))
            | (df["low"] > df[["open", "close", "high"]].min(axis=1))
            | (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
            | (df["volume"] < 0)
        ).sum()
    )
    duplicate_ts = int(df.index.duplicated(keep=False).sum())
    clean_df, scale_quarantines = _quarantine_scale_anomalies(df)
    diffs = clean_df.index.to_series().diff().dropna().dt.total_seconds().div(60.0)
    close_ret = clean_df["close"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    large = close_ret.abs() > 0.01
    biggest = close_ret.abs().nlargest(15)
    yahoo = _yahoo_daily_agreement(clean_df) if compare_yahoo else {"status": "NOT_RUN"}
    failures: list[str] = []
    if null_rows:
        failures.append("null_numeric_rows")
    if invalid_ohlc:
        failures.append("invalid_ohlc_rows")
    if duplicate_ts:
        failures.append("duplicate_timestamps")
    unpaired_scale_jumps = max(0, int((df["close"].pct_change().abs() > 0.50).sum()) - 2 * len(scale_quarantines))
    if unpaired_scale_jumps:
        failures.append("unpaired_scale_discontinuity")
    if float(large.mean()) > 0.002:
        failures.append("excessive_1pct_minute_returns")
    if yahoo.get("status") == "PASS" and float(yahoo["close_return_correlation"]) < 0.95:
        failures.append("weak_yahoo_return_agreement")
    # The file lacks Databento identity/cache metadata. Even perfect row quality
    # therefore remains WARN and research-only, never paper-provider evidence.
    status = "FAIL" if failures else "WARN_UNVERIFIED_PROVENANCE"
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "research_use_only": True,
        "paper_provider_allowed": False,
        "provenance": {
            "source_post": "https://www.reddit.com/r/FuturesTrading/comments/1kns6vk/",
            "public_drive_file_id": "1Gznd9uTMMfEfGRt427aKLVi4LSe0nRUh",
            "claimed_origin": "Databento (author statement only; no manifest supplied)",
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        },
        "shape": {"rows": len(df), "columns": list(df.columns)},
        "window": [str(df.index.min()), str(df.index.max())],
        "quality": {
            "null_numeric_rows": null_rows,
            "invalid_ohlc_rows": invalid_ohlc,
            "duplicate_timestamp_rows": duplicate_ts,
            "out_of_order_rows_after_sort": int((df.index.to_series().diff().dropna() < pd.Timedelta(0)).sum()),
            "gap_2_to_30_minutes": int(((diffs >= 2) & (diffs <= 30)).sum()),
            "gaps_over_30_minutes": int((diffs > 30).sum()),
            "minute_returns_over_1pct": int(large.sum()),
            "minute_returns_over_1pct_rate": float(large.mean()),
            "max_abs_minute_return": float(close_ret.abs().max()) if len(close_ret) else 0.0,
            "biggest_return_timestamps": [
                {"timestamp": str(ts), "abs_return": float(value)} for ts, value in biggest.items()
            ],
            "price_min": float(df["low"].min()),
            "price_max": float(df["high"].max()),
            "scale_quarantines": scale_quarantines,
            "quarantined_rows": int(len(df) - len(clean_df)),
            "clean_rows": int(len(clean_df)),
        },
        "yahoo_daily_agreement": yahoo,
        "failures": failures,
    }
    return clean_df, payload


def write_external_audit(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "EXTERNAL_NQ_QUALITY.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    q = payload["quality"]
    y = payload["yahoo_daily_agreement"]
    lines = [
        "# External NQ 2010–2025 Quality Audit",
        "",
        f"**Status: {payload['status']}**",
        "",
        "The public file is permitted only as a long-history research-development source. It has no Databento manifest or continuous-contract identity metadata and can never replace the audited paid NQ.v.0 paper/research cache.",
        "",
        f"- Rows: {payload['shape']['rows']:,}",
        f"- Window: {payload['window'][0]} to {payload['window'][1]}",
        f"- SHA-256: `{payload['provenance']['sha256']}`",
        f"- Invalid OHLC rows: {q['invalid_ohlc_rows']}",
        f"- Duplicate timestamp rows: {q['duplicate_timestamp_rows']}",
        f"- Quarantined scale-error rows: {q['quarantined_rows']:,}",
        f"- Clean research rows: {q['clean_rows']:,}",
        f"- >1% one-minute returns: {q['minute_returns_over_1pct']} ({q['minute_returns_over_1pct_rate']:.4%})",
        f"- Yahoo daily return agreement: {y.get('close_return_correlation', 'unavailable')}",
        "",
        "Recent validation and any paper promotion must still use corrected paid Databento plus an independent current source.",
    ]
    (output_dir / "EXTERNAL_NQ_QUALITY.md").write_text("\n".join(lines), encoding="utf-8")
