"""Non-regression tests for locked trading-agent invariants."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import yaml

from agent.config import load_settings
from agent.data.bar_cursor import BarCursorStore
from agent.data.base import Bar
from agent.decision.ranker import select_executable
from agent.decision.setup import TradeSetup
from agent.decision.tiering import assign_tier, can_execute
from agent.execution.sizing import resolve_trade_quantity
from agent.risk.portfolio import ExposureIntent, PortfolioCoordinator, PortfolioState
from agent.schedule.sessions import futures_market_open, session_ok


ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")


def _cfg():
    return load_settings(ROOT / "config" / "settings.yaml")


def _execution_logic_cfg(*engine_names: str):
    """Opt named legacy engines into isolated logic tests, never live config."""
    cfg = _cfg()
    cfg["research_only_engines"] = [
        name for name in (cfg.get("research_only_engines") or []) if name not in engine_names
    ]
    return cfg


def _setup(tier="A", conf=75, symbol="MES", side="BUY", agent="agent_1", r=1.6):
    return TradeSetup(
        strategy_name="liquidity_sweep",
        symbol=symbol,
        direction=side,
        setup_tier=tier,
        confidence_score=conf,
        entry=100.0,
        stop=99.0,
        target=100.0 + r,
        expected_r=r,
        market_timestamp=datetime(2026, 8, 7, 10, 32),
        received_timestamp=datetime(2026, 8, 7, 10, 45, tzinfo=timezone.utc),
        reasons=["test"],
        agent_id=agent,
        quantity=1,
        reward_dollars=160.0,
        metadata={
            "has_location": True,
            "agreeing_engines": ["liquidity_sweep"],
            "location_source": "location_engine",
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        },
    )


def test_one_minute_scan_config():
    cfg = _cfg()
    assert int(cfg["schedule"]["poll_interval_minutes"]) == 1


def test_paid_databento_cache_is_in_paper_data_path_without_api_spend():
    cfg = _cfg()
    md = cfg["market_data"]
    assert md["provider"] == "databento_cache_yahoo"
    assert md["databento_allow_api_refresh"] is False


def test_asia_london_ny_tradable_when_exchange_open():
    cfg = _cfg()
    # Use non-Friday dates (skip_friday_entries may block Fri)
    # Thu Asia overnight
    ok, label = session_ok(cfg, datetime(2026, 8, 6, 21, 0, tzinfo=ET))
    assert ok and label == "asia"
    # Thu London / NY
    ok, label = session_ok(cfg, datetime(2026, 8, 6, 5, 0, tzinfo=ET))
    assert ok and label == "london"
    ok, label = session_ok(cfg, datetime(2026, 8, 6, 11, 0, tzinfo=ET))
    assert ok and ("ny" in label or label == "ny")
    # A research observation for one ORB variant must not disable the whole
    # specialist book on Friday while CME is still open.
    ok, label = session_ok(cfg, datetime(2026, 8, 14, 11, 0, tzinfo=ET))
    assert ok and label == "ny"


def test_cme_closed_window_blocks():
    cfg = _cfg()
    # Thursday maintenance window (Fri 17:30 is weekend-gap, not daily halt)
    ok, reason = futures_market_open(cfg, datetime(2026, 8, 6, 17, 30, tzinfo=ET))
    assert not ok
    assert "closed" in reason.lower() or "halt" in reason.lower()


def test_symbol_universe_not_mes_mnq_only():
    cfg = _cfg()
    syms = {s.upper() for s in cfg["universe"]["symbols"]}
    assert {"MES", "MNQ", "MGC", "ES", "NQ", "GC", "CL"}.issubset(syms)
    assert len(syms) >= 8


def test_quantity_configurable_not_hardcoded():
    cfg = _cfg()
    assert int(cfg["quantity"]["default_quantity"]) == 2
    assert resolve_trade_quantity(cfg, symbol="MES") == 2
    assert resolve_trade_quantity(cfg, symbol="MES", tier="A+") == 3
    cfg2 = dict(cfg)
    cfg2["quantity"] = {
        "default_quantity": 5,
        "max_quantity": 25,
        "quantity_by_symbol": {"MNQ": 10},
    }
    assert resolve_trade_quantity(cfg2, symbol="MES") == 5
    assert resolve_trade_quantity(cfg2, symbol="MNQ") == 10


def test_multi_quantity_pnl_and_risk():
    from agent.paper.blotter import _money

    one = abs(_money("BUY", 100, 99, 1, 5.0))
    five = abs(_money("BUY", 100, 99, 5, 5.0))
    assert five == one * 5


def test_no_trade_without_stop():
    from agent.risk.directional import DirectionalRiskEngine
    from agent.strategy.sweep_retest import SweepSignal
    from agent.models import AccountSnapshot

    cfg = _cfg()
    risk = DirectionalRiskEngine(cfg)
    sig = SweepSignal(
        symbol="MES",
        side="BUY",
        entry=100,
        stop=0,
        target=110,
        confidence=90,
        reason="x",
        pdh=1,
        pdl=1,
        ts=datetime.now(timezone.utc),
        risk_dollars=50,
        reward_dollars=100,
    )
    acct = AccountSnapshot(
        equity=50_000,
        cash=50_000,
        buying_power=50_000,
        realized_pnl_today=0,
        healthy=True,
    )
    ok, reasons = risk.evaluate(sig, acct, [], skip_session_check=True)
    assert not ok
    assert any("stop" in r.lower() or "missing" in r.lower() for r in reasons)


def test_tiers_a_plus_and_a_execute_b_c_do_not():
    cfg = _execution_logic_cfg("liquidity_sweep")
    assert can_execute(_setup("A+", 90), cfg)
    assert can_execute(_setup("A", 75), cfg)
    assert not can_execute(_setup("B", 60), cfg)
    assert not can_execute(_setup("C", 40), cfg)


def test_assign_tier_from_confidence():
    cfg = _cfg()
    # A+ needs multi-confirm + location/agreement — not confidence alone
    assert (
        assign_tier(
            90,
            expected_r=1.5,
            reason_count=3,
            cfg=cfg,
            strategy_name="liquidity_sweep",
            agreeing_engines=1,
            has_location=True,
        )
        == "A+"
    )
    assert (
        assign_tier(
            75,
            expected_r=1.5,
            reason_count=2,
            cfg=cfg,
            strategy_name="liquidity_sweep",
            has_location=True,
        )
        == "A"
    )
    # Lone EMA cannot be A/A+
    assert (
        assign_tier(
            82,
            expected_r=1.5,
            reason_count=1,
            cfg=cfg,
            strategy_name="ema_pullback",
            agreeing_engines=1,
            has_location=False,
        )
        == "B"
    )
    assert assign_tier(40, expected_r=1.0, reason_count=1, cfg=cfg) == "C"


def test_lone_ema_does_not_execute_as_a():
    from agent.decision.tiering import assign_tier_for_setup

    cfg = _cfg()
    s = _setup("A", 82)  # pretier — will be reassigned
    s.strategy_name = "ema_pullback"
    s.reasons = ["strategy:ema_pullback", "ema touch"]
    s.metadata = {"strategy_local_score": 82}
    s.setup_tier = assign_tier_for_setup(s, cfg)
    assert s.setup_tier == "B"
    assert not can_execute(s, cfg)


def test_product_family_blocks_mes_es_duplicate():
    cfg = _cfg()
    coord = PortfolioCoordinator(cfg)
    state = PortfolioState(opens=[{"symbol": "MES", "side": "BUY", "agent_id": "a1"}])
    ok, reason = coord.check(
        ExposureIntent("a2", "ES", "BUY", 1, "x", "A"), state
    )
    assert not ok
    assert "family" in reason.lower() or "MES" in reason


def test_prefer_full_size_over_micro_in_family():
    """MES+ES same side → keep ES so micros don't monopolize the family slot."""
    from agent.decision.ranker import prefer_full_size_within_family
    from agent.decision.setup import TradeSetup

    cfg = _cfg()
    cfg = dict(cfg)
    cfg["risk"] = dict(cfg.get("risk") or {})
    cfg["risk"]["prefer_full_size_in_family"] = True
    mes = TradeSetup(
        strategy_name="breakout_retest",
        symbol="MES",
        direction="BUY",
        setup_tier="A+",
        confidence_score=90,
        entry=5000.0,
        stop=4990.0,
        target=5020.0,
        expected_r=2.0,
        market_timestamp=datetime.now(timezone.utc),
        received_timestamp=datetime.now(timezone.utc),
        reasons=["mes"],
        metadata={"agreeing_engines": ["breakout_retest"], "global_score": 90},
    )
    es = TradeSetup(
        strategy_name="breakout_retest",
        symbol="ES",
        direction="BUY",
        setup_tier="A+",
        confidence_score=90,
        entry=5000.0,
        stop=4990.0,
        target=5020.0,
        expected_r=2.0,
        market_timestamp=datetime.now(timezone.utc),
        received_timestamp=datetime.now(timezone.utc),
        reasons=["es"],
        metadata={"agreeing_engines": ["breakout_retest"], "global_score": 90},
    )
    kept = prefer_full_size_within_family([mes, es], cfg)
    assert len(kept) == 1
    assert kept[0].symbol == "ES"


def test_hard_risk_limit_rejects_over_cap():
    from agent.risk.directional import DirectionalRiskEngine
    from agent.strategy.sweep_retest import SweepSignal
    from agent.models import AccountSnapshot

    cfg = _cfg()
    cfg = dict(cfg)
    cfg["risk"] = dict(cfg.get("risk") or {})
    cfg["risk"]["max_risk_dollars_per_trade"] = 500  # re-enable for this unit test
    risk = DirectionalRiskEngine(cfg)
    sig = SweepSignal(
        symbol="MGC",
        side="BUY",
        entry=2400,
        stop=2340,  # 60 pts * $10 = $600 > $500 hard cap
        target=2450,
        confidence=90,
        reason="x",
        pdh=1,
        pdl=1,
        ts=datetime.now(timezone.utc),
        risk_dollars=600.0,
        reward_dollars=500.0,
    )
    setattr(sig, "quantity", 1)
    acct = AccountSnapshot(
        equity=50_000,
        cash=50_000,
        buying_power=50_000,
        realized_pnl_today=0,
        healthy=True,
    )
    ok, reasons = risk.evaluate(sig, acct, [], skip_session_check=True)
    assert not ok
    assert any("RISK_LIMIT" in r for r in reasons)


def test_hard_risk_cap_finite_in_live_settings():
    from agent.execution.risk_budget import effective_max_risk_dollars

    cfg = _cfg()
    assert float(cfg["risk"]["max_risk_dollars_per_trade"]) == 500
    assert effective_max_risk_dollars(cfg) == 500.0


def test_instrument_point_values_and_stop_risk():
    from agent.paper.blotter import _money

    cfg = _cfg()
    expected = {
        "MES": 5.0,
        "MNQ": 2.0,
        "MGC": 10.0,
        "MYM": 0.5,
        "M2K": 5.0,
        "MCL": 100.0,
        "ES": 50.0,
        "NQ": 20.0,
        "CL": 1000.0,
        "GC": 100.0,
    }
    for sym, pv in expected.items():
        assert float(cfg["instruments"][sym]["point_value"]) == pv
        # 1.0 point stop risk for 1 contract
        assert abs(_money("BUY", 100.0, 99.0, 1, pv)) == pv


def test_setup_identity_suppresses_duplicate(tmp_path):
    from agent.decision.setup_identity import SetupIdentityStore, setup_fingerprint

    store = SetupIdentityStore(tmp_path / "id.json")
    fp = setup_fingerprint(
        symbol="MYM",
        strategy="ema_pullback",
        direction="BUY",
        market_bar_ts=datetime(2026, 8, 7, 10, 30),
        entry=42000.0,
        level=42000.0,
    )
    assert not store.already_traded(fp)
    store.mark_traded(fp)
    assert store.already_traded(fp)


def test_single_engine_can_qualify_without_mandatory_confluence():
    cfg = _execution_logic_cfg("liquidity_sweep")
    # must_include_one_of empty; min agree not used by decision pipeline
    # Non-EMA engines can still execute alone; EMA is the partner exception
    assert cfg.get("confluence", {}).get("must_include_one_of") in ([], None)
    s = _setup("A", 80)
    assert s.strategy_name == "liquidity_sweep"
    assert can_execute(s, cfg)


def test_multiple_aa_setups_selected_same_cycle():
    cfg = _execution_logic_cfg("liquidity_sweep")
    setups = []
    for tier, conf, sym in [("A", 80, "MES"), ("A+", 90, "MNQ"), ("A", 78, "MGC")]:
        s = _setup(tier, conf, symbol=sym)
        s.strategy_name = "liquidity_sweep"
        s.reasons = ["strategy:liquidity_sweep", "pdh sweep reclaim", "vwap support"]
        s.metadata = {"has_location": True, "agreeing_engines": ["liquidity_sweep"]}
        s.reward_dollars = 160.0
        s.expected_r = 1.6
        s.metadata = {
            **(s.metadata or {}),
            "cascade": {
                "thesis": "LONG_SUPPORT",
                "location": "ACCEPTABLE_LOCATION",
                "trigger": "BREAKOUT_RETEST",
            },
        }
        s.setup_tier = tier
        setups.append(s)
    exe = select_executable(setups, cfg)
    assert len(exe) == 3


def test_portfolio_blocks_opposite_and_duplicate():
    cfg = _cfg()
    coord = PortfolioCoordinator(cfg)
    state = PortfolioState(opens=[{"symbol": "MES", "side": "BUY", "agent_id": "a1"}])
    ok, reason = coord.check(
        ExposureIntent("a2", "MES", "SELL", 1, "x", "A"), state
    )
    assert not ok
    ok2, _ = coord.check(
        ExposureIntent("a2", "MES", "BUY", 1, "x", "A"), state
    )
    assert not ok2


def test_bar_cursor_processes_once(tmp_path):
    store = BarCursorStore(tmp_path / "cursors.json")
    ts = datetime(2026, 8, 7, 10, 32)
    assert not store.already_processed("MES", ts)
    store.set("MES", ts)
    assert store.already_processed("MES", ts)
    assert store.already_processed("MES", datetime(2026, 8, 7, 10, 30))
    assert not store.already_processed("MES", datetime(2026, 8, 7, 10, 35))


def test_stale_bar_flag():
    received = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    bar = Bar(
        symbol="MES",
        timestamp=datetime(2026, 8, 7, 10, 0),
        open=1,
        high=1,
        low=1,
        close=1,
        volume=1,
        source="yahoo_delayed",
        is_realtime=False,
        estimated_delay_seconds=7200,
        is_stale=True,
        received_time=received,
    )
    assert bar.is_stale
    assert not bar.is_realtime
    assert bar.timestamp != bar.received_time.replace(tzinfo=None)


def test_paper_mode_forces_dry_run_path():
    from agent.execution.directional import DirectionalExecutor
    from agent.strategy.sweep_retest import SweepSignal

    cfg = _cfg()
    cfg["mode"] = "paper"
    cfg["execution"]["dry_run"] = False  # even if mis-set
    broker = MagicMock()
    broker.place_bracket_order = MagicMock(return_value={"status": "LIVE"})
    blotter = MagicMock()
    blotter.record_paper_fill.return_value = {"id": "PAPER-1"}
    ex = DirectionalExecutor(broker, cfg, blotter=blotter)
    sig = SweepSignal(
        symbol="MES",
        side="BUY",
        entry=100,
        stop=99,
        target=102,
        confidence=80,
        reason="t",
        pdh=1,
        pdl=1,
        ts=datetime.now(timezone.utc),
        risk_dollars=5,
        reward_dollars=10,
    )
    setattr(sig, "quantity", 1)
    setattr(sig, "setup_tier", "A")
    result = ex.execute(sig)
    assert result["dry_run"] is True
    assert result["status"] == "PAPER_FILL"
    broker.place_bracket_order.assert_not_called()


def test_rejected_setup_has_reason_fields():
    s = _setup("B", 60)
    assert s.setup_tier == "B"
    assert s.entry and s.stop and s.target
    assert s.reasons


def test_trade_records_agent_strategy_tier_session():
    s = _setup("A", 80)
    s.session = "london"
    assert s.agent_id
    assert s.strategy_name
    assert s.setup_tier
    assert s.session


def test_market_and_received_timestamps_separate():
    s = _setup()
    assert s.market_timestamp.hour == 10 and s.market_timestamp.minute == 32
    assert s.received_timestamp.hour == 10 and s.received_timestamp.minute == 45


def test_settings_yaml_poll_and_universe_locked():
    raw = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    assert raw["schedule"]["poll_interval_minutes"] == 1
    assert "MGC" in raw["universe"]["symbols"]
    assert raw["quantity"]["default_quantity"] == 2
    assert raw["quantity"]["quantity_by_tier"]["A"] == 2
    assert raw["tiering"]["minimum_trade_tier"] == "A"
    assert raw["schedule"]["skip_friday_entries"] is False
    assert raw["shadow"]["evaluate_research_engines_live"] is False
    assert set(raw["confluence"]["engines"]) == set(raw["paper_specialist_engines"])
