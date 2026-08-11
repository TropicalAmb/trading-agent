"""CL priority learning + HC shadow parallel (no paper promotion)."""

from __future__ import annotations

from datetime import datetime

from agent.decision.hc_shadow import (
    attach_high_confidence_shadow_decisions,
    attach_model_evidence_shadow,
)
from agent.decision.setup import TradeSetup
from agent.learning.cl_priority import (
    compare_win_loss_traits,
    entry_snapshot_from_trade,
    find_subcells,
)
from agent.learning.shrink import shrink_rate


def test_shrink_still_conservative():
    shr = shrink_rate(8, 10, prior_mean=0.50, prior_strength=20.0)
    assert shr.raw == 0.8
    assert shr.shrunk < 0.65


def test_entry_snapshot_no_lookahead_fields():
    t = {
        "symbol": "CL",
        "strategy_name": "cl_vwap_prox_momentum",
        "side": "BUY",
        "session": "asia",
        "entry": 82.0,
        "stop": 81.8,
        "target": 82.4,
        "opened_at": "2026-08-11 01:45:00",
        "pnl_dollars": 270,
        "result": "WIN",
        "reason": "agreement:cl_vwap_prox_momentum,ema_pullback,vwap_reclaim",
        "metadata": {
            "entry_features": {"mtf_aligned": 2, "above_vwap": 1, "dir_15m": -1},
            "regime": "TREND_UP",
        },
    }
    snap = entry_snapshot_from_trade(t)
    assert snap["symbol"] == "CL"
    assert snap["mtf_aligned"] == 2
    assert "post_entry" not in snap
    assert snap["agreeing_engines"]


def test_compare_win_loss_reports_actual_rates():
    wins = [
        {
            "symbol": "CL",
            "strategy": "liquidity_reversal",
            "side": "SELL",
            "session": "london",
            "closed_at": "t",
            "pnl": 1,
            "metadata": {"entry_features": {"mtf_aligned": 3, "above_vwap": 0, "below_vwap": 1}},
        }
        for _ in range(10)
    ]
    losses = [
        {
            "symbol": "CL",
            "strategy": "liquidity_reversal",
            "side": "BUY",
            "session": "asia",
            "closed_at": "t",
            "pnl": -1,
            "metadata": {"entry_features": {"mtf_aligned": 1, "above_vwap": 1, "below_vwap": 0}},
        }
        for _ in range(10)
    ]
    cmp_ = compare_win_loss_traits(wins, losses)
    assert cmp_["n_wins"] == 10
    assert cmp_["n_losses"] == 10
    assert cmp_["winners"]["pct_london"] == 1.0
    assert cmp_["losers"]["pct_london"] == 0.0


def test_subcell_categories():
    rows = []
    for i in range(45):
        rows.append(
            {
                "symbol": "CL",
                "strategy": "liquidity_reversal",
                "side": "SELL",
                "session": "london",
                "closed_at": "t",
                "r_achieved": 1.0 if i % 2 == 0 else -1.0,
                "metadata": {"entry_features": {"session": "london"}, "regime": "TREND_DOWN"},
            }
        )
    cells = find_subcells(rows, min_n=20)
    assert any(c.get("category") == "DEVELOPING" for c in cells)


def test_hc_shadow_does_not_require_v2_enabled():
    cfg = {
        "performance_router": {"enabled": True, "trade_paths": [], "include_shadow": False},
        "performance_router_v2": {"enabled": False},
        "trade_quality_model": {"enabled": True, "models_dir": "data/learning/models"},
        "high_confidence": {
            "enabled": True,
            "shadow_parallel": True,
            "attach_shadow_evidence": True,
            "min_predicted_probability": 0.65,
            "min_sample": 1,
            "min_expectancy_r": -9,
            "min_profit_factor": 0,
        },
    }
    s = TradeSetup(
        strategy_name="liquidity_reversal",
        symbol="CL",
        direction="SELL",
        setup_tier="A",
        confidence_score=80,
        entry=80,
        stop=80.5,
        target=79,
        expected_r=2,
        market_timestamp=datetime(2026, 8, 11),
        received_timestamp=datetime(2026, 8, 11),
        session="london",
        metadata={
            "setup_id": "CL|liquidity_reversal|SELL|test",
            "global_score": 80,
            "regime": "TREND_DOWN",
            "entry_features": {
                "strategy": "liquidity_reversal",
                "symbol": "CL",
                "direction": "SHORT",
                "session": "london",
                "mtf_aligned": 3,
                "global_score": 80,
            },
            "router_evidence": {
                "sample_count": 50,
                "win_rate": 0.7,
                "shrunk_win_rate": 0.66,
                "raw_win_rate": 0.7,
                "expectancy_r": 0.3,
                "profit_factor": 1.8,
                "model_probability": 0.7,
                "model_calibrated": True,
            },
        },
    )
    attach_model_evidence_shadow([s], cfg)
    attach_high_confidence_shadow_decisions(
        [s], cfg, router_v1_selected_ids={s.metadata["setup_id"]}
    )
    assert "high_confidence_shadow" in (s.metadata or {})
    assert (s.metadata or {})["high_confidence_shadow"]["decision"] in {"SELECT", "PASS"}
