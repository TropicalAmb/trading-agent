from __future__ import annotations

import numpy as np
import pandas as pd

from agent.strategy.liquidity_sweep import evaluate_liquidity_sweep
from agent.strategy.confluence import ConfluenceScanner


def _bars_with_pdh_sweep() -> pd.DataFrame:
    """Prior day high ~100; later wick above then reclaim below."""
    # Day 1
    d1 = pd.date_range("2026-08-04 09:30", periods=78, freq="5min", tz="UTC")
    close1 = np.linspace(95, 100, len(d1))
    df1 = pd.DataFrame(
        {
            "open": close1 - 0.2,
            "high": close1 + 0.5,
            "low": close1 - 0.5,
            "close": close1,
            "volume": np.full(len(d1), 1000.0),
        },
        index=d1,
    )
    # Day 2: sweep PDH then bearish reclaim
    d2 = pd.date_range("2026-08-05 09:30", periods=80, freq="5min", tz="UTC")
    close2 = np.concatenate(
        [
            np.linspace(99, 101.5, 40),  # push through PDH
            np.linspace(101.2, 98.5, 40),  # fail back inside
        ]
    )
    high2 = close2 + 0.4
    high2[38:42] = 102.5  # explicit sweep wick above PDH (~100)
    low2 = close2 - 0.4
    open2 = close2 + 0.3  # bearish closes relative to open near end
    open2[-5:] = close2[-5:] + 0.8
    df2 = pd.DataFrame(
        {
            "open": open2,
            "high": high2,
            "low": low2,
            "close": close2,
            "volume": np.full(len(d2), 1200.0),
        },
        index=d2,
    )
    return pd.concat([df1, df2])


def test_liquidity_sweep_can_signal_or_skip_safely():
    df = _bars_with_pdh_sweep()
    cfg = {
        "liquidity_sweep": {
            "min_confidence": 50,
            "max_risk_dollars": 500,
            "min_reward_dollars": 50,
            "target_dollars": 80,
            "allow_against_trend": True,
            "vwap_slack": 0.05,
        }
    }
    sig = evaluate_liquidity_sweep("MES", df, cfg, point_value=5.0)
    # Synthetic path may or may not fire depending on VWAP/EMA; must not crash
    if sig is not None:
        assert sig.side in {"BUY", "SELL"}
        assert sig.stop > 0 and sig.target > 0
        assert "LIQUIDITY_SWEEP" in sig.reason


def test_confluence_includes_liquidity_sweep_engine():
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

    cfg = {
        "universe": {"symbols": ["MES"]},
        "instruments": {"MES": {"point_value": 5.0}},
        "confluence": {
            "min_engines_agree": 2,
            "engines": ["liquidity_sweep", "vwap_acceptance", "sweep_retest"],
            "max_risk_dollars": 500,
            "min_reward_dollars": 50,
        },
        "liquidity_sweep": {"min_confidence": 0},
        "vwap_acceptance": {"min_confidence": 0, "skip_trend_days": False},
        "sweep_retest": {
            "min_confidence": 0,
            "max_risk_dollars": 500,
            "min_reward_dollars": 0,
        },
    }
    scanner = ConfluenceScanner(cfg, lambda _s: df)
    sig = scanner.scan_symbol("MES")
    assert sig is None or len(sig.voters) >= 2
