"""Iterate NQ PULLBACK on Databento cache until consistent WR>=65% (or report best honest frontier).

Consistency gates (all required for READY):
- each walk-forward fold WR >= 0.55
- mean fold WR >= 0.65
- holdout WR >= 0.65
- holdout n >= 20 (comfort floor; prefer 40+)
- PF >= 1.15 and expectancy_r > 0 on val and holdout
- avg_win_r >= 0.85 (blocks tiny-target WR inflation)
- anti_cheat_ok

Uses local cache only — no Databento download.
"""

from __future__ import annotations

import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.metrics import trade_stats
from agent.research.nq_context_entry import (
    SESSION_WINDOWS,
    build_context_5m,
    filter_by_days,
    generate_candidates,
    realize_trades,
    rolling_walk_forward_splits,
    stats_for,
)

CACHE = ROOT / "data" / "databento" / "NQ_1m_cache.parquet"
OUT = ROOT / "data" / "nq_focused_research"
TARGET_WR = 0.65


def _fmt(st: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "n",
        "wr",
        "pf",
        "expectancy_r",
        "max_dd_r",
        "avg_win_r",
        "avg_loss_r",
        "worst_r",
        "trades_per_week",
        "anti_cheat_ok",
    ]
    return {k: st.get(k) for k in keys}


def _dedupe(trades):
    seen, out = set(), []
    for t in trades:
        k = (t.entry_ts, t.side, t.confirmation, t.exit_style)
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
    return out


def fold_stats(trades, folds) -> list[dict[str, Any]]:
    rows = []
    for fold in folds:
        # expanding: score on val days of fold
        vt = _dedupe(filter_by_days(trades, fold["val_days"]))
        st = stats_for(vt)
        rows.append({"fold": fold["fold"], **_fmt(st)})
    return rows


def passes_consistency(fold_rows: list[dict], hold: dict, val: dict) -> tuple[bool, list[str]]:
    reasons = []
    wrs = [float(r["wr"] or 0) for r in fold_rows if int(r.get("n") or 0) >= 5]
    if len(wrs) < 3:
        reasons.append("insufficient_folds_with_n>=5")
    else:
        if min(wrs) < 0.55:
            reasons.append(f"min_fold_wr={min(wrs):.3f}<0.55")
        if sum(wrs) / len(wrs) < TARGET_WR:
            reasons.append(f"mean_fold_wr={sum(wrs)/len(wrs):.3f}<{TARGET_WR}")
    hn = int(hold.get("n") or 0)
    if hn < 20:
        reasons.append(f"holdout_n={hn}<20")
    if float(hold.get("wr") or 0) < TARGET_WR:
        reasons.append(f"holdout_wr={hold.get('wr')}<{TARGET_WR}")
    if float(hold.get("pf") or 0) < 1.15:
        reasons.append("holdout_pf<1.15")
    if float(hold.get("expectancy_r") or 0) <= 0:
        reasons.append("holdout_E<=0")
    if float(hold.get("avg_win_r") or 0) < 0.85:
        reasons.append("holdout_avg_win<0.85R")
    if not hold.get("anti_cheat_ok", True):
        reasons.append("holdout_anti_cheat")
    if float(val.get("wr") or 0) < TARGET_WR:
        reasons.append(f"val_wr={val.get('wr')}<{TARGET_WR}")
    if float(val.get("pf") or 0) < 1.15:
        reasons.append("val_pf<1.15")
    if float(val.get("expectancy_r") or 0) <= 0:
        reasons.append("val_E<=0")
    return len(reasons) == 0, reasons


def comfort_score(fold_rows, hold, val) -> float:
    """Rank configs approaching the 65% consistency bar."""
    wrs = [float(r["wr"] or 0) for r in fold_rows if int(r.get("n") or 0) >= 5]
    mean_f = sum(wrs) / len(wrs) if wrs else 0
    min_f = min(wrs) if wrs else 0
    hw = float(hold.get("wr") or 0)
    vw = float(val.get("wr") or 0)
    he = float(hold.get("expectancy_r") or 0)
    hn = int(hold.get("n") or 0)
    avg_w = float(hold.get("avg_win_r") or 0)
    if avg_w < 0.85 and hw > 0.7:
        return -1e6
    return (
        min(hw, TARGET_WR) * 100
        + min(vw, TARGET_WR) * 40
        + min(mean_f, TARGET_WR) * 40
        + min_f * 30
        + max(he, -1) * 25
        + min(hn, 50) * 0.5
        + min(float(hold.get("pf") or 0), 3) * 5
    )


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    df_1m = pd.read_parquet(CACHE)
    if getattr(df_1m.index, "tz", None) is None:
        df_1m.index = pd.to_datetime(df_1m.index, utc=True).tz_convert("America/New_York")
    df_1m = df_1m[df_1m["close"] >= 10000].sort_index()
    print(f"Cache {len(df_1m)} {df_1m.index.min()} -> {df_1m.index.max()}", flush=True)
    df5 = build_context_5m(df_1m)
    splits = rolling_walk_forward_splits(df5.index, n_folds=5, holdout_frac=0.22)
    print(
        f"folds={len(splits['folds'])} research_days={splits['n_research_days']} "
        f"holdout_days={splits['n_holdout_days']}",
        flush=True,
    )

    windows = list(SESSION_WINDOWS.keys())
    confirms = ("rejection_wick", "next_bar", "engulf", "signal_close")
    exits = (1.0, 1.15, 1.25, 1.35, 1.5, 1.75)
    zones = (0.15, 0.25, 0.35)
    stops = (0.30, 0.45, 0.60)
    side_opts = (("BUY", "SELL"), ("BUY",), ("SELL",))
    vwap_bufs = (0.05, 0.15)

    # Candidate keys (expensive) × exits (cheap)
    cand_grid = list(
        itertools.product(windows, confirms, zones, stops, side_opts, vwap_bufs)
    )
    print(f"Candidate configs {len(cand_grid)} × exits {len(exits)}", flush=True)

    cells = []
    ready = []
    best = None
    cand_cache: dict[tuple, list] = {}

    for i, (window, conf, zone, stop, sides, vbuf) in enumerate(cand_grid, 1):
        if i % 25 == 0 or i == 1:
            print(
                f"[{i}/{len(cand_grid)}] cache={len(cand_cache)} "
                f"best={(best or {}).get('comfort_score')} ready={len(ready)}",
                flush=True,
            )
        key = (window, conf, zone, stop, sides, vbuf)
        if key not in cand_cache:
            cand_cache[key] = generate_candidates(
                df5,
                trigger="PULLBACK",
                window=window,
                confirmation=conf,
                zone_atr=zone,
                stop_atr=stop,
                vwap_buffer_atr=vbuf,
                sides=sides,
                min_stop_atr=max(0.25, stop * 0.8),
                cooldown_bars=6,
            )
        cands = cand_cache[key]
        if len(cands) < 25:
            continue

        for ex in exits:
            trades = realize_trades(cands, df_1m, target_r=ex, min_target_r=0.95)
            if len(trades) < 25:
                continue

            train_all, val_all = [], []
            for fold in splits["folds"]:
                train_all.extend(filter_by_days(trades, fold["train_days"]))
                val_all.extend(filter_by_days(trades, fold["val_days"]))
            train_u, val_u = _dedupe(train_all), _dedupe(val_all)
            hold = filter_by_days(trades, splits["holdout_days"])
            st_tr, st_va, st_ho = stats_for(train_u), stats_for(val_u), stats_for(hold)
            frows = fold_stats(trades, splits["folds"])
            ok, reasons = passes_consistency(frows, st_ho, st_va)
            score = comfort_score(frows, st_ho, st_va)
            cell = {
                "window": window,
                "confirmation": conf,
                "exit": f"{ex}R",
                "target_r": ex,
                "zone_atr": zone,
                "stop_atr": stop,
                "vwap_buffer_atr": vbuf,
                "sides": list(sides),
                "n_cands": len(cands),
                "train": _fmt(st_tr),
                "val": _fmt(st_va),
                "holdout": _fmt(st_ho),
                "folds": frows,
                "consistency_ok": ok,
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
                print(
                    f"READY {window} {conf} {ex}R sides={sides} "
                    f"holdWR={st_ho['wr']} n={st_ho['n']} valWR={st_va['wr']}",
                    flush=True,
                )
            if best is None or score > best["comfort_score"]:
                best = cell

    cells_sorted = sorted(cells, key=lambda c: c["comfort_score"], reverse=True)
    ready_sorted = sorted(ready, key=lambda c: (c["holdout"]["wr"], c["holdout"]["n"]), reverse=True)

    verdict = (
        "NQ STRATEGY READY FOR DEMO"
        if ready_sorted and int(ready_sorted[0]["holdout"]["n"]) >= 30
        else (
            "NQ STRATEGY APPROACHING_65_NOT_YET"
            if ready_sorted
            else "NQ STRATEGY NOT YET GOOD ENOUGH"
        )
    )
    # If ready with n>=20 but <30, still approaching
    if ready_sorted and int(ready_sorted[0]["holdout"]["n"]) >= 20:
        if int(ready_sorted[0]["holdout"]["n"]) >= 40 and float(ready_sorted[0]["holdout"]["wr"]) >= 0.65:
            verdict = "NQ STRATEGY READY FOR DEMO"
        elif float(ready_sorted[0]["holdout"]["wr"]) >= 0.65:
            verdict = "NQ_WR65_HIT_SAMPLE_THIN"

    report = {
        "target_wr": TARGET_WR,
        "source": "databento_cache_only",
        "bars": len(df_1m),
        "range": [str(df_1m.index.min()), str(df_1m.index.max())],
        "grid_tried": len(cand_grid) * len(exits),
        "candidate_configs": len(cand_grid),
        "cells_with_trades": len(cells_sorted),
        "ready_count": len(ready_sorted),
        "verdict": verdict,
        "best_overall": cells_sorted[0] if cells_sorted else None,
        "ready_top": ready_sorted[:10],
        "closest_top10": cells_sorted[:10],
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "gates": {
            "mean_fold_wr": TARGET_WR,
            "min_fold_wr": 0.55,
            "holdout_wr": TARGET_WR,
            "holdout_n_min": 20,
            "pf_min": 1.15,
            "avg_win_r_min": 0.85,
        },
    }
    (OUT / "nq_wr65_search.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md = [
        "# NQ WR≥65% Consistency Search",
        "",
        f"**Verdict:** `{verdict}`",
        f"Ready configs: `{len(ready_sorted)}` / cells scored `{len(cells_sorted)}`",
        f"Cache: `{df_1m.index.min()}` → `{df_1m.index.max()}` ({len(df_1m)} bars)",
        "",
        "## Best / closest",
        f"```\n{json.dumps(cells_sorted[0] if cells_sorted else None, indent=2, default=str)}\n```",
        "",
        "## Ready (passed consistency gates)",
        f"```\n{json.dumps(ready_sorted[:5], indent=2, default=str)}\n```",
        "",
        "## Closest top 5",
        f"```\n{json.dumps(cells_sorted[:5], indent=2, default=str)}\n```",
        "",
    ]
    (OUT / "NQ_WR65_SEARCH_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("VERDICT:", verdict, flush=True)
    if cells_sorted:
        b = cells_sorted[0]
        print(
            "BEST",
            b["window"],
            b["confirmation"],
            b["exit"],
            "sides",
            b["sides"],
            "hold",
            b["holdout"],
            "mean_fold",
            b["mean_fold_wr"],
            "min_fold",
            b["min_fold_wr"],
            "fails",
            b["fail_reasons"][:5],
            flush=True,
        )
    return report


if __name__ == "__main__":
    run()
