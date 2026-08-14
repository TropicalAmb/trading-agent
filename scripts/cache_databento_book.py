"""Cache Databento ohlcv-1m for NQ/ES/CL/GC. Quotes cost, refuses over max, writes parquet.

Default: 180d ending at latest licensed slice. Reuses cache unless --force.
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

OUT = ROOT / "data" / "databento"
SYMBOLS = {
    "NQ": "NQ.v.0",
    "ES": "ES.v.0",
    "CL": "CL.v.0",
    "GC": "GC.v.0",
}
# Drop junk / calendar-spread prints (DEBUG traps)
CLOSE_FLOOR = {"NQ": 5000.0, "ES": 1000.0, "CL": 10.0, "GC": 500.0}
CACHE_FORMAT_VERSION = "databento_continuous_v1"


def _compatible_cache(root: str) -> bool:
    path = OUT / f"{root}_1m_cache.parquet"
    meta_path = OUT / f"{root}_1m_cache_meta.json"
    if not path.exists() or not meta_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        meta.get("cache_format_version") == CACHE_FORMAT_VERSION
        and str(meta.get("stype_in") or "").lower() == "continuous"
        and str(meta.get("databento") or "").lower() == SYMBOLS[root].lower()
    )


def _end_available(client) -> datetime:
    """Use dataset available_end minus a small cushion (license wall is earlier than wall clock)."""
    try:
        rng = client.metadata.get_dataset_range(dataset="GLBX.MDP3")
        # SDK may return dict-like with schema ranges
        end_raw = None
        if isinstance(rng, dict):
            end_raw = rng.get("end") or rng.get("available_end")
            schema = rng.get("schema") or {}
            if isinstance(schema, dict) and "ohlcv-1m" in schema:
                end_raw = schema["ohlcv-1m"].get("end") or end_raw
        if end_raw is not None:
            end = pd.Timestamp(end_raw).to_pydatetime()
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            return end.astimezone(timezone.utc) - timedelta(minutes=5)
    except Exception as exc:
        print(f"WARN get_dataset_range failed: {exc}")
    # Fallback: last known-good licensed slice style
    return datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-cost-usd", type=float, default=30.0)
    ap.add_argument("--quote-only", action="store_true")
    ap.add_argument(
        "--symbols",
        default="NQ,ES,CL,GC",
        help="Comma list of roots to pull",
    )
    args = ap.parse_args()
    if args.days > 180:
        print("REFUSED: days>180 without new explicit OK")
        return 2

    want = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    for s in want:
        if s not in SYMBOLS:
            print(f"Unknown symbol {s}")
            return 2

    key = (os.getenv("DATABENTO_API_KEY") or "").strip()
    if not key:
        print("DATABENTO_API_KEY missing")
        return 3

    import databento as db
    from agent.data.databento_historical import DatabentoHistoricalProvider

    client = db.Historical(key)
    end = _end_available(client)
    start = end - timedelta(days=int(args.days))
    db_syms = [SYMBOLS[s] for s in want]

    # Prefer batch quote (matches billing shape better)
    batch_cost = float(
        client.metadata.get_cost(
            dataset="GLBX.MDP3",
            symbols=db_syms,
            schema="ohlcv-1m",
            stype_in="continuous",
            start=start.isoformat(),
            end=end.isoformat(),
        )
    )
    print(f"Window: {start.isoformat()} -> {end.isoformat()}")
    print(f"Symbols: {want}")
    print(f"Batch estimate: ${batch_cost:.4f}")
    for s in want:
        c = float(
            client.metadata.get_cost(
                dataset="GLBX.MDP3",
                symbols=SYMBOLS[s],
                schema="ohlcv-1m",
                stype_in="continuous",
                start=start.isoformat(),
                end=end.isoformat(),
            )
        )
        path = OUT / f"{s}_1m_cache.parquet"
        hit = _compatible_cache(s) and not args.force
        print(f"  {s:3} {SYMBOLS[s]:8} ${c:.4f}  cache={'HIT' if hit else 'MISS'}")

    if batch_cost > float(args.max_cost_usd):
        print(f"REFUSED: ${batch_cost:.4f} > max ${args.max_cost_usd}")
        return 4
    if args.quote_only:
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    prov = DatabentoHistoricalProvider(api_key=key)
    spent_note = []
    for s in want:
        path = OUT / f"{s}_1m_cache.parquet"
        meta_path = OUT / f"{s}_1m_cache_meta.json"
        if _compatible_cache(s) and not args.force:
            df = pd.read_parquet(path)
            print(f"CACHE HIT {s} rows={len(df)} {df.index.min()} -> {df.index.max()}")
            continue
        print(f"DOWNLOAD {s}...", flush=True)
        df = prov.fetch_ohlcv_df(
            s, start=start, end=end, schema="ohlcv-1m", stype_in="continuous"
        )
        if df is None or df.empty:
            print(f"FAIL empty {s}")
            return 5
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        floor = CLOSE_FLOOR.get(s, 0.0)
        before = len(df)
        df = df[df["close"] >= floor].copy()
        if df.index.duplicated().any():
            df = df[~df.index.duplicated(keep="last")]
        jumps = df["close"].pct_change().abs().dropna()
        large_jump_fraction = float((jumps > 0.01).mean()) if len(jumps) else 0.0
        if large_jump_fraction > 0.002:
            print(
                f"REFUSED {s}: continuity audit found {large_jump_fraction:.3%} "
                "of minute returns above 1%"
            )
            return 6
        df.to_parquet(path)
        meta = {
            "symbol": s,
            "databento": SYMBOLS[s],
            "stype_in": "continuous",
            "roll_rule": "volume",
            "cache_format_version": CACHE_FORMAT_VERSION,
            "large_jump_fraction": large_jump_fraction,
            "rows": len(df),
            "rows_raw": before,
            "start": str(df.index.min()),
            "end": str(df.index.max()),
            "days": args.days,
            "close_floor": floor,
            "dataset": "GLBX.MDP3",
            "schema": "ohlcv-1m",
            "query_start": start.isoformat(),
            "query_end": end.isoformat(),
            "batch_est_cost_usd": batch_cost,
            "saved_utc": datetime.now(timezone.utc).isoformat(),
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        spent_note.append(s)
        print(f"SAVED {path} rows={len(df)} (filtered {before - len(df)} junk)", flush=True)

    (OUT / "book_cache_manifest.json").write_text(
        json.dumps(
            {
                "symbols": want,
                "days": args.days,
                "batch_est_cost_usd": batch_cost,
                "downloaded": spent_note,
                "force": bool(args.force),
                "note": "No further Databento downloads without user OK",
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"DONE. Est. spend this run (if all miss): ${batch_cost:.4f}")
    print("LOCK: do not download more Databento until user OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
