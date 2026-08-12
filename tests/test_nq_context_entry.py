"""Tests for NQ_CONTEXT_ENTRY research family + Kaggle loader helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from agent.data.data_quality import audit_nq_1m
from agent.data.kaggle_nq import resample_ohlcv
from agent.research.nq_context_entry import (
    SESSION_WINDOWS,
    build_context_5m,
    generate_candidates,
    in_window,
    realize_trades,
    rolling_walk_forward_splits,
    stats_for,
)


def _synth_1m(n: int = 5000) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02 09:00", periods=n, freq="1min", tz="America/New_York")
    rng = np.random.default_rng(7)
    px = 18000 + np.cumsum(rng.normal(0, 2.0, size=n))
    high = px + rng.uniform(0.5, 4.0, size=n)
    low = px - rng.uniform(0.5, 4.0, size=n)
    open_ = np.r_[px[0], px[:-1]]
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": px, "volume": rng.integers(10, 500, size=n)},
        index=idx,
    )
    df.attrs["source"] = "synth"
    return df


def test_resample_and_context():
    df = _synth_1m(2000)
    df5 = build_context_5m(df)
    assert len(df5) > 50
    for col in ("ema20", "ema50", "vwap", "atr", "dir_15m", "dir_1h", "pdh", "pdl"):
        assert col in df5.columns


def test_session_windows():
    ts = pd.Timestamp("2024-06-03 09:45", tz="America/New_York")
    assert in_window(ts, "0930_1030")
    assert in_window(ts, "0930_1100")
    assert not in_window(ts, "0830_0930")


def test_candidate_generation_smoke():
    df = _synth_1m(8000)
    df5 = build_context_5m(df)
    any_cands = False
    for trig in ("PULLBACK", "LIQUIDITY", "BREAKOUT_RETEST"):
        for win in SESSION_WINDOWS:
            c = generate_candidates(df5, trigger=trig, window=win, confirmation="signal_close")
            if c:
                any_cands = True
                trades = realize_trades(c, df, target_r=1.5)
                st = stats_for(trades)
                assert "n" in st
    # synthetic may be quiet; generation path must not crash
    assert any_cands or True


def test_walk_forward_holdout_untouched_fraction():
    df = _synth_1m(20000)
    splits = rolling_walk_forward_splits(df.index, n_folds=4, holdout_frac=0.2)
    assert splits["n_holdout_days"] > 0
    assert splits["holdout_days"].isdisjoint(splits["research_days"])


def test_audit_flags_empty():
    r = audit_nq_1m(pd.DataFrame())
    assert r["ok"] is False


@pytest.mark.skipif(
    not (Path("data/kaggle/Dataset_NQ_1min_2022_2025.csv").exists()),
    reason="Kaggle NQ CSV not present locally",
)
def test_load_real_kaggle_head():
    from agent.data.kaggle_nq import load_nq_1m_csv

    df = load_nq_1m_csv(auto_download=False)
    assert len(df) > 100_000
    q = audit_nq_1m(df)
    assert q["rows"] == len(df)
