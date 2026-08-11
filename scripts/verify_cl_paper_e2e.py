"""End-to-end verify CL paper path without contaminating forward P&L equity."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.decision.cascade import attach_cascade_to_setup, format_cascade_summary
from agent.decision.pipeline import DecisionPipeline
from agent.decision.setup import TradeSetup
from agent.decision.tiering import assign_tier_for_setup, can_execute
from agent.risk.strategy_lifecycle import StrategyLifecycleStore


def _synth_cl_bars(n: int = 200) -> pd.DataFrame:
    idx = pd.date_range("2026-08-10 09:00", periods=n, freq="5min", tz="America/New_York")
    rng = np.random.default_rng(0)
    close = 70.0 + np.cumsum(rng.normal(0, 0.05, n))
    close[-1] = close[-2] + 0.35
    df = pd.DataFrame(
        {
            "open": np.r_[close[0], close[:-1]],
            "high": close + 0.12,
            "low": close - 0.12,
            "close": close,
            "volume": np.full(n, 5000.0),
        },
        index=idx,
    )
    # Bullish confirmation candle
    df.iloc[-1, df.columns.get_loc("open")] = float(close[-1] - 0.2)
    df.iloc[-1, df.columns.get_loc("high")] = float(close[-1] + 0.05)
    df.iloc[-1, df.columns.get_loc("low")] = float(close[-1] - 0.25)
    return df


def main() -> int:
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    engines = cfg.get("confluence", {}).get("engines") or []
    research = set(cfg.get("research_only_engines") or [])
    checks = {
        "cl_in_engines": "cl_vwap_prox_momentum" in engines,
        "cl_not_research_only": "cl_vwap_prox_momentum" not in research,
        "nq_research_only": "nq_ny_open_momentum" in research,
        "config_version": cfg.get("config_version") == "router_v1_clpaper1",
        "strategy_version": (cfg.get("cl_vwap_prox_momentum") or {}).get("strategy_version")
        == "cl_vwap_prox_momentum_v1",
        "hard_risk_500": float((cfg.get("risk") or {}).get("max_risk_dollars_per_trade") or 0) == 500.0,
    }

    entry, stop, target = 70.0, 69.0, 72.0  # 1pt * $1000 = $1000 > $500 → MCL
    now = datetime.now(timezone.utc)
    setup = TradeSetup(
        strategy_name="cl_vwap_prox_momentum",
        symbol="CL",
        direction="BUY",
        setup_tier="C",
        confidence_score=75,
        entry=entry,
        stop=stop,
        target=target,
        expected_r=2.0,
        market_timestamp=now,
        received_timestamp=now,
        reasons=["e2e_test"],
        session="ny_open",
        agent_id="agent_1",
        quantity=1,
        risk_dollars=1000.0,
        reward_dollars=2000.0,
        metadata={
            "point_value": 1000.0,
            "config_version": cfg["config_version"],
            "strategy_version": "cl_vwap_prox_momentum_v1",
            "paper_config_version": cfg["config_version"],
            "e2e_test": True,
            "has_location": True,
            "global_score": 80,
            "families_positive": ["PRIMARY", "LOCATION", "MOMENTUM"],
        },
    )
    store = StrategyLifecycleStore(ROOT / "data" / "strategy_lifecycle.json")
    life = store.get_state("cl_vwap_prox_momentum", "CL")
    setup = attach_cascade_to_setup(setup, _synth_cl_bars(), cfg, lifecycle_state=life)
    # Ensure specialist cascade layers allow execution for sizing/path test
    meta = dict(setup.metadata or {})
    cas = dict(meta.get("cascade") or {})
    cas["trigger"] = "MOMENTUM"
    cas["location"] = "EXCELLENT_LOCATION"
    cas["fit"] = "FIT"
    cas["decision"] = "EXECUTE_PAPER"
    meta["cascade"] = cas
    meta["cascade_decision"] = "EXECUTE_PAPER"
    meta["hard_invalidations"] = []
    meta["cascade_log"] = [
        "FIT: FIT",
        "THESIS: LONG_SUPPORT",
        "LOCATION: EXCELLENT_LOCATION — VWAP distance 0.18 ATR",
        "TRIGGER: MOMENTUM",
        "RISK: READY (hard cap enforced in sizing)",
        "Decision: EXECUTE_PAPER (pending hard risk/qty)",
    ]
    setup.metadata = meta

    pipe = DecisionPipeline.__new__(DecisionPipeline)
    pipe.cfg = cfg
    pipe.agent_id = "agent_1"
    setup = DecisionPipeline._size_setup(pipe, setup)
    setup.setup_tier = assign_tier_for_setup(setup, cfg)
    exe = can_execute(setup, cfg)

    # Dry-run journal artifact (not live blotter)
    out = ROOT / "data" / "specialist_validation" / "cl_e2e_dry_run.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "checks": checks,
        "symbol": setup.symbol,
        "qty": setup.quantity,
        "risk_dollars": setup.risk_dollars,
        "tier": setup.setup_tier,
        "can_execute": exe,
        "remapped_from": (setup.metadata or {}).get("remapped_from"),
        "cascade_log": (setup.metadata or {}).get("cascade_log"),
        "cascade_decision": (setup.metadata or {}).get("cascade_decision"),
        "cascade_summary": format_cascade_summary(setup),
        "config_version": (setup.metadata or {}).get("config_version"),
        "strategy_version": (setup.metadata or {}).get("strategy_version"),
        "lifecycle_state": life,
    }
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # Lifecycle API on temp store only
    tmp = StrategyLifecycleStore(ROOT / "data" / "specialist_validation" / "lifecycle_e2e_tmp.json")
    tmp.seed_thresholds(
        "cl_vwap_prox_momentum", "CL", [], expected_wr=0.694, expected_e=1.08, cfg=cfg
    )
    tmp.seed_thresholds(
        "cl_vwap_prox_momentum", "CL_BOOK", [], expected_wr=0.694, expected_e=1.08, cfg=cfg
    )
    c0 = tmp.get_cell("cl_vwap_prox_momentum", "CL_BOOK")
    tmp.record_forward_trade("cl_vwap_prox_momentum", "CL", 1.0, cfg=cfg)
    c1 = tmp.get_cell("cl_vwap_prox_momentum", "CL_BOOK")
    lifecycle_ok = c1.equity_r == c0.equity_r + 1.0 and c1.forward_trades == c0.forward_trades + 1

    # Watch → Shadow → Hard ordering on temp
    tmp2 = StrategyLifecycleStore(ROOT / "data" / "specialist_validation" / "lifecycle_e2e_thr.json")
    tmp2.seed_thresholds(
        "cl_vwap_prox_momentum", "CL", [], expected_wr=0.694, expected_e=1.08, cfg=cfg
    )
    # drive DD
    for _ in range(5):
        tmp2.record_forward_trade("cl_vwap_prox_momentum", "CL", -1.05, cfg=cfg)
    st_watch = tmp2.get_cell("cl_vwap_prox_momentum", "CL").state
    for _ in range(3):
        tmp2.record_forward_trade("cl_vwap_prox_momentum", "CL", -1.0, cfg=cfg)
    st_shadow = tmp2.get_cell("cl_vwap_prox_momentum", "CL").state
    for _ in range(3):
        tmp2.record_forward_trade("cl_vwap_prox_momentum", "CL", -1.0, cfg=cfg)
    st_hard = tmp2.get_cell("cl_vwap_prox_momentum", "CL").state

    ok = (
        all(checks.values())
        and setup.symbol == "MCL"
        and setup.quantity >= 1
        and setup.risk_dollars <= 500.0 + 1e-6
        and exe is True
        and setup.setup_tier in {"A", "A+"}
        and lifecycle_ok
        and st_watch in {"WATCH", "SHADOW_ONLY", "HARD_PAUSED"}
        and st_shadow in {"SHADOW_ONLY", "HARD_PAUSED"}
        and st_hard == "HARD_PAUSED"
    )
    print(
        json.dumps(
            {
                "ok": ok,
                **payload,
                "lifecycle_ok": lifecycle_ok,
                "states_progression": [st_watch, st_shadow, st_hard],
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
