"""Execution observability, score calibration, engines, weekend resume, research."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from agent.config import load_settings
from agent.context.market_context import build_market_context
from agent.decision.execution_decisions import ExecutionDecisionLedger
from agent.decision.global_score import score_setup
from agent.decision.ranker import select_executable_detailed
from agent.decision.setup import TradeSetup
from agent.decision.tiering import assign_tier_from_global, can_execute
from agent.research.engine_audit import audit_engine_on_df, audit_from_last_evaluation
from agent.research.missed_moves import scan_missed_moves, summarize_missed
from agent.research.opportunity_stats import (
    OpportunityStatsStore,
    is_closed_session_reason,
)
from agent.schedule.sessions import session_ok
from agent.strategy.breakout_retest import evaluate_breakout_retest
from agent.strategy.opening_range import evaluate_opening_range
from agent.strategy.trend_continuation import evaluate_trend_continuation

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")


def _cfg():
    return load_settings(ROOT / "config" / "settings.yaml")


def _setup(**kwargs):
    base = dict(
        strategy_name="liquidity_sweep",
        symbol="MYM",
        direction="BUY",
        setup_tier="A+",
        confidence_score=82,
        entry=100.0,
        stop=99.0,
        target=102.0,
        expected_r=2.0,
        market_timestamp=datetime(2026, 8, 7, 16, 45),
        received_timestamp=datetime(2026, 8, 7, 20, 55, tzinfo=timezone.utc),
        reasons=["strategy:liquidity_sweep"],
        metadata={
            "strategy_local_score": 82,
            "global_score": 92,
            "setup_id": "MYM|liquidity_sweep|BUY|test",
            "has_location": True,
            "config_version": "opt_v1",
        },
    )
    base.update(kwargs)
    return TradeSetup(**base)


def test_minimum_trade_tier_still_a():
    assert _cfg()["tiering"]["minimum_trade_tier"] == "A"


def test_primary_setup_base_is_32():
    cfg = _cfg()
    assert float(cfg["global_scoring"]["primary_setup_base_points"]) == 32


def test_global_score_base_32_not_45():
    cfg = _cfg()
    df = pd.DataFrame(
        {
            "open": np.linspace(100, 110, 80),
            "high": np.linspace(100.5, 110.5, 80),
            "low": np.linspace(99.5, 109.5, 80),
            "close": np.linspace(100.2, 110.2, 80),
            "volume": np.ones(80) * 100,
        },
        index=pd.date_range("2026-08-01", periods=80, freq="5min", tz="UTC"),
    )
    ctx = build_market_context(df, cfg=cfg)
    s = _setup(strategy_name="ema_pullback", metadata={"strategy_local_score": 82})
    gs = score_setup(s, ctx, cfg)
    primary = next(c for c in gs.components if c.family == "PRIMARY")
    assert primary.points == 32
    # Lone primary + supportive context should not trivially mint 90+ B inflation
    assert gs.score < 100


def test_aa_cannot_silently_disappear(tmp_path):
    ledger = ExecutionDecisionLedger(tmp_path / "dec.jsonl")
    ledger.begin_cycle()
    a_plus = _setup()
    a = _setup(
        strategy_name="ema_pullback",
        setup_tier="A",
        metadata={
            "strategy_local_score": 82,
            "global_score": 81,
            "setup_id": "MYM|ema_pullback|BUY|test",
        },
    )
    # Only reject one — assert must catch the other
    ledger.reject(a, "AGREEMENT_SUPERSEDED_BY_liquidity_sweep")
    missing = ledger.unresolved([a_plus, a])
    assert len(missing) == 1
    assert missing[0].strategy_name == "liquidity_sweep"
    with pytest.raises(RuntimeError, match="UNRESOLVED_EXECUTABLE_CANDIDATE"):
        ledger.assert_all_resolved([a_plus, a])
    ledger.executed(a_plus, "PAPER-1")
    ledger.assert_all_resolved([a_plus, a])


def test_agreement_superseded_reported():
    cfg = _cfg()
    cfg["research_only_engines"] = [
        name for name in (cfg.get("research_only_engines") or []) if name != "liquidity_sweep"
    ]
    # Isolate agreement merge from live paper empirical router cells
    cfg = dict(cfg)
    cfg["performance_router"] = {"enabled": False}
    winner = _setup(
        setup_tier="A+",
        confidence_score=92,
        metadata={
            "strategy_local_score": 82,
            "global_score": 92,
            "setup_id": "w1",
            "has_location": True,
            "families_positive": ["MTF", "VWAP", "LOCATION", "RISK_REWARD"],
            "config_version": "opt_v1",
        },
    )
    loser = _setup(
        strategy_name="ema_pullback",
        setup_tier="A",
        confidence_score=81,
        metadata={
            "setup_id": "x2",
            "global_score": 81,
            "strategy_local_score": 82,
            "has_location": False,
            "families_positive": ["MTF", "VWAP", "EMA_TREND"],
            "agreeing_engines": ["ema_pullback", "liquidity_sweep"],
            "config_version": "opt_v1",
        },
    )
    executable, superseded = select_executable_detailed([winner, loser], cfg)
    assert len(executable) == 1
    assert executable[0].strategy_name == "liquidity_sweep"
    assert len(superseded) == 1
    assert superseded[0][0].strategy_name == "ema_pullback"


def test_weekend_gap_then_sunday_globex_auto_resume():
    cfg = _cfg()
    fri = datetime(2026, 8, 7, 17, 30, tzinfo=ET)
    ok, reason = session_ok(cfg, fri)
    assert not ok
    assert "weekend" in reason.lower()

    sun_before = datetime(2026, 8, 9, 17, 30, tzinfo=ET)
    ok2, reason2 = session_ok(cfg, sun_before)
    assert not ok2
    assert "weekend" in reason2.lower()

    sun_open = datetime(2026, 8, 9, 18, 5, tzinfo=ET)
    ok3, label = session_ok(cfg, sun_open)
    assert ok3
    assert label  # ACTIVE automatically — no manual restart


def test_opportunity_stats_exclude_weekend(tmp_path):
    store = OpportunityStatsStore(tmp_path / "opp.json")
    store.record_cycle(
        session_reason="weekend gap (Fri close → Sun open)",
        bars_processed=10,
        candidates=[{"tier": "A", "strategy": "x", "symbol": "MES"}],
        executions=0,
        active=False,
    )
    s = store.summary()
    assert s["market_bars_processed"] == 0
    assert s["closed_session_cycles_excluded"] == 1
    assert is_closed_session_reason("WEEKEND_GAP")

    store.record_cycle(
        session_reason="ny",
        bars_processed=100,
        candidates=[
            {"tier": "A+", "strategy": "liquidity_sweep", "symbol": "MYM", "regime": "TREND_UP"},
            {"tier": "B", "strategy": "ema_pullback", "symbol": "MNQ", "regime": "TREND_UP"},
        ],
        executions=1,
        active=True,
    )
    s2 = store.summary()
    assert s2["market_bars_processed"] == 100
    assert s2["A+"] == 1
    assert s2["executions_per_100_bars"] == 1.0


def test_new_engines_import_and_safe_none():
    cfg = _cfg()
    df = pd.DataFrame(
        {
            "open": np.linspace(100, 101, 60),
            "high": np.linspace(100.2, 101.2, 60),
            "low": np.linspace(99.8, 100.8, 60),
            "close": np.linspace(100.1, 101.1, 60),
            "volume": np.ones(60) * 50,
        },
        index=pd.date_range("2026-08-06 09:00", periods=60, freq="5min", tz=ET),
    )
    # May or may not fire — must not raise
    evaluate_breakout_retest("MES", df, cfg, point_value=5.0)
    evaluate_trend_continuation("MES", df, cfg, point_value=5.0)
    evaluate_opening_range("MES", df, cfg, point_value=5.0)


def test_engine_audit_walk():
    cfg = _cfg()
    df = pd.DataFrame(
        {
            "open": np.linspace(100, 105, 80),
            "high": np.linspace(100.5, 105.5, 80),
            "low": np.linspace(99.5, 104.5, 80),
            "close": np.linspace(100.2, 105.2, 80),
            "volume": np.ones(80) * 100,
        },
        index=pd.date_range("2026-08-01", periods=80, freq="5min"),
    )
    from agent.strategy.momentum import evaluate_momentum

    row = audit_engine_on_df(
        "momentum", evaluate_momentum, df, cfg, step=5, min_bars=40
    )
    assert row["bars_evaluated"] > 0
    assert "top_rejection_reasons" in row


def test_missed_move_research_only():
    idx = pd.date_range("2026-08-01", periods=40, freq="5min")
    close = np.concatenate([np.linspace(100, 100.2, 25), np.linspace(100.2, 104, 15)])
    df = pd.DataFrame(
        {
            "open": close - 0.05,
            "high": close + 0.3,
            "low": close - 0.1,
            "close": close,
            "volume": np.ones(40) * 10,
        },
        index=idx,
    )
    moves = scan_missed_moves(df, symbol="NQ", atr_threshold=1.0, adverse_atr=2.0)
    summary = summarize_missed(moves)
    assert "large_directional_moves" in summary
    assert summary["note"].startswith("research-only")


def test_runtime_book_is_only_validated_paper_specialists():
    """Live evaluation stays lean; unvalidated engines remain available offline."""
    cfg = _cfg()
    engines = set(cfg["confluence"]["engines"])
    research = set(cfg.get("research_only_engines") or [])
    specialists = set(cfg.get("paper_specialist_engines") or [])
    assert engines == specialists
    assert engines == set()
    assert {"nq_context_entry", "cl_vwap_prox_momentum"}.issubset(research)
    assert "cl_vwap_prox_momentum" in research
    assert "vwap_rejection" in research
    assert {"vwap_acceptance", "vwap_reclaim", "trend_pullback", "liquidity_reversal", "ema_pullback"} <= research
    assert not (engines & research)
    assert (cfg.get("shadow") or {}).get("evaluate_research_engines_live") is False
    assert (cfg.get("performance_router") or {}).get("enabled", True)
    assert (cfg.get("performance_router_v2") or {}).get("enabled") is False


def test_blotter_risk_context_tz_safe():
    from agent.live_main import _blotter_risk_context
    from agent.paper.blotter import PaperBlotter

    b = PaperBlotter(
        json_path=str(ROOT / "data" / "_tmp_tz_test_paper.json"),
        html_path=str(ROOT / "data" / "_tmp_tz_test.html"),
        csv_path=str(ROOT / "data" / "_tmp_tz_test.csv"),
        starting_equity=50000,
    )
    b._state["trades"] = [
        {
            "symbol": "MYM",
            "side": "BUY",
            "opened_at": "2026-08-07T16:00:00",  # naive
            "entry": 1,
            "stop": 0.5,
            "target": 2,
            "qty": 1,
        }
    ]
    open_sides, last_fill = _blotter_risk_context(b)
    assert "MYM" in last_fill
    assert last_fill["MYM"].tzinfo is not None
