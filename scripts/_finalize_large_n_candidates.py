"""FINAL holdout metrics for large-n VAL leaders (selection min_n correction)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.research.harness.datasets import assign_period, fetch_yahoo, load_split_lock
from agent.research.harness.metrics import meets_gates, trade_stats
from agent.research.harness.monte_carlo import monte_carlo
from agent.research.vwap_mss_deep import attach_fixed_r_pnls, event_to_trade_fast, filter_events, scan_events

OUT = ROOT / "data" / "vwap_mss_deep"
SYMBOLS = {"NQ": "NQ=F", "MNQ": "MNQ=F", "ES": "ES=F", "MES": "MES=F", "GC": "GC=F", "MGC": "MGC=F", "CL": "CL=F", "MCL": "MCL=F"}

CANDIDATES = [
    {"id": "v9_mtf3_mE_reclaim_R1.0", "mss_mode": "E", "vwap_mode": "reclaim", "target_r": 1.0, "min_mtf": 3},
    {"id": "v9_mtf3_mE_reclaim_R1.5", "mss_mode": "E", "vwap_mode": "reclaim", "target_r": 1.5, "min_mtf": 3},
    {"id": "v9_mtf3_mC_retest_R1.0", "mss_mode": "C", "vwap_mode": "retest", "target_r": 1.0, "min_mtf": 3},
    {"id": "v9_mtf3_mC_reclaim_R1.25", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.25, "min_mtf": 3},
    {"id": "v20_quality_mC_reclaim_R1.25", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.25, "need_disp": True, "max_overext": 0.75, "min_mtf": 2},
    {"id": "v2_pdh_mC_reclaim_R1.5", "mss_mode": "C", "vwap_mode": "reclaim", "target_r": 1.5, "need_pdh_pdl": True},
]


def main() -> int:
    lock = load_split_lock(OUT / "split_lock.json")
    from agent.research.harness.datasets import SplitSpec

    splits = {k: SplitSpec(**v) for k, v in (lock or {}).get("splits_1h", {}).items()}
    frames = {}
    events = {}
    for name, ysym in SYMBOLS.items():
        print("load", name, flush=True)
        df = fetch_yahoo(ysym, "1h", "730d")
        if df.empty:
            df = fetch_yahoo(ysym, "1h", "365d")
        frames[name] = df
        if name not in splits:
            continue
        ev = scan_events(df, name)
        attach_fixed_r_pnls(df, ev)
        events[name] = ev
        print(" ", len(ev), "events", flush=True)

    out = {}
    for spec in CANDIDATES:
        by = {"train": [], "val": [], "final": []}
        by_sym = defaultdict(list)
        filt = {k: v for k, v in spec.items() if k not in ("id", "mss_mode", "vwap_mode", "target_r")}
        for sym, evs in events.items():
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
            seen = set()
            uniq = []
            for t in by[p]:
                key = (t.entry_ts, t.side, t.symbol)
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(t)
            by[p] = uniq
        st_f = trade_stats([t.pnl_r for t in by["final"]], [t.entry_ts for t in by["final"]])
        st_v = trade_stats([t.pnl_r for t in by["val"]], [t.entry_ts for t in by["val"]])
        mc = monte_carlo([t.pnl_r for t in by["final"]], n_sims=10000) if st_f["n"] >= 20 else {}
        sessions = defaultdict(list)
        for t in by["final"]:
            sessions[t.session].append(t)
        out[spec["id"]] = {
            "val": st_v,
            "final": st_f,
            "gates_met": meets_gates(st_f),
            "monte_carlo": mc,
            "by_symbol_final": {
                s: trade_stats([t.pnl_r for t in ts], [t.entry_ts for t in ts]) for s, ts in by_sym.items()
            },
            "by_session_final": {
                s: trade_stats([t.pnl_r for t in ts], [t.entry_ts for t in ts]) for s, ts in sessions.items()
            },
        }
        print(
            spec["id"],
            "VAL",
            st_v["n"],
            st_v["wr"],
            "FINAL",
            st_f["n"],
            st_f["wr"],
            st_f["pf"],
            st_f["expectancy_r"],
            "gates",
            meets_gates(st_f),
            flush=True,
        )

    path = OUT / "large_n_finalists.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
