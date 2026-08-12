"""Densify around WR65 winner family; optional cheap cache extension.

Seed: PULLBACK / 10:00-11:30 / signal_close / ~1.0-1.25R
Comfortable = consistency gates + holdout n>=40.
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.data.databento_historical import DatabentoHistoricalProvider
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

# load helper module without package install
_spec = importlib.util.spec_from_file_location(
    "wr65", ROOT / "scripts" / "run_nq_wr65_search.py"
)
_wr = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_wr)


def maybe_extend(days: int, max_cost: float) -> None:
    if days <= 0:
        return
    import os
    from dotenv import load_dotenv
    import databento as db

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


def run(*, extend_days: int, max_cost: float) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    maybe_extend(extend_days, max_cost)

    df_1m = pd.read_parquet(CACHE)
    if getattr(df_1m.index, "tz", None) is None:
        df_1m.index = pd.to_datetime(df_1m.index, utc=True).tz_convert("America/New_York")
    df_1m = df_1m[df_1m["close"] >= 10000].sort_index()
    print(f"Cache {len(df_1m)} {df_1m.index.min()} -> {df_1m.index.max()}", flush=True)
    df5 = build_context_5m(df_1m)
    splits = rolling_walk_forward_splits(df5.index, n_folds=5, holdout_frac=0.20)
    print(
        f"folds={len(splits['folds'])} research={splits['n_research_days']} holdout={splits['n_holdout_days']}",
        flush=True,
    )

    windows = ("1000_1130", "0930_1100", "0930_1030")
    confirms = ("signal_close", "next_bar")
    exits = (1.0, 1.1, 1.15, 1.25)
    zones = (0.25, 0.30, 0.35, 0.40, 0.45)
    stops = (0.40, 0.45, 0.50, 0.55, 0.60)
    side_opts = (("BUY", "SELL"), ("BUY",))
    vbufs = (0.05, 0.10, 0.15)
    cooldowns = (4, 6)

    cand_grid = list(
        itertools.product(windows, confirms, zones, stops, side_opts, vbufs, cooldowns)
    )
    print(f"Dense candidate configs={len(cand_grid)} x exits={len(exits)}", flush=True)

    cells, ready, best = [], [], None
    cache: dict[tuple, list] = {}

    for i, (window, conf, zone, stop, sides, vbuf, cd) in enumerate(cand_grid, 1):
        if i % 50 == 0 or i == 1:
            print(
                f"[{i}/{len(cand_grid)}] ready={len(ready)} best={(best or {}).get('comfort_score')}",
                flush=True,
            )
        key = (window, conf, zone, stop, sides, vbuf, cd)
        if key not in cache:
            cache[key] = generate_candidates(
                df5,
                trigger="PULLBACK",
                window=window,
                confirmation=conf,
                zone_atr=zone,
                stop_atr=stop,
                vwap_buffer_atr=vbuf,
                sides=sides,
                min_stop_atr=max(0.25, stop * 0.75),
                cooldown_bars=cd,
            )
        cands = cache[key]
        if len(cands) < 30:
            continue
        for ex in exits:
            trades = realize_trades(cands, df_1m, target_r=ex, min_target_r=0.95)
            if len(trades) < 30:
                continue
            train_all, val_all = [], []
            for fold in splits["folds"]:
                train_all.extend(filter_by_days(trades, fold["train_days"]))
                val_all.extend(filter_by_days(trades, fold["val_days"]))
            train_u, val_u = _wr._dedupe(train_all), _wr._dedupe(val_all)
            hold = filter_by_days(trades, splits["holdout_days"])
            st_tr, st_va, st_ho = stats_for(train_u), stats_for(val_u), stats_for(hold)
            frows = _wr.fold_stats(trades, splits["folds"])
            ok, reasons = _wr.passes_consistency(frows, st_ho, st_va)
            comfortable = ok and int(st_ho.get("n") or 0) >= 40
            score = _wr.comfort_score(frows, st_ho, st_va) + (
                25 if int(st_ho.get("n") or 0) >= 40 else 0
            )
            cell = {
                "window": window,
                "confirmation": conf,
                "exit": f"{ex}R",
                "target_r": ex,
                "zone_atr": zone,
                "stop_atr": stop,
                "vwap_buffer_atr": vbuf,
                "cooldown": cd,
                "sides": list(sides),
                "n_cands": len(cands),
                "train": _wr._fmt(st_tr),
                "val": _wr._fmt(st_va),
                "holdout": _wr._fmt(st_ho),
                "folds": frows,
                "consistency_ok": ok,
                "comfortable": comfortable,
                "fail_reasons": reasons,
                "comfort_score": score,
                "mean_fold_wr": (
                    sum(float(r["wr"] or 0) for r in frows if int(r.get("n") or 0) >= 5)
                    / max(1, sum(1 for r in frows if int(r.get("n") or 0) >= 5))
                ),
                "min_fold_wr": min(
                    (float(r["wr"] or 0) for r in frows if int(r.get("n") or 0) >= 5),
                    default=0.0,
                ),
            }
            cells.append(cell)
            if ok:
                ready.append(cell)
                tag = "COMFORTABLE" if comfortable else "READY"
                print(
                    f"{tag} {window} {conf} {ex}R cd={cd} sides={sides} "
                    f"hold n={st_ho['n']} WR={st_ho['wr']} PF={st_ho['pf']} E={st_ho['expectancy_r']}",
                    flush=True,
                )
            if best is None or score > best["comfort_score"]:
                best = cell

    cells_sorted = sorted(cells, key=lambda c: c["comfort_score"], reverse=True)
    ready_sorted = sorted(
        ready,
        key=lambda c: (int(c.get("comfortable") or 0), c["holdout"]["n"], c["holdout"]["wr"]),
        reverse=True,
    )
    comfortable = [c for c in ready_sorted if c.get("comfortable")]
    if comfortable:
        verdict = "NQ STRATEGY READY FOR DEMO"
    elif ready_sorted:
        verdict = "NQ_WR65_HIT_SAMPLE_THIN"
    else:
        verdict = "NQ STRATEGY NOT YET GOOD ENOUGH"

    champion = (comfortable or ready_sorted or cells_sorted or [None])[0]
    report = {
        "target_wr": _wr.TARGET_WR,
        "verdict": verdict,
        "bars": len(df_1m),
        "range": [str(df_1m.index.min()), str(df_1m.index.max())],
        "ready_count": len(ready_sorted),
        "comfortable_count": len(comfortable),
        "champion": champion,
        "ready_top": ready_sorted[:15],
        "comfortable_top": comfortable[:10],
        "closest_top10": cells_sorted[:10],
        "finished_utc": datetime.now(timezone.utc).isoformat(),
    }
    (OUT / "nq_wr65_dense.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (OUT / "NQ_WR65_DENSE_REPORT.md").write_text(
        "\n".join(
            [
                "# NQ WR≥65% Dense Iteration",
                "",
                f"**Verdict:** `{verdict}`",
                f"Ready: {len(ready_sorted)} | Comfortable (holdout n≥40 + gates): {len(comfortable)}",
                f"Range: `{report['range'][0]}` → `{report['range'][1]}` ({len(df_1m)} bars)",
                "",
                "## Champion",
                f"```\n{json.dumps(champion, indent=2, default=str)}\n```",
                "",
                "## Comfortable",
                f"```\n{json.dumps(comfortable[:5], indent=2, default=str)}\n```",
                "",
                "## Ready top",
                f"```\n{json.dumps(ready_sorted[:5], indent=2, default=str)}\n```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (OUT / "NQ_FOCUSED_RESEARCH_REPORT.md").write_text(
        "\n".join(
            [
                "# NQ Focused Research Report (latest)",
                "",
                f"**Verdict:** `{verdict}`",
                "",
                "Primary docs: `NQ_WR65_DENSE_REPORT.md`, `NQ_WR65_SEARCH_REPORT.md`.",
                "",
                "## Champion",
                f"```\n{json.dumps(champion, indent=2, default=str)}\n```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("VERDICT:", verdict, flush=True)
    if champion:
        print(
            "CHAMPION",
            champion.get("window"),
            champion.get("confirmation"),
            champion.get("exit"),
            "hold",
            champion.get("holdout"),
            "meanF",
            champion.get("mean_fold_wr"),
            flush=True,
        )
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--extend-days", type=int, default=60)
    ap.add_argument("--max-cost-usd", type=float, default=0.35)
    args = ap.parse_args()
    run(extend_days=args.extend_days, max_cost=args.max_cost_usd)
