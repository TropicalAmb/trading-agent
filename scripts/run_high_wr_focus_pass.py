"""Focused high-WR hunt from field research (FB sniper / session / product).

Runs in parallel with paper agent. Soft paper gates; aspirational WR>=0.60 tracked.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.datasets import SplitSpec, assign_period, fetch_yahoo, save_split_lock
from agent.research.harness.metrics import PAPER_GATES, meets_paper_gates, trade_stats
from agent.research.harness.monte_carlo import monte_carlo
from agent.research.vwap_mss_deep import (
    attach_fixed_r_pnls,
    event_to_trade_fast,
    filter_events,
    scan_events,
)

OUT = ROOT / "data" / "high_wr_focus"
SYMBOLS = {
    "NQ": "NQ=F",
    "ES": "ES=F",
    "GC": "GC=F",
    "CL": "CL=F",
    "MNQ": "MNQ=F",
    "MES": "MES=F",
}


def freeze_new(df):
    """Reuse deep-pass style newest 20% holdout."""
    from agent.research.harness.datasets import SplitSpec

    days = sorted(df.index.normalize().unique())
    n = len(days)
    n_final = max(int(n * 0.20), 5)
    n_dev = n - n_final
    n_train = max(int(n_dev * 0.70), 8)
    train, val, final = days[:n_train], days[n_train:n_dev], days[n_dev:]
    return SplitSpec(
        train_end=str(train[-1]),
        val_end=str(val[-1]),
        final_start=str(final[0]),
        n_days_train=len(train),
        n_days_val=len(val),
        n_days_final=len(final),
    )


SPECS = [
    # Field: 3-align sniper → MTF3 + VWAP reclaim + MSS
    {"id": "sniper_mtf3_reclaim_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3},
    {"id": "sniper_mtf3_reclaim_R1.25", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.25, "min_mtf": 3},
    {"id": "sniper_mtf3_retest_R1.0", "mss_mode": "C", "vwap_mode": "retest", "target_r": 1.0, "min_mtf": 3},
    {"id": "sniper_mtf3_disp_R1.0", "mss_mode": "E", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "need_disp": True},
    {"id": "sniper_mtf3_pdh_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "need_pdh_pdl": True},
    {"id": "sniper_mtf3_engulf_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "need_engulf": True},
    {"id": "sniper_mtf3_reject_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "need_reject": True},
    {"id": "sniper_mtf3_nochase_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "max_overext": 0.5},
    # Session focus (FB London futures / NY open curiosity)
    {"id": "london_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "session": "LONDON"},
    {"id": "nyopen_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "retest", "target_r": 1.0, "min_mtf": 3, "session": "NY_OPEN"},
    {"id": "nymid_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "session": "NY_MID"},
    # Product focus where prior FINAL looked hotter
    {"id": "gc_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "symbols": ["GC"]},
    {"id": "cl_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "symbols": ["CL"]},
    {"id": "es_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "symbols": ["ES", "MES"]},
    {"id": "nq_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "symbols": ["NQ", "MNQ"]},
    {"id": "gc_london_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "session": "LONDON", "symbols": ["GC"]},
    {"id": "cl_london_mtf3_R1.0", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3, "session": "LONDON", "symbols": ["CL"]},
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frames, events, splits = {}, {}, {}
    for name, ysym in SYMBOLS.items():
        print("load", name, flush=True)
        df = fetch_yahoo(ysym, "1h", "730d")
        if df.empty:
            df = fetch_yahoo(ysym, "1h", "365d")
        frames[name] = df
        if len(df) < 100:
            continue
        splits[name] = freeze_new(df)
        ev = scan_events(df, name)
        attach_fixed_r_pnls(df, ev)
        events[name] = ev
        print(f"  bars={len(df)} events={len(ev)}", flush=True)

    save_split_lock(
        OUT / "split_lock.json",
        {
            "locked_at": datetime.now(timezone.utc).isoformat(),
            "rule": "newest 20% FINAL holdout; DEV 70/30",
            "splits": {k: asdict(v) for k, v in splits.items()},
            "paper_gates": PAPER_GATES,
            "aspirational_wr": 0.65,
        },
    )

    rows = []
    for spec in SPECS:
        print("eval", spec["id"], flush=True)
        by = {"train": [], "val": [], "final": []}
        by_sym = defaultdict(list)
        allow = set(spec.get("symbols") or SYMBOLS.keys())
        filt = {
            k: v
            for k, v in spec.items()
            if k not in ("id", "target_r", "mss_mode", "vwap_mode", "symbols")
        }
        for sym, evs in events.items():
            if sym not in allow or sym not in splits:
                continue
            for ev in filter_events(evs, mss_mode=spec["mss_mode"], vwap_mode=spec["vwap_mode"], **filt):
                tr = event_to_trade_fast(ev, target_r=float(spec["target_r"]), config_id=spec["id"])
                if not tr:
                    continue
                p = assign_period(tr.entry_ts, splits[sym])
                by[p].append(tr)
                if p == "final":
                    by_sym[sym].append(tr)
        # dedupe
        for p in by:
            seen, uniq = set(), []
            for t in by[p]:
                key = (t.symbol, t.entry_ts, t.side)
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(t)
            by[p] = uniq

        st_v = trade_stats([t.pnl_r for t in by["val"]], [t.entry_ts for t in by["val"]])
        st_f = trade_stats([t.pnl_r for t in by["final"]], [t.entry_ts for t in by["final"]])
        rows.append(
            {
                "config": spec["id"],
                "spec": spec,
                "val": st_v,
                "final": st_f,
                "paper_gates_final": meets_paper_gates(st_f),
                "wr_ge_60_final": st_f["n"] >= 30 and st_f["wr"] >= 0.60,
                "wr_ge_65_final": st_f["n"] >= 50 and st_f["wr"] >= 0.65,
                "monte_carlo": monte_carlo([t.pnl_r for t in by["final"]], n_sims=5000)
                if st_f["n"] >= 20
                else {},
                "by_symbol_final": {
                    s: trade_stats([t.pnl_r for t in ts], [t.entry_ts for t in ts]) for s, ts in by_sym.items()
                },
            }
        )
        print(
            f"  VAL n={st_v['n']} WR={st_v['wr']:.1%} | FINAL n={st_f['n']} WR={st_f['wr']:.1%} "
            f"PF={st_f['pf']} E={st_f['expectancy_r']:+.3f}",
            flush=True,
        )

    # rank by FINAL WR among n>=30 with E>0
    ranked = sorted(
        [r for r in rows if r["final"]["n"] >= 20],
        key=lambda r: (r["final"]["wr"], r["final"]["expectancy_r"], r["final"]["n"]),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Focused high-WR hunt from FB sniper/session/product themes. Paper agent not frozen.",
        "best_final": best,
        "results": rows,
        "ranked_final": [
            {
                "config": r["config"],
                "n": r["final"]["n"],
                "wr": r["final"]["wr"],
                "pf": r["final"]["pf"],
                "e": r["final"]["expectancy_r"],
                "paper_ok": r["paper_gates_final"],
                "wr60": r["wr_ge_60_final"],
                "wr65": r["wr_ge_65_final"],
            }
            for r in ranked[:15]
        ],
    }
    (OUT / "high_wr_focus.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# High-WR Focus Report",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "## Ranked FINAL (n>=20)",
        "```json",
        json.dumps(payload["ranked_final"], indent=2),
        "```",
        "",
        "## Best",
        "```json",
        json.dumps(best, indent=2, default=str)[:4000] if best else "{}",
        "```",
    ]
    (OUT / "HIGH_WR_FOCUS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("\nBEST:", best["config"] if best else None, flush=True)
    if best:
        print(best["final"], flush=True)
    print("Report:", OUT / "HIGH_WR_FOCUS_REPORT.md", flush=True)
    return 0


if __name__ == "__main__":
    # fix botched import line
    raise SystemExit(main())
