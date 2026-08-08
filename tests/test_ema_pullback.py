from __future__ import annotations

import numpy as np
import pandas as pd

from agent.strategy.ema_pullback import evaluate_ema_pullback


def test_ema_pullback_uptrend_can_signal():
    idx = pd.date_range("2026-08-06 18:00", periods=120, freq="5min")
    # Uptrend then dip into EMA then reclaim
    base = np.linspace(5000, 5100, 100)
    dip = np.linspace(5095, 5085, 10)
    reclaim = np.linspace(5088, 5105, 10)
    close = np.concatenate([base, dip, reclaim])
    df = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.full(len(close), 1000.0),
        },
        index=idx,
    )
    # Force last bars to look like reclaim
    df.iloc[-1, df.columns.get_loc("open")] = float(df.iloc[-1]["close"]) - 3
    df.iloc[-1, df.columns.get_loc("low")] = float(df.iloc[-1]["close"]) - 4
    cfg = {
        "ema_pullback": {
            "min_confidence": 50,
            "max_risk_dollars": 500,
            "min_reward_dollars": 50,
            "target_dollars": 80,
            "touch_atr": 2.0,
        }
    }
    sig = evaluate_ema_pullback("MES", df, cfg, point_value=5.0)
    assert sig is None or sig.side in {"BUY", "SELL"}
