"""Focused boost: widen BUY-only PULLBACK around champion to lift holdout n toward 40+."""

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

OUT = ROOT / "data" / "nq_focused_research"
CACHE = ROOT / "data" / "databento" / "NQ_1m_cache.parquet"

spec = importlib.util.spec_from_file_location("wr65", ROOT / "scripts" / "run_nq_wr65_search.py")
wr = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(wr)


def main() -> None:
    df = pd.read_parquet(CACHE)
    df = df[df["close"] >= 10000].sort_index()
    print(f"bars={len(df)} {df.index.min()} -> {df.index.max()}", flush=True)
    df5 = build_context_5m(df)
    splits = rolling_walk_forward_splits(df5.index, n_folds=5, holdout_frac=0.20)
    print(f"holdout_days={splits['n_holdout_days']}", flush=True)

    windows = ("1000_1130", "1000_1200", "0930_1130")
    exits = (1.0, 1.15, 1.25)
    zones = (0.35, 0.45, 0.55)
    stops = (0.45, 0.55, 0.65)
    vbufs = (0.10, 0.20)
    cds = (3, 4, 5)
    grid = list(itertools.product(windows, zones, stops, vbufs, cds))
    print(f"grid={len(grid)}", flush=True)

    ready, best = [], None
    for i, (window, zone, stop, vbuf, cd) in enumerate(grid, 1):
        if i % 20 == 0 or i == 1:
            print(f"[{i}/{len(grid)}] ready={len(ready)}", flush=True)
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
        if len(cands) < 40:
            continue
        for ex in exits:
            trades = realize_trades(cands, df, target_r=ex, min_target_r=0.95)
            if len(trades) < 40:
                continue
            val_all = []
            for fold in splits["folds"]:
                val_all.extend(filter_by_days(trades, fold["val_days"]))
            val_u = wr._dedupe(val_all)
            hold = filter_by_days(trades, splits["holdout_days"])
            st_va, st_ho = stats_for(val_u), stats_for(hold)
            frows = wr.fold_stats(trades, splits["folds"])
            ok, reasons = wr.passes_consistency(frows, st_ho, st_va)
            comfortable = ok and int(st_ho["n"]) >= 40
            score = wr.comfort_score(frows, st_ho, st_va)
            if int(st_ho["n"]) >= 40:
                score += 30
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
                "consistency_ok": ok,
                "comfortable": comfortable,
                "fail_reasons": reasons,
                "comfort_score": score,
                "mean_fold_wr": sum(r["wr"] for r in frows if r["n"] >= 5)
                / max(1, sum(1 for r in frows if r["n"] >= 5)),
                "min_fold_wr": min((r["wr"] for r in frows if r["n"] >= 5), default=0.0),
            }
            if ok:
                ready.append(cell)
                tag = "COMFORTABLE" if comfortable else "READY"
                print(
                    f"{tag} {window} {ex}R cd={cd} zone={zone} "
                    f"n={st_ho['n']} WR={st_ho['wr']} PF={st_ho['pf']} E={st_ho['expectancy_r']}",
                    flush=True,
                )
            if best is None or score > best["comfort_score"]:
                best = cell

    ready = sorted(
        ready,
        key=lambda c: (c["comfortable"], c["holdout"]["n"], c["holdout"]["wr"]),
        reverse=True,
    )
    comfort = [c for c in ready if c["comfortable"]]
    verdict = (
        "NQ STRATEGY READY FOR DEMO"
        if comfort
        else ("NQ_WR65_HIT_SAMPLE_THIN" if ready else "NQ STRATEGY NOT YET GOOD ENOUGH")
    )
    champ = (comfort or ready or [best])[0]
    out = {
        "verdict": verdict,
        "ready_count": len(ready),
        "comfortable_count": len(comfort),
        "champion": champ,
        "ready_top": ready[:12],
        "bars": len(df),
        "range": [str(df.index.min()), str(df.index.max())],
    }
    (OUT / "nq_wr65_boost.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    (OUT / "NQ_WR65_BOOST_REPORT.md").write_text(
        "\n".join(
            [
                "# NQ WR≥65% Sample Boost",
                "",
                f"**Verdict:** `{verdict}`",
                f"Ready={len(ready)} Comfortable={len(comfort)}",
                "",
                "## Champion",
                f"```\n{json.dumps(champ, indent=2, default=str)}\n```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    # update main pointer
    (OUT / "NQ_FOCUSED_RESEARCH_REPORT.md").write_text(
        "\n".join(
            [
                "# NQ Focused Research Report (latest)",
                "",
                f"**Verdict:** `{verdict}`",
                "",
                "Champion family: **PULLBACK BUY-only / NY late morning / signal_close / ~1.0–1.25R**",
                "",
                f"```\n{json.dumps(champ, indent=2, default=str)}\n```",
                "",
                "See `NQ_WR65_DENSE_REPORT.md` and `NQ_WR65_BOOST_REPORT.md`.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("VERDICT", verdict, flush=True)
    print(
        "CHAMP",
        champ.get("window"),
        champ.get("exit"),
        "hold",
        champ.get("holdout"),
        "meanF",
        champ.get("mean_fold_wr"),
        "minF",
        champ.get("min_fold_wr"),
        flush=True,
    )


if __name__ == "__main__":
    main()
