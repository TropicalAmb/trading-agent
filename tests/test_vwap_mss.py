from __future__ import annotations

import numpy as np
import pandas as pd

from agent.strategy.vwap_mss import evaluate_vwap_mss


def test_vwap_mss_no_crash_on_synthetic():
    idx = pd.date_range("2026-08-04 09:00", periods=120, freq="5min")
    # trend up then reclaim-ish path
    close = np.linspace(5200, 5250, len(idx))
    df = pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.5,
            "low": close - 1.5,
            "close": close,
            "volume": np.full(len(idx), 1000.0),
        },
        index=idx,
    )
    cfg = {
        "vwap_mss": {
            "min_mtf_align": 1,  # synthetic may not have 3TF
            "target_r": 1.25,
            "min_confidence": 0,
            "base_confidence": 74,
            "max_risk_dollars": 500,
            "min_reward_dollars": 1,
            "max_overext_atr": 5.0,
        }
    }
    sig = evaluate_vwap_mss("MES", df, cfg, point_value=5.0)
    assert sig is None or (sig.side in {"BUY", "SELL"} and sig.entry > 0)


def test_paper_gates_soft():
    from agent.research.harness.metrics import PAPER_GATES, meets_gates, meets_paper_gates

    st = {
        "n": 40,
        "wr": 0.56,
        "pf": 1.3,
        "expectancy_r": 0.12,
        "anti_cheat_ok": True,
        "worst_r": -1.1,
    }
    assert meets_paper_gates(st)
    assert not meets_gates(st)  # fails hard ≥65% / n≥100
    assert PAPER_GATES["min_n"] == 30
