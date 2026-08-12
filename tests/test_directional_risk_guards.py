from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from agent.models import AccountSnapshot
from agent.risk.directional import DirectionalRiskEngine


def _sig(**kwargs):
    base = dict(
        symbol="MES",
        side="BUY",
        entry=5000.0,
        stop=4990.0,
        target=5020.0,
        confidence=80,
        risk_dollars=50.0,
        reward_dollars=100.0,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _acct():
    return AccountSnapshot(
        equity=50_000,
        cash=50_000,
        buying_power=100_000,
        open_positions=0,
        open_underlyings=[],
        realized_pnl_today=0.0,
        unrealized_pnl=0.0,
        healthy=True,
    )


def test_symbol_cooldown_blocks_reentry():
    cfg = {
        "risk": {"symbol_cooldown_minutes": 45, "max_open_positions": 10},
        "growth_plan": {"active": {"min_confidence": 50}},
        "sweep_retest": {
            "min_confidence": 50,
            "max_risk_dollars": 250,
            "min_reward_dollars": 50,
        },
        "schedule": {
            "timezone": "America/New_York",
            "entry_mode": "always_open",
            "weekend_open": "18:00",
            "weekend_close": "17:00",
            "maintenance_start": "17:00",
            "maintenance_end": "18:00",
        },
    }
    eng = DirectionalRiskEngine(cfg)
    last = datetime.now(timezone.utc) - timedelta(minutes=10)
    ok, reasons = eng.evaluate(
        _sig(),
        _acct(),
        [],
        skip_session_check=True,
        last_fill_ts={"MES": last},
    )
    assert not ok
    assert any("cooldown" in r for r in reasons)


def test_opposite_correlated_blocked():
    cfg = {
        "risk": {
            "block_opposite_correlated": True,
            "correlation_groups": [["MES", "MNQ", "MYM"]],
            "max_open_positions": 10,
        },
        "growth_plan": {"active": {"min_confidence": 50}},
        "sweep_retest": {
            "min_confidence": 50,
            "max_risk_dollars": 250,
            "min_reward_dollars": 50,
        },
        "schedule": {
            "timezone": "America/New_York",
            "entry_mode": "always_open",
            "weekend_open": "18:00",
            "weekend_close": "17:00",
            "maintenance_start": "17:00",
            "maintenance_end": "18:00",
        },
    }
    eng = DirectionalRiskEngine(cfg)
    ok, reasons = eng.evaluate(
        _sig(symbol="MNQ", side="SELL", entry=20000, stop=20050, target=19900),
        _acct(),
        ["MES"],
        skip_session_check=True,
        open_sides={"MES": "BUY"},
    )
    assert not ok
    assert any("opposite correlated" in r for r in reasons)


def test_min_reward_uses_position_dollars_not_per_contract():
    """A+ qty=3 must not fail because reward/qty < stale sweep floor."""
    cfg = {
        "risk": {"max_open_positions": 50, "max_risk_dollars_per_trade": 500},
        "growth_plan": {"active": {"min_confidence": 50}},
        "execution_quality": {"min_reward_dollars": 150},
        "confluence": {"min_reward_dollars": 150},
        "sweep_retest": {
            "min_confidence": 50,
            "max_risk_dollars": 500,
            "min_reward_dollars": 90,
        },
        "schedule": {
            "timezone": "America/New_York",
            "entry_mode": "always_open",
            "weekend_open": "18:00",
            "weekend_close": "17:00",
            "maintenance_start": "17:00",
            "maintenance_end": "18:00",
        },
    }
    eng = DirectionalRiskEngine(cfg)
    # Per-contract $80 × qty 3 = $240 position reward ≥ $150 EQ floor
    sig = _sig(reward_dollars=80.0, risk_dollars=45.0)
    setattr(sig, "quantity", 3)
    ok, reasons = eng.evaluate(sig, _acct(), [], skip_session_check=True)
    assert ok, reasons


def test_min_reward_still_blocks_thin_position_reward():
    cfg = {
        "risk": {"max_open_positions": 50, "max_risk_dollars_per_trade": 500},
        "growth_plan": {"active": {"min_confidence": 50}},
        "execution_quality": {"min_reward_dollars": 150},
        "sweep_retest": {"min_confidence": 50, "max_risk_dollars": 500, "min_reward_dollars": 90},
        "schedule": {
            "timezone": "America/New_York",
            "entry_mode": "always_open",
            "weekend_open": "18:00",
            "weekend_close": "17:00",
            "maintenance_start": "17:00",
            "maintenance_end": "18:00",
        },
    }
    eng = DirectionalRiskEngine(cfg)
    sig = _sig(reward_dollars=40.0, risk_dollars=20.0)
    setattr(sig, "quantity", 2)  # position reward $80 < $150
    ok, reasons = eng.evaluate(sig, _acct(), [], skip_session_check=True)
    assert not ok
    assert any("reward $" in r and "< min" in r for r in reasons)
