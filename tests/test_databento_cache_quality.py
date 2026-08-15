from __future__ import annotations

import pandas as pd

from agent.research.databento_cache_quality import audit_continuous_cache


def _meta(root: str) -> dict:
    return {
        "databento": f"{root}.v.0",
        "stype_in": "continuous",
        "cache_format_version": "databento_continuous_v1",
        "roll_rule": "volume",
    }


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2026-08-14 09:30", periods=20, freq="1min", tz="America/New_York")
    close = pd.Series([100 + i * 0.01 for i in range(20)], index=idx)
    return pd.DataFrame(
        {
            "open": close - 0.01,
            "high": close + 0.02,
            "low": close - 0.02,
            "close": close,
            "volume": 10.0,
        },
        index=idx,
    )


def test_clean_continuous_cache_passes():
    report = audit_continuous_cache(_frame(), _meta("NQ"), root="NQ")
    assert report["status"] == "PASS"
    assert report["duplicate_timestamps"] == 0
    assert report["invalid_ohlc_rows"] == 0


def test_parent_metadata_fails_even_when_prices_look_clean():
    report = audit_continuous_cache(
        _frame(),
        {"databento": "NQ.FUT", "stype_in": "parent"},
        root="NQ",
    )
    assert report["status"] == "FAIL"
    assert "metadata_stype_not_continuous" in report["failures"]


def test_duplicate_timestamp_and_invalid_ohlc_fail():
    frame = _frame()
    dup = pd.concat([frame, frame.iloc[[0]]])
    dup.iloc[0, dup.columns.get_loc("high")] = 90.0
    report = audit_continuous_cache(dup, _meta("NQ"), root="NQ")
    assert report["status"] == "FAIL"
    assert report["duplicate_timestamps"] == 2
    assert report["invalid_ohlc_rows"] == 1
