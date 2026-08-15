"""One-shot cheap Databento NQ 1m cache. Reuses disk file — no re-download if present.

Default: 120 calendar days (~$0.60). Never pull more without --force-days.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

CACHE = ROOT / "data" / "databento" / "NQ_1m_cache.parquet"
META = ROOT / "data" / "databento" / "NQ_1m_cache_meta.json"
CACHE_FORMAT_VERSION = "databento_continuous_v1"


def _compatible_cache() -> bool:
    if not CACHE.exists() or not META.exists():
        return False
    try:
        meta = json.loads(META.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        meta.get("cache_format_version") == CACHE_FORMAT_VERSION
        and str(meta.get("stype_in") or "").lower() == "continuous"
        and str(meta.get("databento") or meta.get("symbol") or "").lower()
        == "nq.v.0"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=120, help="Calendar days (default 120, keep cheap)")
    ap.add_argument("--force", action="store_true", help="Re-download even if cache exists")
    ap.add_argument("--max-cost-usd", type=float, default=1.0, help="Abort if estimate exceeds this")
    ap.add_argument("--quote-only", action="store_true", help="Quote cost without downloading")
    args = ap.parse_args()
    if args.days > 180:
        print("REFUSED: days>180 without explicit product decision. Keep Databento spend small.")
        return 2

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if _compatible_cache() and not args.force:
        df = pd.read_parquet(CACHE)
        print(f"CACHE HIT {CACHE} rows={len(df)} range={df.index.min()} -> {df.index.max()}")
        return 0

    key = (os.getenv("DATABENTO_API_KEY") or "").strip()
    if not key:
        print("DATABENTO_API_KEY missing")
        return 3

    import databento as db
    from agent.data.databento_historical import DatabentoHistoricalProvider

    end = datetime(2025, 12, 11, 21, tzinfo=timezone.utc)
    start = end - timedelta(days=int(args.days))
    client = db.Historical(key)
    cost = float(
        client.metadata.get_cost(
            dataset="GLBX.MDP3",
            symbols="NQ.v.0",
            schema="ohlcv-1m",
            stype_in="continuous",
            start=start.isoformat(),
            end=end.isoformat(),
        )
    )
    print(f"Estimated cost ${cost:.4f} for {args.days}d")
    if cost > float(args.max_cost_usd):
        print(f"REFUSED: estimate ${cost:.4f} > max ${args.max_cost_usd}")
        return 4
    if args.quote_only:
        return 0

    prov = DatabentoHistoricalProvider(api_key=key)
    df = prov.fetch_ohlcv_df(
        "NQ", start=start, end=end, schema="ohlcv-1m", stype_in="continuous"
    )
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    if df.index.duplicated().any():
        df = df[~df.index.duplicated(keep="last")]
    jumps = df["close"].pct_change().abs().dropna()
    large_jump_fraction = float((jumps > 0.01).mean()) if len(jumps) else 0.0
    if large_jump_fraction > 0.002:
        print(
            f"REFUSED: continuity audit found {large_jump_fraction:.3%} "
            "of minute returns above 1%"
        )
        return 5
    df.to_parquet(CACHE)
    META.write_text(
        pd.Series(
            {
                "rows": len(df),
                "start": str(df.index.min()),
                "end": str(df.index.max()),
                "days": args.days,
                "est_cost_usd": cost,
                "dataset": "GLBX.MDP3",
                "symbol": "NQ.v.0",
                "databento": "NQ.v.0",
                "stype_in": "continuous",
                "roll_rule": "volume",
                "cache_format_version": CACHE_FORMAT_VERSION,
                "large_jump_fraction": large_jump_fraction,
                "schema": "ohlcv-1m",
            }
        ).to_json()
    )
    print(f"SAVED {CACHE} rows={len(df)} cost~${cost:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
