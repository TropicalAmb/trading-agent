from __future__ import annotations

import numpy as np
import pandas as pd

from agent.strategy.vwap_orb import evaluate_vwap_orb
from datetime import datetime
from zoneinfo import ZoneInfo


def test_vwap_orb_no_crash_on_synthetic():
    idx = pd.date_range("2026-08-06 09:30", periods=60, freq="5min")
    close = np.concatenate([np.linspace(5200, 5205, 3), np.linspace(5205, 5220, 57)])
    df = pd.DataFrame(
        {
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.full(len(idx), 1000.0),
        },
        index=idx,
    )
    cfg = {
        "vwap_orb": {
            "or_start": "09:30",
            "or_end": "09:45",
            "entry_end": "15:00",
            "flatten_ct": "15:05",
            "min_or_width_points": 1.0,
            "max_or_width_points": 100.0,
            "min_confidence": 0,
            "target_dollars": 150,
            "min_reward_dollars": 50,
            "max_risk_dollars": 200,
            "skip_two_sided_days": False,
        }
    }
    now = datetime(2026, 8, 6, 10, 30, tzinfo=ZoneInfo("America/New_York"))
    sig = evaluate_vwap_orb("MES", df, cfg, point_value=5.0, now=now)
    assert sig is None or (sig.side in {"BUY", "SELL"} and sig.reward_dollars >= 50)
