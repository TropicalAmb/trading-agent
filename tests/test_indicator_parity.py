from __future__ import annotations

import numpy as np
import pandas as pd

from agent.strategy.indicator_parity import compute_parity_frame, evaluate_indicator_parity, state_at


def _synth_1m(n: int = 800) -> pd.DataFrame:
    idx = pd.date_range("2026-08-04 09:30", periods=n, freq="1min", tz="America/New_York")
    # trending up with a sweep below prior day then reclaim
    close = np.linspace(20000, 20150, n) + np.sin(np.linspace(0, 12, n)) * 8
    # force a PDL sweep mid-series
    close[400:410] = close[399] - 40
    close[410:420] = close[399] + 5
    df = pd.DataFrame(
        {
            "open": close - 1.0,
            "high": close + 3.0,
            "low": close - 3.0,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )
    # deepen sweep wick
    df.loc[df.index[405], "low"] = float(df["close"].iloc[405]) - 25
    df.loc[df.index[405], "close"] = float(df["close"].iloc[404]) + 2
    return df


def test_parity_frame_columns():
    df = _synth_1m()
    frame = compute_parity_frame(df, {"indicator_parity": {}})
    for col in (
        "buy_now",
        "sell_now",
        "pullback",
        "momentum",
        "dir_15m",
        "dir_1h",
        "dir_4h",
        "ema20",
        "ema50",
        "vwap",
        "pdh",
        "pdl",
    ):
        assert col in frame.columns


def test_state_dump_fields():
    df = _synth_1m()
    frame = compute_parity_frame(df, {"indicator_parity": {}})
    st = state_at(frame, len(frame) - 1, symbol="NQ", entry_mode="exact")
    assert st.timestamp
    assert st.action in {
        "Wait",
        "Buy Now",
        "Sell Now",
        "Watching Long Retest",
        "Watching Short Retest",
        "Long Bias",
        "Short Bias",
    }


def test_evaluate_smoke():
    df = _synth_1m()
    cfg = {"indicator_parity": {"enabled": True, "min_confidence": 0}}
    sig = evaluate_indicator_parity("NQ", df, cfg, point_value=20.0)
    assert sig is None or sig.side in {"BUY", "SELL"}
