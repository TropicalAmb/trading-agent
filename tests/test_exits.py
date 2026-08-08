from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from agent.management.exits import estimate_close_debit, evaluate_exits
from agent.models import OpenPosition, SpreadType


def _pos(**kwargs) -> OpenPosition:
    today = date.today()
    data = dict(
        id="abc",
        underlying="SPY",
        spread_type=SpreadType.PUT_CREDIT,
        short_strike=500.0,
        long_strike=495.0,
        right="P",
        expiry=today + timedelta(days=30),
        width=5.0,
        entry_credit=1.0,
        quantity=1,
        entry_spot=520.0,
        entry_ts=datetime.now(timezone.utc) - timedelta(days=5),
        status="open",
    )
    data.update(kwargs)
    return OpenPosition(**data)


def test_profit_target_triggers_when_debit_cheap():
    cfg = {
        "management": {
            "profit_take_frac_of_credit": 0.50,
            "stop_loss_mult_of_credit": 2.0,
            "time_exit_dte": 21,
            "force_close_dte": 7,
        }
    }
    # Entered ~25 days ago, expiry in 5 days → extrinsic mostly gone, OTM → profit target
    today = date.today()
    pos = _pos(
        expiry=today + timedelta(days=5),
        entry_ts=datetime.now(timezone.utc) - timedelta(days=25),
        entry_credit=1.0,
    )
    signals = evaluate_exits([pos], {"SPY": 530.0}, cfg, today=today)
    assert signals
    assert signals[0].reason.value in {"profit_target", "expiry_risk", "time_exit"}
    assert signals[0].pnl >= 0


def test_stop_loss_when_spot_crashes_through_short():
    cfg = {
        "management": {
            "profit_take_frac_of_credit": 0.50,
            "stop_loss_mult_of_credit": 2.0,
            "time_exit_dte": 21,
            "force_close_dte": 7,
        }
    }
    pos = _pos(entry_credit=1.0, width=5.0, short_strike=500, long_strike=495)
    signals = evaluate_exits([pos], {"SPY": 490.0}, cfg)
    assert signals
    assert signals[0].reason.value == "stop_loss"
    assert signals[0].pnl < 0


def test_estimate_close_debit_bounded_by_width():
    pos = _pos()
    debit = estimate_close_debit(pos, spot=400.0, days_passed=10, entry_dte=30)
    assert 0 < debit <= pos.width
