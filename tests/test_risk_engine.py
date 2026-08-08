from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from agent.models import (
    AccountSnapshot,
    CreditSpreadCandidate,
    OptionLeg,
    Side,
    SpreadType,
)
from agent.risk.engine import RiskEngine


def _cfg(**overrides):
    base = {
        "schedule": {
            "timezone": "America/New_York",
            "entry_start": "09:45",
            "entry_end": "15:30",
        },
        "risk": {
            "max_contracts_per_trade": 1,
            "max_open_positions": 3,
            "max_loss_pct_of_equity_per_trade": 0.02,
            "daily_loss_kill_pct": 0.03,
            "max_correlated_index_positions": 1,
            "index_symbols": ["SPY", "QQQ", "IWM"],
            "require_defined_risk": True,
            "require_both_legs": True,
            "halt_on_stale_data": True,
            "max_quote_age_sec": 120,
        },
    }
    base.update(overrides)
    return base


def _put_credit(qty: int = 1, width: float = 5.0, credit: float = 1.0) -> CreditSpreadCandidate:
    expiry = date(2030, 1, 17)
    max_loss = (width - credit) * 100 * qty
    return CreditSpreadCandidate(
        underlying="SPY",
        spread_type=SpreadType.PUT_CREDIT,
        short_leg=OptionLeg(
            symbol="SPY", expiry=expiry, strike=500, right="P", action=Side.SELL, quantity=qty
        ),
        long_leg=OptionLeg(
            symbol="SPY", expiry=expiry, strike=495, right="P", action=Side.BUY, quantity=qty
        ),
        width=width,
        credit=credit,
        max_loss=max_loss,
        dte=30,
        spot=520,
        iv_rank=40,
        quote_ts=datetime.now(timezone.utc),
    )


def _account(**kwargs) -> AccountSnapshot:
    data = dict(
        equity=100_000,
        cash=80_000,
        buying_power=200_000,
        open_positions=0,
        open_underlyings=[],
        realized_pnl_today=0.0,
        unrealized_pnl=0.0,
        healthy=True,
    )
    data.update(kwargs)
    return AccountSnapshot(**data)


def test_approves_valid_defined_risk_spread():
    engine = RiskEngine(_cfg())
    verdict = engine.evaluate(
        _put_credit(), _account(), skip_session_check=True
    )
    assert verdict.approved
    assert verdict.sized_candidate is not None
    assert verdict.sized_candidate.contracts == 1


def test_rejects_naked_short_missing_long_protection():
    engine = RiskEngine(_cfg())
    c = _put_credit()
    # Corrupt: long strike above short for put credit = not protective
    c.long_leg.strike = 505
    verdict = engine.evaluate(c, _account(), skip_session_check=True)
    assert not verdict.approved
    assert any("below short" in r for r in verdict.reasons)


def test_rejects_oversized_max_loss():
    engine = RiskEngine(_cfg())
    # width 5, credit 0.1 → max loss ~490 per contract; with tiny equity fails
    c = _put_credit(credit=0.1)
    verdict = engine.evaluate(
        c, _account(equity=1_000), skip_session_check=True
    )
    assert not verdict.approved
    assert any("exceeds" in r or "budget" in r for r in verdict.reasons)


def test_daily_kill_switch():
    engine = RiskEngine(_cfg())
    # 4% daily realized loss on 100k with 3% kill
    acct = _account(realized_pnl_today=-4_000)
    verdict = engine.evaluate(_put_credit(), acct, skip_session_check=True)
    assert verdict.kill_switch
    assert not verdict.approved
    # Subsequent calls remain halted
    verdict2 = engine.evaluate(_put_credit(), _account(), skip_session_check=True)
    assert verdict2.halt_trading


def test_rejects_outside_rth():
    engine = RiskEngine(_cfg())
    # Sunday evening ET
    sunday = datetime(2026, 8, 2, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    verdict = engine.evaluate(_put_credit(), _account(), now=sunday)
    assert not verdict.approved
    assert any("weekend" in r for r in verdict.reasons)


def test_rejects_correlated_index_book():
    engine = RiskEngine(_cfg())
    acct = _account(open_positions=1, open_underlyings=["QQQ"])
    verdict = engine.evaluate(_put_credit(), acct, skip_session_check=True)
    assert not verdict.approved
    assert any("correlated" in r for r in verdict.reasons)


def test_rejects_stale_quote():
    engine = RiskEngine(_cfg())
    c = _put_credit()
    c.quote_ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    verdict = engine.evaluate(c, _account(), skip_session_check=True)
    assert not verdict.approved
    assert any("stale" in r for r in verdict.reasons)


def test_caps_contracts_to_max():
    engine = RiskEngine(_cfg())
    c = _put_credit(qty=5)
    # Still may fail max loss — use rich credit so max loss small
    c = _put_credit(qty=5, credit=4.5)
    verdict = engine.evaluate(c, _account(), skip_session_check=True)
    assert verdict.approved
    assert verdict.sized_candidate.contracts == 1
