"""Seed explicit ordered CL lifecycle thresholds into runtime store."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.risk.strategy_lifecycle import StrategyLifecycleStore, thresholds_from_cfg

CFG = {
    "strategy_lifecycle": {
        "cl_vwap_prox_momentum": {
            "watch_dd_r": -5.0,
            "shadow_dd_r": -7.5,
            "hard_kill_r": -9.0,
        }
    }
}


def main() -> int:
    thr = thresholds_from_cfg(CFG, "cl_vwap_prox_momentum")
    assert thr["watch_dd_r"] > thr["shadow_dd_r"] > thr["hard_kill_r"], thr
    store = StrategyLifecycleStore(ROOT / "data" / "strategy_lifecycle.json")
    for sym in ("CL", "MCL", "CL_BOOK"):
        cell = store.seed_thresholds(
            "cl_vwap_prox_momentum",
            sym,
            [],  # ignored for CL — uses cfg explicit
            expected_wr=0.694,
            expected_e=1.08,
            cfg=CFG,
        )
        print(sym, cell.state, cell.watch_dd_r, cell.shadow_dd_r, cell.hard_kill_r)
    # NQ remains seeded for shadow tracking only
    for sym in ("NQ", "MNQ"):
        store.seed_thresholds(
            "nq_ny_open_momentum",
            sym,
            [2.0, -1.0] * 20,
            expected_wr=0.648,
            expected_e=0.94,
            cfg={"strategy_lifecycle": {}},
        )
    print("OK ordered:", thr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
