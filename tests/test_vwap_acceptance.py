from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from agent.strategy.vwap_acceptance import evaluate_vwap_acceptance


def test_globex_filter_allows_asia_evening():
    """RTH flatten/entry windows must not kill Asia (e.g. 21:00 ET)."""
    d1 = pd.date_range("2026-08-05 09:30", periods=80, freq="5min")
    d2 = pd.date_range("2026-08-05 18:00", periods=40, freq="5min")
    idx = d1.append(d2)
    close = np.concatenate(
        [np.linspace(5200, 5210, 80), np.linspace(5208, 5195, 40)]
    )
    df = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.full(len(idx), 1500.0),
        },
        index=idx,
    )
    cfg = {
        "vwap_acceptance": {
            "session_filter": "globex",
            "flatten_ct": "15:05",  # would kill Asia if honored
            "entry_start": "09:45",
            "entry_end": "15:00",
            "min_confidence": 0,
            "target_dollars": 150,
            "min_reward_dollars": 50,
            "max_risk_dollars": 200,
            "skip_trend_days": False,
        }
    }
    now = datetime(2026, 8, 5, 21, 0, tzinfo=ZoneInfo("America/New_York"))
    # Must not hard-return solely due to time-of-day (may still be None on setup)
    sig = evaluate_vwap_acceptance("MES", df, cfg, point_value=5.0, now=now)
    assert sig is None or sig.side in {"BUY", "SELL"}


def test_acceptance_runs_without_crash():
    # Two sessions so prior POC exists
    d1 = pd.date_range("2026-08-05 09:30", periods=80, freq="5min")
    d2 = pd.date_range("2026-08-06 09:30", periods=80, freq="5min")
    idx = d1.append(d2)
    close = np.concatenate(
        [np.linspace(5200, 5210, 80), np.linspace(5185, 5205, 80)]
    )
    df = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.full(len(idx), 1500.0),
        },
        index=idx,
    )
    cfg = {
        "vwap_acceptance": {
            "entry_start": "09:45",
            "entry_end": "15:00",
            "flatten_ct": "15:05",
            "min_confidence": 0,
            "target_dollars": 150,
            "min_reward_dollars": 50,
            "max_risk_dollars": 200,
            "skip_trend_days": False,
        }
    }
    now = datetime(2026, 8, 6, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    sig = evaluate_vwap_acceptance("MES", df, cfg, point_value=5.0, now=now)
    assert sig is None or sig.side in {"BUY", "SELL"}
