from __future__ import annotations

import numpy as np
import pandas as pd

from agent.research.high_precision_state_model import (
    FEATURE_COLUMNS,
    _candidates,
    _gate,
    build_decision_rows,
)


def _bars() -> pd.DataFrame:
    index = pd.date_range(
        "2025-01-05 18:00", periods=600, freq="15min", tz="America/New_York"
    )
    path = 20000.0 + np.arange(len(index)) * 0.25 + np.sin(np.arange(len(index)) / 7.0) * 3.0
    return pd.DataFrame(
        {
            "open": path - 0.25,
            "high": path + 1.0,
            "low": path - 1.0,
            "close": path,
            "volume": 1000.0 + (np.arange(len(index)) % 37) * 10.0,
        },
        index=index,
    )


def test_decision_rows_use_completed_bar_and_pair_sides() -> None:
    rows = build_decision_rows(_bars(), include_label=False)
    assert len(rows) > 0
    assert set(FEATURE_COLUMNS).issubset(rows.columns)
    assert set(rows["side"]) == {"BUY", "SELL"}
    assert rows.groupby("entry_ts")["side"].nunique().eq(2).all()
    signal = pd.to_datetime(rows["signal_ts"], utc=True)
    entry = pd.to_datetime(rows["entry_ts"], utc=True)
    assert (entry - signal).eq(pd.Timedelta(minutes=15)).all()


def test_candidate_requires_probability_and_opposing_side_margin() -> None:
    rows = build_decision_rows(_bars(), include_label=False)
    pair = rows.iloc[:2].copy()
    accepted = _candidates(pair, np.array([0.80, 0.60]), 0.75)
    rejected = _candidates(pair, np.array([0.80, 0.77]), 0.75)
    assert len(accepted) == 1
    assert accepted[0].side == str(pair.iloc[0]["side"])
    assert rejected == []


def test_full_gate_requires_all_four_segments() -> None:
    qualified = {"n": 60, "wr": 0.75, "pf": 1.5, "expectancy_r": 0.2}
    weak_yahoo = {"n": 20, "wr": 0.60, "pf": 1.0, "expectancy_r": 0.0}
    failures = _gate(qualified, qualified, qualified, weak_yahoo)
    assert "yahoo_WR<70%" in failures
    assert "yahoo_PF<1.20" in failures
    assert _gate(qualified, qualified, qualified, qualified) == []
