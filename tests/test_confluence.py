from __future__ import annotations

from agent.strategy.confluence import ConfluenceScanner
import pandas as pd
import numpy as np


def test_confluence_scanner_handles_empty_agreement():
    idx = pd.date_range("2026-08-06 09:30", periods=100, freq="5min")
    close = np.linspace(5200, 5210, 100)
    df = pd.DataFrame(
        {
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.full(100, 1000.0),
        },
        index=idx,
    )

    def src(_sym: str) -> pd.DataFrame:
        return df

    cfg = {
        "universe": {"symbols": ["MES"]},
        "instruments": {"MES": {"point_value": 5.0}},
        "confluence": {
            "min_engines_agree": 2,
            "engines": ["vwap_acceptance", "vwap_orb", "sweep_retest"],
            "max_risk_dollars": 100,
            "min_reward_dollars": 100,
        },
        "vwap_acceptance": {"min_confidence": 0, "skip_trend_days": False},
        "vwap_orb": {"min_confidence": 0, "skip_two_sided_days": False},
        "sweep_retest": {"min_confidence": 0, "max_risk_dollars": 500, "min_reward_dollars": 0},
    }
    scanner = ConfluenceScanner(cfg, src)
    # May be None — must not crash
    sig = scanner.scan_symbol("MES")
    assert sig is None or len(sig.voters) >= 2
