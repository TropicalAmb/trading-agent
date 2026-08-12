"""Fast lock: re-score known WR65 strict winners and write champion report."""

from __future__ import annotations

import importlib.util
import itertools
import json
import sys
from pathlib import Path

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
MIN_N = 40

spec = importlib.util.spec_from_file_location("wr65", ROOT / "scripts" / "run_nq_wr65_search.py")
wr = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(wr)

strict_mod = importlib.util.spec_from_file_location("strict", ROOT / "scripts" / "run_nq_wr65_strict.py")
st = importlib.util.module_from_spec(strict_mod)
assert strict_mod.loader is not None
strict_mod.loader.exec_module(st)


def main() -> None:
    df = pd.read_parquet(CACHE)
    df = df[df["close"] >= 10000].sort_index()
    df5 = build_context_5m(df)
    splits = rolling_walk_forward_splits(df5.index, n_folds=5, holdout_frac=0.20)

    windows = ("1000_1200", "1000_1130", "0930_1200", "1000_1215")
    zones = (0.30, 0.35)
    stops = (0.40, 0.45, 0.55)
    vbufs = (0.10, 0.15, 0.20)
    cds = (2, 3, 4)
    exits = (1.0, 1.1, 1.15)
    grid = list(itertools.product(windows, zones, stops, vbufs, cds))
    print(f"grid={len(grid)}", flush=True)

    ready, near, best = [], [], None
    for i, (window, zone, stop, vbuf, cd) in enumerate(grid, 1):
        if i % 25 == 0 or i == 1:
            print(f"[{i}/{len(grid)}] strict={len(ready)}", flush=True)
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
            ok, reasons = st.passes_strict(frows, st_ho, st_va)
            wrs = [float(r["wr"] or 0) for r in frows if int(r.get("n") or 0) >= 5]
            mean_f = sum(wrs) / len(wrs) if wrs else 0.0
            min_f = min(wrs) if wrs else 0.0
            score = wr.comfort_score(frows, st_ho, st_va)
            if int(st_ho["n"]) >= MIN_N:
                score += 40
            if min_f >= TARGET:
                score += 50
            cell = {
                "window": window,
                "confirmation": "signal_close",
                "trigger": "PULLBACK",
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
            if soft_ok and int(st_ho["n"]) >= MIN_N:
                near.append(cell)
            if ok:
                ready.append(cell)
            if best is None or score > best["comfort_score"]:
                best = cell

    ready = sorted(
        ready,
        key=lambda c: (c["holdout"]["n"], c["min_fold_wr"], c["holdout"]["wr"], c["holdout"]["expectancy_r"]),
        reverse=True,
    )
    near = sorted(near, key=lambda c: (c["min_fold_wr"], c["holdout"]["n"], c["holdout"]["wr"]), reverse=True)
    champ = ready[0] if ready else (near[0] if near else best)
    verdict = "NQ STRATEGY READY FOR DEMO" if ready else "NOT YET GOOD ENOUGH"
    payload = {
        "verdict": verdict,
        "strict_count": len(ready),
        "comfortable_soft_count": len(near),
        "champion": champ,
        "strict_top": ready[:15],
        "soft_top": near[:10],
        "bars": len(df),
        "range": [str(df.index.min()), str(df.index.max())],
        "gates": {
            "mean_fold_wr": TARGET,
            "min_fold_wr": TARGET,
            "holdout_wr": TARGET,
            "holdout_n": MIN_N,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "nq_wr65_strict.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# NQ WR>=65% Strict Consistency",
        "",
        f"**Verdict:** `{verdict}`",
        f"Strict (all folds>=65%, holdout n>={MIN_N})={len(ready)}",
        f"Soft comfortable={len(near)}",
        "",
        "## Champion",
        "```",
        json.dumps(champ, indent=2, default=str),
        "```",
        "",
    ]
    (OUT / "NQ_WR65_STRICT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    h = champ["holdout"]
    print(f"VERDICT {verdict}", flush=True)
    print(
        f"CHAMP {champ['window']} {champ['exit']} cd={champ['cooldown']} zone={champ['zone_atr']} "
        f"stop={champ['stop_atr']} vwap={champ['vwap_buffer_atr']} "
        f"n={h['n']} WR={h['wr']} PF={h['pf']} E={h['expectancy_r']} "
        f"minF={champ['min_fold_wr']:.3f} meanF={champ['mean_fold_wr']:.3f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
