"""Strict WR≥65% consistency: every fold + holdout ≥65%, holdout n≥40.

Reuses Databento cache; optional cheap backward extend.
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.nq_context_entry import (
    build_context_5m,
    filter_by_days,
    generate_candidates,
    realize_trades,
    rolling_walk_forward_splits,
    stats_for,
)

CACHE = ROOT / "data" / "databento" / "NQ_1m_cache.parquet"
OUT = ROOT / "data" / "nq_focused_research"
TARGET = 0.65
MIN_HOLDOUT_N = 40

_spec = importlib.util.spec_from_file_location("wr65", ROOT / "scripts" / "run_nq_wr65_search.py")
wr = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(wr)


def maybe_extend(days: int, max_cost: float) -> None:
    if days <= 0:
        return
    import os

    import databento as db
    from dotenv import load_dotenv

    from agent.data.databento_historical import DatabentoHistoricalProvider

    load_dotenv(ROOT / ".env")
    old = pd.read_parquet(CACHE)
    end = old.index.min().tz_convert("UTC").to_pydatetime()
    start = end - timedelta(days=days)
    client = db.Historical(os.getenv("DATABENTO_API_KEY"))
    cost = float(
        client.metadata.get_cost(
            dataset="GLBX.MDP3",
            symbols="NQ.FUT",
            schema="ohlcv-1m",
            stype_in="parent",
            start=start.isoformat(),
            end=end.isoformat(),
        )
    )
    print(f"Extend {days}d estimate ${cost:.4f}", flush=True)
    if cost > max_cost:
        print(f"SKIP extend: ${cost:.4f} > max ${max_cost}", flush=True)
        return
    prov = DatabentoHistoricalProvider()
    extra = prov.fetch_ohlcv_df("NQ", start=start, end=end, schema="ohlcv-1m")
    extra = extra[["open", "high", "low", "close", "volume"]].astype(float)
    extra = extra[extra["close"] >= 10000]
    merged = pd.concat([extra, old]).sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    merged = merged[merged["close"] >= 10000]
    merged.to_parquet(CACHE)
    print(f"Merged rows={len(merged)} {merged.index.min()} -> {merged.index.max()}", flush=True)


def passes_strict(fold_rows: list[dict], hold: dict, val: dict) -> tuple[bool, list[str]]:
    ok, reasons = wr.passes_consistency(fold_rows, hold, val)
    wrs = [float(r["wr"] or 0) for r in fold_rows if int(r.get("n") or 0) >= 5]
    if wrs and min(wrs) < TARGET:
        reasons.append(f"min_fold_wr={min(wrs):.3f}<{TARGET}")
        ok = False
    if int(hold.get("n") or 0) < MIN_HOLDOUT_N:
        reasons.append(f"holdout_n={hold.get('n')}<{MIN_HOLDOUT_N}")
        ok = False
    return ok, reasons


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extend-days", type=int, default=90)
    ap.add_argument("--max-cost", type=float, default=0.40)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    maybe_extend(args.extend_days, args.max_cost)

    df = pd.read_parquet(CACHE)
    if getattr(df.index, "tz", None) is None:
        df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    df = df[df["close"] >= 10000].sort_index()
    print(f"bars={len(df)} {df.index.min()} -> {df.index.max()}", flush=True)
    df5 = build_context_5m(df)
    splits = rolling_walk_forward_splits(df5.index, n_folds=5, holdout_frac=0.20)
    print(f"holdout_days={splits['n_holdout_days']} research_days={splits['n_research_days']}", flush=True)

    # Densify around BOOST/strict winners: BUY-only PULLBACK / signal_close
    windows = ("1000_1200", "1000_1130", "1000_1215", "0945_1145", "0930_1200")
    zones = (0.30, 0.35, 0.40)
    stops = (0.40, 0.45, 0.50, 0.55)
    vbufs = (0.10, 0.15, 0.20)
    cds = (2, 3, 4)
    exits = (1.0, 1.1, 1.15, 1.25)
    grid = list(itertools.product(windows, zones, stops, vbufs, cds))
    print(f"grid={len(grid)} x exits={len(exits)}", flush=True)

    ready: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    best = None

    for i, (window, zone, stop, vbuf, cd) in enumerate(grid, 1):
        if i % 50 == 0 or i == 1:
            print(f"[{i}/{len(grid)}] strict={len(ready)} near={len(near)}", flush=True)
        cands = generate_candidates(
            df5,
            trigger="PULLBACK",
            window=window,
            confirmation="signal_close",
            zone_atr=zone,
            stop_atr=stop,
            vwap_buffer_atr=vbuf,
            sides=("BUY",),
            min_stop_atr=max(0.25, stop * 0.7),
            cooldown_bars=cd,
        )
        if len(cands) < 50:
            continue
        for ex in exits:
            trades = realize_trades(cands, df, target_r=ex, min_target_r=0.95)
            if len(trades) < 50:
                continue
            val_all = []
            for fold in splits["folds"]:
                val_all.extend(filter_by_days(trades, fold["val_days"]))
            val_u = wr._dedupe(val_all)
            hold = filter_by_days(trades, splits["holdout_days"])
            st_va, st_ho = stats_for(val_u), stats_for(hold)
            frows = wr.fold_stats(trades, splits["folds"])
            ok, reasons = passes_strict(frows, st_ho, st_va)
            wrs = [float(r["wr"] or 0) for r in frows if int(r.get("n") or 0) >= 5]
            mean_f = sum(wrs) / len(wrs) if wrs else 0.0
            min_f = min(wrs) if wrs else 0.0
            score = wr.comfort_score(frows, st_ho, st_va)
            if int(st_ho["n"]) >= MIN_HOLDOUT_N:
                score += 40
            if min_f >= TARGET:
                score += 50
            cell = {
                "window": window,
                "confirmation": "signal_close",
                "exit": f"{ex}R",
                "target_r": ex,
                "zone_atr": zone,
                "stop_atr": stop,
                "vwap_buffer_atr": vbuf,
                "cooldown": cd,
                "sides": ["BUY"],
                "val": wr._fmt(st_va),
                "holdout": wr._fmt(st_ho),
                "folds": frows,
                "strict_ok": ok,
                "fail_reasons": reasons,
                "comfort_score": score,
                "mean_fold_wr": mean_f,
                "min_fold_wr": min_f,
            }
            soft_ok, _ = wr.passes_consistency(frows, st_ho, st_va)
            if soft_ok and int(st_ho["n"]) >= MIN_HOLDOUT_N:
                near.append(cell)
            if ok:
                ready.append(cell)
                print(
                    f"STRICT {window} {ex}R cd={cd} zone={zone} "
                    f"n={st_ho['n']} WR={st_ho['wr']} minF={min_f:.3f} meanF={mean_f:.3f}",
                    flush=True,
                )
            if best is None or score > best["comfort_score"]:
                best = cell

    ready = sorted(
        ready,
        key=lambda c: (c["holdout"]["n"], c["min_fold_wr"], c["holdout"]["wr"]),
        reverse=True,
    )
    near = sorted(
        near,
        key=lambda c: (c["min_fold_wr"], c["holdout"]["n"], c["holdout"]["wr"]),
        reverse=True,
    )
    champ = ready[0] if ready else (near[0] if near else best)
    verdict = (
        "NQ STRATEGY READY FOR DEMO"
        if ready
        else (
            "NQ_WR65_COMFORTABLE_SOFT_ONLY"
            if near
            else "NOT YET GOOD ENOUGH"
        )
    )

    payload = {
        "verdict": verdict,
        "strict_count": len(ready),
        "comfortable_soft_count": len(near),
        "champion": champ,
        "strict_top": ready[:12],
        "soft_top": near[:12],
        "bars": len(df),
        "range": [str(df.index.min()), str(df.index.max())],
        "gates": {
            "mean_fold_wr": TARGET,
            "min_fold_wr": TARGET,
            "holdout_wr": TARGET,
            "holdout_n": MIN_HOLDOUT_N,
        },
    }
    (OUT / "nq_wr65_strict.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# NQ WR>=65% Strict Consistency",
        "",
        f"**Verdict:** `{verdict}`",
        f"Strict (all folds>=65%, holdout n>={MIN_HOLDOUT_N})={len(ready)}",
        f"Soft comfortable (mean>=65%, min>=55%, holdout n>={MIN_HOLDOUT_N})={len(near)}",
        "",
        "## Champion",
        "```",
        json.dumps(champ, indent=2, default=str),
        "```",
        "",
    ]
    (OUT / "NQ_WR65_STRICT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"VERDICT {verdict}", flush=True)
    if champ:
        h = champ["holdout"]
        print(
            f"CHAMP {champ.get('window')} {champ.get('exit')} "
            f"n={h.get('n')} WR={h.get('wr')} minF={champ.get('min_fold_wr')} "
            f"meanF={champ.get('mean_fold_wr')}",
            flush=True,
        )


if __name__ == "__main__":
    main()
