from __future__ import annotations

from agent.broker.ibkr import MockIBKRClient
from agent.config import load_settings
from agent.market_data import MarketDataService, pick_expiry
from agent.strategy.credit_spreads import CreditSpreadScanner
from datetime import date, timedelta


def test_pick_expiry_respects_dte_window():
    today = date(2026, 8, 6)
    expiries = [today + timedelta(days=d) for d in (3, 10, 20, 60)]
    picked = pick_expiry(expiries, min_dte=7, max_dte=45, today=today)
    assert picked == today + timedelta(days=10)


def test_scanner_produces_defined_risk_candidates():
    cfg = load_settings()
    # Force equity option universe for this legacy test
    cfg["universe"]["symbols"] = ["SPY", "QQQ", "GLD"]
    cfg["strategy"]["min_iv_rank"] = 0
    cfg["strategy"]["use_trend_filter"] = False
    cfg["strategy"]["min_credit_pct_of_width"] = 0.05
    cfg["strategy"]["min_score"] = -1e9

    broker = MockIBKRClient()
    broker.connect()
    market = MarketDataService(broker, cfg)
    scanner = CreditSpreadScanner(market, cfg)
    candidates = scanner.scan_universe()
    assert len(candidates) > 0
    for c in candidates:
        assert c.width > 0
        assert c.credit > 0
        assert c.max_loss > 0
        assert c.short_leg.action.value == "SELL"
        assert c.long_leg.action.value == "BUY"
        assert c.short_leg.right == c.long_leg.right
