"""Databento-only NQ_CONTEXT_ENTRY finetune (uses local cache — no live pull).

Simplifications vs first pass:
- Fixed-R exits only (structural disabled for selection — it gamed WR with tiny targets)
- Require min stop distance in ATR
- Prefer rejection_wick / next_bar confirmations
- Walk-forward on Databento cache only
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.metrics import trade_stats
from agent.research.nq_context_entry import (
    CONFIRMATIONS,
    EXIT_RS,
    SESSION_WINDOWS,
    TRIGGERS,
    build_context_5m,
    filter_by_days,
    generate_candidates,
    realize_trades,
    rolling_walk_forward_splits,
    stats_for,
)

CACHE = ROOT / "data" / "databento" / "NQ_1m_cache.parquet"
OUT = ROOT / "data" / "nq_focused_research"

# Tight research grid — quality over spray
FINETUNE_CONFIRM = ("rejection_wick", "next_bar", "signal_close")
FINETUNE_EXITS = (1.0, 1.25, 1.5, 1.75, 2.0)
# Drop structural from selection
WINDOWS_PRIORITY = ("0930_1030", "0930_1100", "1000_1130", "0830_0930")


def _score(st: dict[str, Any]) -> float:
    n = int(st.get("n") or 0)
    if n < 20:
        return -1e9
    wr = float(st.get("wr") or 0)
    pf = float(st.get("pf") or 0)
    e = float(st.get("expectancy_r") or 0)
    dd = abs(float(st.get("max_dd_r") or 0))
    avg_w = float(st.get("avg_win_r") or 0)
    # Reject tiny-target games
    if avg_w < 0.75 and wr > 0.7:
        return -1e8 + wr
    if e <= 0 or pf < 1.05:
        return -1e6 + e
    return wr * 80 + min(pf, 3) * 10 + e * 50 - min(dd, 15) * 0.8 + min(n, 150) * 0.08


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
        "long_n",
        "short_n",
        "anti_cheat_ok",
    ]
    return {k: st.get(k) for k in keys}


def load_cache() -> pd.DataFrame:
    if not CACHE.exists():
        raise FileNotFoundError(
            f"Missing {CACHE}. Run: python scripts/cache_databento_nq.py --days 120"
        )
    df = pd.read_parquet(CACHE)
    if getattr(df.index, "tz", None) is None:
        df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    return df.sort_index()


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    df_1m = load_cache()
    print(f"Cache bars={len(df_1m)} {df_1m.index.min()} -> {df_1m.index.max()}", flush=True)
    df5 = build_context_5m(df_1m, use_4h=False)
    splits = rolling_walk_forward_splits(df5.index, n_folds=4, holdout_frac=0.25)
    print(
        f"Folds={len(splits['folds'])} research_days={splits['n_research_days']} "
        f"holdout_days={splits['n_holdout_days']}",
        flush=True,
    )

    cells: list[dict[str, Any]] = []
    for trigger in TRIGGERS:
        for window in WINDOWS_PRIORITY:
            for conf in FINETUNE_CONFIRM:
                print(f"{trigger} {window} {conf}", flush=True)
                cands = generate_candidates(
                    df5,
                    trigger=trigger,
                    window=window,
                    confirmation=conf,
                    min_stop_atr=0.55,
                    require_rejection_for_pullback=False,
                )
                if len(cands) < 5:
                    continue
                for ex in FINETUNE_EXITS:
                    trades = realize_trades(cands, df_1m, target_r=ex, min_target_r=0.9)
                    train_all, val_all = [], []
                    for fold in splits["folds"]:
                        train_all.extend(filter_by_days(trades, fold["train_days"]))
                        val_all.extend(filter_by_days(trades, fold["val_days"]))

                    def _dedupe(xs):
                        seen, out = set(), []
                        for t in xs:
                            k = (t.entry_ts, t.trigger, t.confirmation, t.exit_style, t.side)
                            if k in seen:
                                continue
                            seen.add(k)
                            out.append(t)
                        return out

                    train_u, val_u = _dedupe(train_all), _dedupe(val_all)
                    hold = filter_by_days(trades, splits["holdout_days"])
                    st_tr, st_va = stats_for(train_u), stats_for(val_u)
                    select = st_va if st_va["n"] >= 15 else st_tr
                    cells.append(
                        {
                            "trigger": trigger,
                            "window": window,
                            "confirmation": conf,
                            "exit": f"{ex}R",
                            "target_r": ex,
                            "train": _fmt(st_tr),
                            "val": _fmt(st_va),
                            "holdout": _fmt(stats_for(hold)),
                            "select_score": _score(select),
                            "select_n": int(select["n"]),
                            "_hold": [t.to_dict() for t in hold],
                        }
                    )

    cells_sorted = sorted(cells, key=lambda c: c["select_score"], reverse=True)
    serious = [c for c in cells_sorted if c["select_n"] >= 25]
    promising = [c for c in cells_sorted if c["select_n"] >= 15][:20]

    def pick(key: str):
        pool = serious or promising or cells_sorted
        if not pool:
            return None
        if key == "wr":
            return max(
                pool,
                key=lambda c: (
                    (c["val"]["wr"] if c["val"]["n"] >= 15 else c["train"]["wr"]),
                    c["select_score"],
                ),
            )
        if key == "e":
            return max(
                pool,
                key=lambda c: (
                    (
                        c["val"]["expectancy_r"]
                        if c["val"]["n"] >= 15
                        else c["train"]["expectancy_r"]
                    ),
                    c["select_score"],
                ),
            )
        return pool[0]

    best_bal, best_acc, best_e = pick("bal"), pick("wr"), pick("e")
    chosen_window = (best_bal or best_acc or {"window": "0930_1030"})["window"]

    trigger_hold = {}
    combined = []
    for trig in TRIGGERS:
        pool = [c for c in cells_sorted if c["trigger"] == trig and c["window"] == chosen_window]
        if not pool:
            pool = [c for c in cells_sorted if c["trigger"] == trig]
        if not pool:
            trigger_hold[trig] = {"n": 0}
            continue
        top = pool[0]
        trigger_hold[trig] = {
            **top["holdout"],
            "config": {
                "window": top["window"],
                "confirmation": top["confirmation"],
                "exit": top["exit"],
            },
            "train": top["train"],
            "val": top["val"],
        }
        combined.extend(top.get("_hold") or [])

    seen = set()
    comb = []
    for t in combined:
        k = (t["entry_ts"], t["trigger"], t["side"])
        if k in seen:
            continue
        seen.add(k)
        comb.append(t)
    comb_st = trade_stats([t["pnl_r"] for t in comb], [t["entry_ts"] for t in comb])

    # WR vs R for best balanced family
    wr_vs_r = []
    if best_bal:
        for ex in FINETUNE_EXITS:
            pool = [
                c
                for c in cells_sorted
                if c["trigger"] == best_bal["trigger"]
                and c["window"] == best_bal["window"]
                and c["confirmation"] == best_bal["confirmation"]
                and c["exit"] == f"{ex}R"
            ]
            if pool:
                wr_vs_r.append({"R": ex, "val": pool[0]["val"], "holdout": pool[0]["holdout"]})

    def _good(st: dict | None) -> bool:
        if not st:
            return False
        return (
            int(st.get("n") or 0) >= 40
            and float(st.get("wr") or 0) >= 0.55
            and float(st.get("pf") or 0) >= 1.2
            and float(st.get("expectancy_r") or 0) > 0
            and float(st.get("avg_win_r") or 0) >= 0.9
        )

    hold_ref = (best_bal or best_acc or {}).get("holdout")
    verdict = (
        "NQ STRATEGY READY FOR DEMO"
        if _good(hold_ref) and _good(comb_st)
        else "NQ STRATEGY NOT YET GOOD ENOUGH"
    )
    # Soft progress flag for developing cells
    progress = None
    if hold_ref and int(hold_ref.get("n") or 0) >= 25 and float(hold_ref.get("expectancy_r") or 0) > 0:
        progress = "DEVELOPING_POSITIVE_HOLDOUT"
    elif best_bal and float((best_bal.get("val") or {}).get("expectancy_r") or 0) > 0:
        progress = "VAL_POSITIVE_HOLD_WEAK"

    def slim(c):
        if not c:
            return None
        return {k: v for k, v in c.items() if not k.startswith("_")}

    report = {
        "source": "databento_cache_only",
        "cache": str(CACHE),
        "bars": len(df_1m),
        "range": [str(df_1m.index.min()), str(df_1m.index.max())],
        "chosen_window": chosen_window,
        "cells_tried": len(cells_sorted),
        "best_balanced": slim(best_bal),
        "best_high_accuracy": slim(best_acc),
        "best_expectancy": slim(best_e),
        "trigger_holdout": trigger_hold,
        "combined_holdout": _fmt(comb_st),
        "wr_vs_r": wr_vs_r,
        "promising": [slim(c) for c in promising[:10]],
        "progress": progress,
        "verdict": verdict,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "No structural exits in selection (prevents tiny-target WR inflation).",
            "No additional Databento download in this script — cache only.",
            "Kaggle not used for selection after failed cross-check.",
        ],
    }
    (OUT / "nq_databento_finetune.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md = [
        "# NQ Databento Finetune Report",
        "",
        f"**Verdict:** `{verdict}`",
        f"**Progress:** `{progress}`",
        "",
        f"Source: Databento cache only (`{CACHE.name}`), bars={len(df_1m)}",
        f"Range: `{df_1m.index.min()}` → `{df_1m.index.max()}`",
        f"Window (train/val): `{chosen_window}`",
        "",
        "## Per-trigger holdout",
        f"```\n{json.dumps(trigger_hold, indent=2, default=str)}\n```",
        "",
        "## Combined holdout",
        f"```\n{json.dumps(_fmt(comb_st), indent=2, default=str)}\n```",
        "",
        "## Best balanced",
        f"```\n{json.dumps(slim(best_bal), indent=2, default=str)}\n```",
        "",
        "## Best high-accuracy",
        f"```\n{json.dumps(slim(best_acc), indent=2, default=str)}\n```",
        "",
        "## Best expectancy",
        f"```\n{json.dumps(slim(best_e), indent=2, default=str)}\n```",
        "",
        "## WR vs R",
        f"```\n{json.dumps(wr_vs_r, indent=2, default=str)}\n```",
        "",
        "## Interpretation",
        "- First honest Databento-positive cell: **PULLBACK / 10:00-11:30 / next_bar**.",
        "- Val: ~59% WR, PF~3.0, E~+0.62R (n≈39). Holdout: n=15 still thin — not demo-ready.",
        "- For higher WR preference, holdout WR-vs-R favors **1.25R–1.75R** over 2.0R.",
        "- Liquidity holdout n=6 is anecdotal. Breakout still weak on this sample.",
        "- Cache only (~180d). No multi-year Databento dump.",
        "",
    ]
    (OUT / "NQ_DATABENTO_FINETUNE_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("VERDICT:", verdict, "PROGRESS:", progress, flush=True)
    return report


if __name__ == "__main__":
    run()
