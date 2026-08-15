"""Historical feature rows must equal what the live prefix knew at that time."""

from __future__ import annotations

import numpy as np
import pandas as pd

from agent.research.features_ict import swing_high_low
from agent.research.momentum_deep import build_feature_frame
from agent.research.nq_context_entry import enrich_context_5m_bars


def _bars(n: int = 180) -> pd.DataFrame:
    idx = pd.date_range("2026-08-10 08:00", periods=n, freq="5min", tz="America/New_York")
    x = np.arange(n, dtype=float)
    close = 100.0 + 0.03 * x + np.sin(x / 5.0)
    open_ = close - np.cos(x / 7.0) * 0.2
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 0.3,
            "low": np.minimum(open_, close) - 0.3,
            "close": close,
            "volume": 100.0 + (x % 17),
        },
        index=idx,
    )


def test_momentum_features_are_prefix_invariant():
    bars = _bars()
    full = build_feature_frame(bars)
    cols = ["dir_15m", "dir_1h", "dir_4h", "trend_15m", "trend_1h", "trend_4h"]
    for end in (90, 121, 157):
        prefix = build_feature_frame(bars.iloc[:end])
        assert prefix.iloc[-1][cols].to_dict() == full.iloc[end - 1][cols].to_dict()


def test_nq_context_features_are_prefix_invariant():
    bars = _bars()
    full = enrich_context_5m_bars(bars, use_4h=True)
    cols = ["dir_15m", "dir_1h", "dir_4h"]
    for end in (90, 121, 157):
        prefix = enrich_context_5m_bars(bars.iloc[:end], use_4h=True)
        assert prefix.iloc[-1][cols].to_dict() == full.iloc[end - 1][cols].to_dict()


def test_centered_swing_is_visible_only_after_right_confirmation_bars():
    bars = _bars(30)
    bars.loc[:, "high"] = 101.0
    bars.loc[:, "low"] = 99.0
    bars.iloc[10, bars.columns.get_loc("high")] = 110.0
    sh, _ = swing_high_low(bars, left=3, right=3)
    assert sh.iloc[10] != 110.0
    assert sh.iloc[13] == 110.0
