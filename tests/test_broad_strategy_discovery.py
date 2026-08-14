from __future__ import annotations

import pandas as pd

from agent.research.broad_strategy_discovery import (
    _binomial_upper_tail,
    Candidate,
    _completed_feature_position,
    _resample_complete,
    freeze_split_lock,
    period_for,
    simulate_candidates,
)


def test_binomial_tail_is_stable_for_long_history_sample() -> None:
    value = _binomial_upper_tail(7000, 10000)
    assert 0.0 <= value < 1e-100


def _bars(start: str, periods: int, price: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range(start, periods=periods, freq="1min", tz="America/New_York")
    return pd.DataFrame(
        {
            "open": price,
            "high": price + 0.25,
            "low": price - 0.25,
            "close": price,
            "volume": 10.0,
        },
        index=idx,
    )


def test_resample_requires_most_minutes() -> None:
    bars = _bars("2026-01-05 09:30", 8)
    result = _resample_complete(bars, "5min")
    assert list(result.index) == [pd.Timestamp("2026-01-05 09:30", tz="America/New_York")]


def test_split_lock_is_strictly_chronological() -> None:
    parts = [_bars(f"2026-01-{day:02d} 09:30", 2) for day in range(1, 29)]
    bars = pd.concat(parts)
    split = freeze_split_lock(bars)
    assert period_for("2026-01-02 10:00-05:00", split) == "development"
    assert period_for(split.holdout_start, split) == "holdout"


def test_simulator_uses_stop_first_and_prevents_overlap() -> None:
    bars = _bars("2026-01-05 09:30", 10)
    bars.loc[bars.index[1], ["high", "low"]] = [102.0, 98.0]
    first = Candidate(
        family="x",
        variant="a",
        source_id="validation",
        symbol="CL",
        side="BUY",
        signal_ts=str(bars.index[0]),
        entry_ts=str(bars.index[0]),
        entry=100.0,
        stop=99.0,
        target_r=1.5,
    )
    second = Candidate(
        family="x",
        variant="a",
        source_id="validation",
        symbol="CL",
        side="BUY",
        signal_ts=str(bars.index[1]),
        entry_ts=str(bars.index[1]),
        entry=100.0,
        stop=99.0,
        target_r=1.5,
    )
    rows = simulate_candidates([first, second], bars)
    assert len(rows) == 1
    assert rows[0]["exit_reason"] == "stop"
    assert rows[0]["pnl_r"] < -1.0


def test_entry_features_use_only_a_completed_five_minute_bar() -> None:
    idx = pd.date_range("2026-01-05 09:30", periods=4, freq="5min", tz="America/New_York")
    assert _completed_feature_position(idx, pd.Timestamp("2026-01-05 09:35", tz="America/New_York")) == 0
    assert _completed_feature_position(idx, pd.Timestamp("2026-01-05 09:39", tz="America/New_York")) == 0
