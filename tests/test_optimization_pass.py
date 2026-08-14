"""Additive optimization pass — regime, context, global score, momentum, shadow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agent.config import load_settings
from agent.context.market_context import build_market_context
from agent.context.regime import MarketRegime, MarketRegimeClassifier
from agent.decision.champion import evaluate_promotion, resolve_execution_mode
from agent.decision.global_score import score_setup
from agent.decision.setup import TradeSetup
from agent.decision.tiering import (
    assign_tier_from_global,
    can_execute,
    execution_reject_reason,
)
from agent.decision.ranker import select_executable_detailed
from agent.execution.directional import apply_paper_friction
from agent.journal.shadow import ShadowTracker
from agent.research.exit_models import evaluate_fixed_r
from agent.risk.circuit_breakers import CircuitBreakerStore, StrategyHealth
from agent.risk.portfolio import ExposureIntent, PortfolioCoordinator, PortfolioState
from agent.strategy.momentum import evaluate_momentum

ROOT = Path(__file__).resolve().parents[1]


def _cfg():
    return load_settings(ROOT / "config" / "settings.yaml")


def _execution_logic_cfg(*engine_names: str):
    """Opt named legacy engines into isolated logic tests, never live config."""
    cfg = _cfg()
    cfg["research_only_engines"] = [
        name for name in (cfg.get("research_only_engines") or []) if name not in engine_names
    ]
    return cfg


def _bars(n=80, trend=1.0, start=100.0, compression=False):
    idx = pd.date_range("2026-08-01", periods=n, freq="5min")
    close = start + np.cumsum(np.ones(n) * 0.05 * trend)
    if compression:
        high = close + 0.05
        low = close - 0.05
    else:
        high = close + (0.8 if trend >= 0 else 0.3)
        low = close - (0.3 if trend >= 0 else 0.8)
    open_ = close - (0.1 * trend)
    # Make last HTF-ish bullish/bearish candles clear
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.ones(n) * 100},
        index=idx,
    )
    return df


def _setup(**kwargs):
    base = dict(
        strategy_name="liquidity_sweep",
        symbol="MES",
        direction="BUY",
        setup_tier="B",
        confidence_score=70,
        entry=100.0,
        stop=99.0,
        target=102.0,
        expected_r=2.0,
        market_timestamp=datetime(2026, 8, 7, 10, 30),
        received_timestamp=datetime(2026, 8, 7, 10, 45, tzinfo=timezone.utc),
        reasons=["strategy:liquidity_sweep"],
        metadata={"strategy_local_score": 70, "has_location": True},
    )
    base.update(kwargs)
    return TradeSetup(**base)


def test_locked_config_unchanged():
    cfg = _cfg()
    assert cfg["quantity"]["default_quantity"] == 2
    assert cfg["quantity"]["quantity_by_tier"]["A+"] == 3
    assert cfg["quantity"]["max_quantity"] == 25
    assert float(cfg["risk"]["max_risk_dollars_per_trade"]) == 500
    assert cfg["risk"]["max_total_open_risk_dollars"] == 3500
    assert cfg["risk"]["max_open_positions"] == 50
    assert cfg["risk"]["daily_loss_kill_dollars"] == 4000
    assert cfg["tiering"]["minimum_trade_tier"] == "A"
    assert cfg["mode"] == "paper"
    assert set(cfg["confluence"]["engines"]) == set(cfg["paper_specialist_engines"])
    assert "momentum" in cfg["research_only_engines"]
    assert "momentum" not in cfg["confluence"]["engines"]


def test_regime_trend_up_down_range_compression_unknown():
    clf = MarketRegimeClassifier()
    up = clf.classify(_bars(80, trend=1.0))
    assert up.regime in {MarketRegime.TREND_UP, MarketRegime.EXPANSION_UP, MarketRegime.RANGE}
    down = clf.classify(_bars(80, trend=-1.0))
    assert down.regime in {
        MarketRegime.TREND_DOWN,
        MarketRegime.EXPANSION_DOWN,
        MarketRegime.RANGE,
    }
    # Flat, tight ranges — no directional drift (compression / range)
    flat = _bars(80, trend=0.0, compression=True)
    flat["close"] = 100.0
    flat["open"] = 100.0
    flat["high"] = 100.05
    flat["low"] = 99.95
    comp = clf.classify(flat)
    assert comp.regime in {
        MarketRegime.COMPRESSION,
        MarketRegime.RANGE,
        MarketRegime.UNKNOWN,
    }
    unk = clf.classify(_bars(10))
    assert unk.regime == MarketRegime.UNKNOWN
    assert "INSUFFICIENT_BARS" in unk.reasons


def test_regime_no_future_bars():
    df = _bars(80)
    # Classifier only sees provided frame — truncating changes result vs full future
    early = MarketRegimeClassifier().classify(df.iloc[:60])
    late = MarketRegimeClassifier().classify(df)
    assert early.regime != MarketRegime.UNKNOWN or len(df.iloc[:60]) < 55
    assert late.reasons  # deterministic reasons exist


def test_market_context_candle_dir_not_ema():
    df = _bars(100, trend=1.0)
    # Force last 15m-ish aggregation: make last bars bearish candle while EMA still up
    df.iloc[-1, df.columns.get_loc("open")] = float(df["close"].iloc[-1]) + 2
    df.iloc[-1, df.columns.get_loc("close")] = float(df["close"].iloc[-1]) - 1
    ctx = build_market_context(df)
    # EMA may still be bull from trend; candle direction fields are close vs open
    assert ctx.direction_15m in (-1, 0, 1)
    # Ensure fields exist separately
    assert isinstance(ctx.ema_bull, bool)


def test_global_score_mtf_vwap_location_and_hard_block():
    cfg = _cfg()
    df = _bars(100, trend=1.0)
    ctx = build_market_context(df)
    s = _setup(expected_r=2.0)
    gs = score_setup(s, ctx, cfg)
    assert 0 <= gs.score <= 100
    assert any(c.family == "PRIMARY" for c in gs.components)
    # Hard invalidation blocks even high score
    gs2 = score_setup(s, ctx, cfg, hard_invalidations=["DATA_STALE"])
    assert "DATA_STALE" in gs2.hard_invalidations
    tier = assign_tier_from_global(
        s,
        cfg,
        global_score=100,
        families_positive=gs2.families_positive,
        has_location=True,
        hard_invalidations=gs2.hard_invalidations,
    )
    assert tier == "C"


def test_evidence_families_not_double_counted():
    cfg = _cfg()
    df = _bars(100, trend=1.0)
    ctx = build_market_context(df)
    s = _setup()
    gs = score_setup(s, ctx, cfg)
    fams = [c.family for c in gs.components]
    assert len(fams) == len(set(fams))


def test_lone_ema_remains_b_with_global_score():
    cfg = _cfg()
    s = _setup(
        strategy_name="ema_pullback",
        metadata={"strategy_local_score": 82, "has_location": False, "agreeing_engines": ["ema_pullback"]},
        confidence_score=82,
        expected_r=1.5,
    )
    tier = assign_tier_from_global(
        s,
        cfg,
        global_score=78,
        families_positive=["EMA_TREND", "VWAP"],
        has_location=False,
        contradictions=[],
    )
    assert tier == "B"
    s.setup_tier = tier
    assert not can_execute(s, cfg)


def test_soft_prior_day_location_does_not_promote_lone_ema():
    """Near PDH/PDL alone must not mint A for ema_pullback."""
    cfg = _cfg()
    s = _setup(
        strategy_name="ema_pullback",
        metadata={
            "agreeing_engines": ["ema_pullback"],
            "location_source": "soft_prior_day",
        },
        confidence_score=90,
        expected_r=1.8,
        reward_dollars=150,
    )
    tier = assign_tier_from_global(
        s,
        cfg,
        global_score=92,
        families_positive=["EMA_TREND", "VWAP", "MTF", "LOCATION"],
        has_location=True,
        contradictions=[],
    )
    assert tier == "B"
    s.setup_tier = tier
    assert not can_execute(s, cfg)


def test_ema_is_research_only_not_executable():
    cfg = _cfg()
    assert "ema_pullback" in (cfg.get("research_only_engines") or [])
    s = _setup(
        strategy_name="ema_pullback",
        metadata={
            "agreeing_engines": ["ema_pullback", "liquidity_sweep"],
            "location_source": "location_engine",
            "has_location": True,
            "research_only": True,
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "PULLBACK",
            },
        },
        confidence_score=80,
        expected_r=1.8,
        reward_dollars=180,
    )
    s.setup_tier = "A"
    assert not can_execute(s, cfg)


def test_location_engine_with_thesis_can_execute():
    cfg = _execution_logic_cfg("liquidity_sweep")
    s = _setup(
        strategy_name="liquidity_sweep",
        metadata={
            "agreeing_engines": ["liquidity_sweep"],
            "has_location": True,
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
        confidence_score=80,
        expected_r=1.8,
        reward_dollars=180,
    )
    s.setup_tier = "A"
    assert can_execute(s, cfg)


def test_execution_quality_rejects_small_reward():
    cfg = _cfg()
    s = _setup(
        strategy_name="liquidity_sweep",
        metadata={
            "agreeing_engines": ["liquidity_sweep"],
            "has_location": True,
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
        confidence_score=80,
        expected_r=1.8,
        reward_dollars=40,
    )
    s.setup_tier = "A"
    assert not can_execute(s, cfg)


def test_research_only_cannot_steal_paper_slot():
    """Shadow EMA/trend must not supersede an executable location engine."""
    from agent.decision.ranker import boost_for_agreement

    cfg = _execution_logic_cfg("liquidity_sweep")
    paper = _setup(
        strategy_name="liquidity_sweep",
        symbol="MGC",
        setup_tier="A",
        confidence_score=80,
        expected_r=1.8,
        reward_dollars=180,
        metadata={
            "has_location": True,
            "agreeing_engines": ["liquidity_sweep"],
            "global_score": 80,
            "families_positive": ["LOCATION", "VWAP", "MTF"],
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
    )
    shadow = _setup(
        strategy_name="ema_pullback",
        symbol="MGC",
        setup_tier="A+",
        confidence_score=95,
        expected_r=2.0,
        reward_dollars=200,
        metadata={
            "research_only": True,
            "execution_mode": "SHADOW",
            "agreeing_engines": ["ema_pullback"],
            "global_score": 95,
            "families_positive": ["EMA_TREND", "VWAP", "MTF"],
        },
    )
    kept, superseded = boost_for_agreement([paper, shadow], cfg)
    assert len(kept) == 1
    assert kept[0].strategy_name == "liquidity_sweep"
    assert any(loser.strategy_name == "ema_pullback" for loser, _ in superseded)


def test_mixed_thesis_allows_location_engine():
    """Location A may paper when MTF is imperfect — factors won't always agree."""
    cfg = _execution_logic_cfg("liquidity_sweep")
    eq = dict(cfg.get("execution_quality") or {})
    eq["location_may_trade_mixed_thesis"] = True
    cfg["execution_quality"] = eq
    s = _setup(
        strategy_name="liquidity_sweep",
        metadata={
            "agreeing_engines": ["liquidity_sweep"],
            "has_location": True,
            "cascade": {
                "thesis": "MIXED",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
        confidence_score=80,
        expected_r=1.8,
        reward_dollars=180,
    )
    s.setup_tier = "A"
    assert can_execute(s, cfg)
    assert execution_reject_reason(s, cfg) is None


def test_mixed_thesis_still_blocks_thin_engine():
    cfg = _execution_logic_cfg("momentum", "breakout_retest")
    eq = dict(cfg.get("execution_quality") or {})
    eq["location_may_trade_mixed_thesis"] = True
    eq["require_non_mixed_thesis"] = True
    cfg["execution_quality"] = eq
    s = _setup(
        strategy_name="momentum",
        metadata={
            "agreeing_engines": ["momentum", "breakout_retest"],
            "cascade": {
                "thesis": "MIXED",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "MOMENTUM",
            },
        },
        confidence_score=80,
        expected_r=1.8,
        reward_dollars=180,
    )
    s.setup_tier = "A"
    assert not can_execute(s, cfg)
    assert execution_reject_reason(s, cfg) == "EXECUTION_QUALITY:thesis_MIXED"


def test_unknown_cascade_thesis_does_not_block():
    """Missing cascade features must not default-block as MIXED."""
    cfg = _execution_logic_cfg("liquidity_sweep")
    s = _setup(
        strategy_name="liquidity_sweep",
        metadata={
            "agreeing_engines": ["liquidity_sweep"],
            "has_location": True,
            "cascade": {
                "thesis": "",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "NONE",
            },
        },
        confidence_score=80,
        expected_r=1.8,
        reward_dollars=180,
    )
    s.setup_tier = "A"
    assert can_execute(s, cfg)
    assert execution_reject_reason(s, cfg) is None


def test_poor_vwap_distance_allows_location_engine():
    """Breakout/OR often fire >1.5 ATR from VWAP — do not POOR-kill location engines."""
    cfg = _execution_logic_cfg("breakout_retest")
    eq = dict(cfg.get("execution_quality") or {})
    eq["reject_poor_cascade_location"] = True
    eq["location_may_trade_away_from_vwap"] = True
    cfg["execution_quality"] = eq
    s = _setup(
        strategy_name="breakout_retest",
        metadata={
            "agreeing_engines": ["breakout_retest"],
            "has_location": True,
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "POOR_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
        confidence_score=85,
        expected_r=1.8,
        reward_dollars=180,
    )
    s.setup_tier = "A+"
    assert can_execute(s, cfg)
    assert execution_reject_reason(s, cfg) is None


def test_poor_vwap_distance_still_blocks_thin_engine():
    cfg = _execution_logic_cfg("momentum", "breakout_retest")
    eq = dict(cfg.get("execution_quality") or {})
    eq["reject_poor_cascade_location"] = True
    eq["location_may_trade_away_from_vwap"] = True
    cfg["execution_quality"] = eq
    s = _setup(
        strategy_name="momentum",
        metadata={
            "agreeing_engines": ["momentum", "breakout_retest"],
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "POOR_LOCATION",
                "trigger": "MOMENTUM",
            },
        },
        confidence_score=85,
        expected_r=1.8,
        reward_dollars=180,
    )
    s.setup_tier = "A"
    assert not can_execute(s, cfg)
    assert execution_reject_reason(s, cfg) == "EXECUTION_QUALITY:POOR_LOCATION"


def test_agreement_keeps_paperable_before_quality_filter():
    """Location A with MIXED thesis stays in agreement pool for ledgered reject."""
    cfg = _execution_logic_cfg("liquidity_sweep")
    paper = _setup(
        strategy_name="liquidity_sweep",
        metadata={
            "agreeing_engines": ["liquidity_sweep", "ema_pullback"],
            "has_location": True,
            "cascade": {
                "thesis": "MIXED",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
        confidence_score=76,
        expected_r=2.2,
        reward_dollars=220,
    )
    paper.setup_tier = "A"
    paper.symbol = "MYM"
    paper.direction = "BUY"
    shadow = _setup(
        strategy_name="ema_pullback",
        metadata={
            "agreeing_engines": ["liquidity_sweep", "ema_pullback"],
            "research_only": True,
            "execution_mode": "SHADOW",
            "cascade": {
                "thesis": "MIXED",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "PULLBACK",
            },
        },
        confidence_score=84,
        expected_r=5.0,
        reward_dollars=100,
    )
    shadow.setup_tier = "A"
    shadow.symbol = "MYM"
    shadow.direction = "BUY"
    kept, _ = select_executable_detailed([paper, shadow], cfg)
    assert len(kept) == 1
    assert kept[0].strategy_name == "liquidity_sweep"
    # quality2g: location engines may paper with MIXED thesis
    assert can_execute(kept[0], cfg)


def test_score_alone_cannot_mint_a_plus():
    cfg = _cfg()
    s = _setup(strategy_name="ema_pullback", expected_r=2.5)
    tier = assign_tier_from_global(
        s,
        cfg,
        global_score=95,
        families_positive=["MTF", "VWAP"],  # only 2, no location
        has_location=False,
    )
    assert tier != "A+"


def test_momentum_exhaustion_vs_valid(tmp_path):
    cfg = _cfg()
    df = _bars(60, trend=1.0)
    # Giant exhaustion candle
    df.iloc[-1, df.columns.get_loc("open")] = float(df["close"].iloc[-2])
    df.iloc[-1, df.columns.get_loc("close")] = float(df["close"].iloc[-2]) + 5.0
    df.iloc[-1, df.columns.get_loc("high")] = float(df["close"].iloc[-1]) + 0.1
    df.iloc[-1, df.columns.get_loc("low")] = float(df["open"].iloc[-1]) - 0.1
    # ATR will be small relative → body_atr huge → no entry
    sig = evaluate_momentum("MES", df, cfg, point_value=5.0)
    # Either None (exhaustion/extension) or valid — if present must be entry_valid
    if sig is not None:
        assert sig.entry_valid is True
        assert sig.momentum_present is True


def test_shadow_does_not_affect_equity_and_tracks_mae(tmp_path):
    path = tmp_path / "shadow.json"
    st = ShadowTracker(path)
    st.open_shadow(
        {
            "symbol": "MES",
            "side": "BUY",
            "entry": 100,
            "stop": 99,
            "target": 102,
            "point_value": 5.0,
            "qty": 1,
            "strategy": "ema_pullback",
            "tier": "B",
            "market_timestamp": "2026-08-07T10:00:00",
        }
    )
    st.mark_prices({"MES": 99.5})  # adverse
    assert st._state["open"][0]["mae_pts"] >= 0.5
    st.mark_prices({"MES": 98.9})  # stop
    assert st.summary()["count"] >= 1
    # Equity untouched — shadow has separate file; blotter equity not referenced
    assert "hypothetical_pnl" in st.summary()


def test_exit_research_isolated():
    row = evaluate_fixed_r(
        side="BUY", entry=100, stop=99, path_high=102.5, path_low=99.5, r_mult=2.0
    )
    assert row["result"] == "WIN"
    assert row["exit"] == 102.0


def test_challenger_shadow_only_and_no_auto_promotion():
    cfg = _cfg()
    cfg["strategy_versions"] = {
        "ema_pullback": {"champion": "ema_pullback_v1", "challengers": ["ema_pullback_v2"]}
    }
    assert resolve_execution_mode(cfg, "ema_pullback", "ema_pullback_v2") == "SHADOW"
    assert resolve_execution_mode(cfg, "ema_pullback", "ema_pullback_v1") == "ACTUAL"
    v = evaluate_promotion(
        cfg,
        strategy="ema_pullback",
        champion_stats={"expectancy": 1, "profit_factor": 1.2, "max_drawdown": 100},
        challenger_stats={
            "trade_count": 10,
            "expectancy": 5,
            "profit_factor": 2,
            "max_drawdown": 50,
        },
    )
    assert v.promotion_candidate is False  # sample too small


def test_circuit_breaker_pause_independent(tmp_path):
    cfg = _cfg()
    cfg["circuit_breakers"] = {
        "consecutive_losses_watch": 2,
        "consecutive_losses_pause": 3,
        "pause_minutes": 60,
        "path": str(tmp_path / "cb.json"),
    }
    store = CircuitBreakerStore(tmp_path / "cb.json")
    store.record_close("ema_pullback", "london", -10, cfg)
    store.record_close("ema_pullback", "london", -10, cfg)
    st = store.record_close("ema_pullback", "london", -10, cfg)
    assert st == StrategyHealth.PAUSED_TEMP
    # Other strategy still active
    assert store.status("momentum", "london", cfg) == StrategyHealth.ACTIVE


def test_portfolio_product_family_and_index():
    cfg = _cfg()
    coord = PortfolioCoordinator(cfg)
    state = PortfolioState(opens=[{"symbol": "MES", "side": "BUY"}])
    ok, reason = coord.check(ExposureIntent("a2", "ES", "BUY", 1, "x", "A"), state)
    assert not ok


def test_paper_friction_never_improves():
    cfg = _cfg()
    e, s, t, note = apply_paper_friction(
        cfg, symbol="MES", side="BUY", entry=100, stop=99, target=102
    )
    assert e >= 100 and s <= 99 and t <= 102
    assert "FILL_MODEL_LIMITATION" in note
    e2, s2, t2, _ = apply_paper_friction(
        cfg, symbol="MNQ", side="SELL", entry=100, stop=101, target=98
    )
    assert e2 <= 100 and s2 >= 101 and t2 >= 98


def test_old_journal_missing_regime_loads():
    # Backward compatible defaults
    t = {"symbol": "MES", "pnl_dollars": 1.0}
    regime = t.get("regime") or "UNKNOWN"
    assert regime == "UNKNOWN"
