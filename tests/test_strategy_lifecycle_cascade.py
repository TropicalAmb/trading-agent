from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from agent.decision.cascade import evaluate_cascade
from agent.decision.setup import TradeSetup
from agent.decision.tiering import can_execute
from agent.risk.strategy_lifecycle import (
    StrategyLifecycleStore,
    blocks_execution,
    compute_kill_thresholds,
    equity_curve_r,
    thresholds_from_cfg,
)


def test_kill_thresholds_ordered():
    rs = [1.0, -1.0, 2.0, -1.0, 2.0, -1.0, 2.0, -1.0, 2.0, 2.0] * 5
    thr = compute_kill_thresholds(rs)
    assert thr["watch_dd_r"] > thr["shadow_dd_r"] > thr["hard_kill_r"]


def test_cl_cfg_thresholds_ordered():
    thr = thresholds_from_cfg(
        {
            "strategy_lifecycle": {
                "cl_vwap_prox_momentum": {
                    "watch_dd_r": -5.0,
                    "shadow_dd_r": -7.5,
                    "hard_kill_r": -9.0,
                }
            }
        },
        "cl_vwap_prox_momentum",
    )
    assert thr == {"watch_dd_r": -5.0, "shadow_dd_r": -7.5, "hard_kill_r": -9.0}
    assert thr["watch_dd_r"] > thr["shadow_dd_r"] > thr["hard_kill_r"]


def test_lifecycle_watch_shadow_hard(tmp_path):
    cfg = {
        "strategy_lifecycle": {
            "cl_vwap_prox_momentum": {
                "watch_dd_r": -2.0,
                "shadow_dd_r": -4.0,
                "hard_kill_r": -6.0,
            }
        }
    }
    store = StrategyLifecycleStore(tmp_path / "lc.json")
    store.seed_thresholds("cl_vwap_prox_momentum", "CL", [], expected_wr=0.69, expected_e=1.0, cfg=cfg)
    store.record_forward_trade("cl_vwap_prox_momentum", "CL", -2.1, cfg=cfg)
    assert store.get_cell("cl_vwap_prox_momentum", "CL").state == "WATCH"
    store.record_forward_trade("cl_vwap_prox_momentum", "CL", -2.0, cfg=cfg)
    assert store.get_cell("cl_vwap_prox_momentum", "CL").state == "SHADOW_ONLY"
    store.record_forward_trade("cl_vwap_prox_momentum", "CL", -2.0, cfg=cfg)
    assert store.get_cell("cl_vwap_prox_momentum", "CL").state == "HARD_PAUSED"
    assert blocks_execution("HARD_PAUSED")


def test_drift_watch_requires_two_weeks(tmp_path):
    store = StrategyLifecycleStore(tmp_path / "lc2.json")
    store.seed_thresholds("demo", "NQ", [2.0, 2.0, -1.0] * 15, expected_wr=0.70, expected_e=1.0)
    bad = [-1.0] * 10
    store.weekly_drift_review("demo", "NQ", bad)
    assert store.get_state("demo", "NQ") == "ACTIVE"
    store.weekly_drift_review("demo", "NQ", bad)
    assert store.get_state("demo", "NQ") == "WATCH"


def test_cascade_layers():
    idx = pd.date_range("2026-08-01", periods=120, freq="5min", tz="America/New_York")
    close = pd.Series(range(120), index=idx, dtype=float) + 70.0
    df = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": 1000.0,
        },
        index=idx,
    )
    now = datetime.now(timezone.utc)
    setup = TradeSetup(
        strategy_name="cl_vwap_prox_momentum",
        symbol="CL",
        direction="BUY",
        setup_tier="A",
        confidence_score=70,
        entry=float(close.iloc[-1]),
        stop=float(close.iloc[-1]) - 1.0,
        target=float(close.iloc[-1]) + 2.0,
        expected_r=2.0,
        market_timestamp=now,
        received_timestamp=now,
        reasons=["test"],
        session="ny_open",
        agent_id="t",
        quantity=1,
        risk_dollars=100.0,
        reward_dollars=200.0,
    )
    cas = evaluate_cascade(
        setup,
        df,
        {"trade_cascade": {"enabled": True}, "cl_vwap_prox_momentum": {"max_abs_vwap_atr": 0.25}},
    )
    assert cas.layer_log
    assert cas.decision in {"EXECUTE_PAPER", "SHADOW", "REJECT"}


def test_can_execute_blocks_hard_paused():
    now = datetime.now(timezone.utc)
    setup = TradeSetup(
        strategy_name="x",
        symbol="CL",
        direction="BUY",
        setup_tier="A",
        confidence_score=80,
        entry=1.0,
        stop=0.9,
        target=1.2,
        expected_r=2.0,
        market_timestamp=now,
        received_timestamp=now,
        reasons=[],
        session="ny",
        agent_id="t",
        quantity=1,
        risk_dollars=10.0,
        reward_dollars=20.0,
        metadata={"lifecycle_state": "HARD_PAUSED"},
    )
    assert can_execute(setup, {"tiering": {"minimum_trade_tier": "A"}}) is False


def test_equity_curve():
    eq = equity_curve_r([1, 1, -1, -1, -1, 2])
    assert eq["max_dd"] < 0
