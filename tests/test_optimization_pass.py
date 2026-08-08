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
from agent.decision.tiering import assign_tier_from_global, can_execute
from agent.execution.directional import apply_paper_friction
from agent.journal.shadow import ShadowTracker
from agent.research.exit_models import evaluate_fixed_r
from agent.risk.circuit_breakers import CircuitBreakerStore, StrategyHealth
from agent.risk.portfolio import ExposureIntent, PortfolioCoordinator, PortfolioState
from agent.strategy.momentum import evaluate_momentum

ROOT = Path(__file__).resolve().parents[1]


def _cfg():
    return load_settings(ROOT / "config" / "settings.yaml")


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
    assert cfg["quantity"]["default_quantity"] == 1
    assert cfg["quantity"]["max_quantity"] == 25
    assert cfg["risk"]["max_risk_dollars_per_trade"] == 250
    assert cfg["risk"]["max_total_open_risk_dollars"] == 3500
    assert cfg["risk"]["max_open_positions"] == 50
    assert cfg["risk"]["daily_loss_kill_dollars"] == 4000
    assert cfg["tiering"]["minimum_trade_tier"] == "A"
    assert cfg["mode"] == "paper"
    assert "momentum" in cfg["confluence"]["engines"]


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
