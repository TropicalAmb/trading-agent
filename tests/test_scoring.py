from __future__ import annotations

from datetime import date, datetime, timezone

from agent.management.scoring import score_candidate
from agent.models import CreditSpreadCandidate, OptionLeg, Side, SpreadType


def _cand(otm_pct: float = 0.03, credit: float = 1.0) -> CreditSpreadCandidate:
    spot = 500.0
    short = spot * (1 - otm_pct)
    return CreditSpreadCandidate(
        underlying="SPY",
        spread_type=SpreadType.PUT_CREDIT,
        short_leg=OptionLeg(
            symbol="SPY",
            expiry=date(2030, 1, 17),
            strike=short,
            right="P",
            action=Side.SELL,
        ),
        long_leg=OptionLeg(
            symbol="SPY",
            expiry=date(2030, 1, 17),
            strike=short - 5,
            right="P",
            action=Side.BUY,
        ),
        width=5.0,
        credit=credit,
        max_loss=(5.0 - credit) * 100,
        dte=30,
        spot=spot,
        iv_rank=60,
        trend_ok=True,
        quote_ts=datetime.now(timezone.utc),
    )


def test_better_yield_scores_higher():
    low = score_candidate(_cand(credit=0.6))
    high = score_candidate(_cand(credit=1.5))
    assert high > low


def test_too_close_otm_penalized():
    far = score_candidate(_cand(otm_pct=0.04, credit=1.0))
    near = score_candidate(_cand(otm_pct=0.005, credit=1.0))
    assert far > near
