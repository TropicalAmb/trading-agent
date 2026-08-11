from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from agent.decision.setup import TradeSetup
from agent.decision.tiering import can_execute
from agent.learning.dataset import build_unified_dataset, time_splits
from agent.learning.model import AdaptiveTradeQualityModel, calibration_bins, is_calibrated_enough
from agent.learning.shrink import shrink_rate
from agent.learning.store import LearningStore
from datetime import datetime


def test_shrink_does_not_trust_tiny_samples():
    shr = shrink_rate(8, 10, prior_mean=0.50, prior_strength=20.0)
    assert shr.raw == 0.8
    assert shr.shrunk < 0.65  # pulled hard toward 50%


def test_learning_store_roundtrip(tmp_path: Path):
    store = LearningStore(tmp_path / "c.jsonl")
    row = store.append({"setup_id": "abc", "symbol": "NQ", "final_result": "OPEN"})
    assert store.find_open_by_setup("abc") is not None
    assert store.update_outcome(row["candidate_id"], {"final_result": "WIN", "win": 1, "realized_r": 1.2})
    closed = [r for r in store.all_rows() if r.get("final_result") == "WIN"]
    assert len(closed) == 1


def test_research_only_cannot_execute():
    cfg = {
        "tiering": {"minimum_trade_tier": "A"},
        "research_only_engines": ["trend_pullback"],
    }
    s = TradeSetup(
        strategy_name="trend_pullback",
        symbol="ES",
        direction="BUY",
        setup_tier="A",
        confidence_score=80,
        entry=1,
        stop=0.5,
        target=2,
        expected_r=2,
        market_timestamp=datetime(2026, 8, 10),
        received_timestamp=datetime(2026, 8, 10),
        metadata={"global_score": 80, "hard_invalidations": []},
    )
    assert can_execute(s, cfg) is False


def test_time_splits_are_chronological():
    df = pd.DataFrame(
        {
            "market_timestamp": [f"2026-01-{i:02d}" for i in range(1, 31)],
            "win": [i % 2 for i in range(30)],
        }
    )
    sp = time_splits(df)
    assert len(sp["train"]) + len(sp["val"]) + len(sp["final"]) == 30
    assert str(sp["train"]["market_timestamp"].iloc[-1]) < str(sp["final"]["market_timestamp"].iloc[0])


def test_calibration_gate():
    import numpy as np

    y = np.array([1, 1, 0, 0, 1, 1, 0, 0, 1, 0] * 5)
    # well calibrated ~0.5
    p = np.array([0.52] * len(y))
    bins = calibration_bins(y.astype(float), p)
    # sparse bins → not enough
    assert is_calibrated_enough(bins, min_bin_n=8) is False


def test_build_dataset_from_repo_files():
    df, audit = build_unified_dataset(backfill_bars=False)
    assert audit.usable_rows == len(df)
    assert "missingness" in audit.to_dict()
