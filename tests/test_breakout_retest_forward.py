"""Observation-only breakout_retest research helpers."""

from __future__ import annotations

from agent.research.breakout_retest_forward import (
    BrRow,
    cell_label,
    cohort_stats,
    feature_compare,
)


def test_cell_label_thresholds():
    assert cell_label(5) == "ANECDOTAL"
    assert cell_label(25) == "EARLY"
    assert cell_label(50) == "DEVELOPING"
    assert cell_label(120) == "VALIDATED"


def test_cohort_stats_and_feature_compare():
    winners = [
        BrRow(
            source="paper",
            trade_id="W1",
            setup_id="s1",
            symbol="ES",
            contract_class="full",
            direction="BUY",
            session="ny",
            regime="TREND_UP",
            market_timestamp="t",
            config_version="router_v1_paperfix2",
            era="post_paperfix2",
            tier="A+",
            qty=2,
            entry=1,
            stop=0,
            target=2,
            pnl_dollars=100,
            realized_r=1.0,
            win=True,
            exit_reason="target",
            features={"mtf_aligned": 3, "overextended": 0, "cascade_thesis": "MIXED"},
        )
    ]
    losers = [
        BrRow(
            source="paper",
            trade_id="L1",
            setup_id="s2",
            symbol="MNQ",
            contract_class="micro",
            direction="SELL",
            session="ny",
            regime="TREND_UP",
            market_timestamp="t",
            config_version="router_v1_paperfix2",
            era="post_paperfix2",
            tier="A+",
            qty=3,
            entry=1,
            stop=0,
            target=2,
            pnl_dollars=-50,
            realized_r=-1.0,
            win=False,
            exit_reason="stop",
            features={"mtf_aligned": 1, "overextended": 1, "cascade_thesis": "MIXED"},
        )
    ]
    st = cohort_stats(winners + losers)
    assert st["n"] == 2
    assert st["wins"] == 1
    assert st["wr"] == 0.5
    feats = feature_compare(winners, losers)
    assert any(f["feature"] == "mtf_aligned" for f in feats)
