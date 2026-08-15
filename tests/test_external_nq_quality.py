from __future__ import annotations

from pathlib import Path

from agent.research.external_nq_quality import _quarantine_scale_anomalies, audit_external_nq
import pandas as pd


def test_external_audit_rejects_duplicate_and_bad_ohlc(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "Date,Time,Open,High,Low,Close,Volume\n"
        "2025-01-02,09:30:00,100,99,101,100,1\n"
        "2025-01-02,09:30:00,100,101,99,100,1\n",
        encoding="utf-8",
    )
    _frame, payload = audit_external_nq(path, compare_yahoo=False)
    assert payload["status"] == "FAIL"
    assert "invalid_ohlc_rows" in payload["failures"]
    assert "duplicate_timestamps" in payload["failures"]


def test_scale_episode_is_quarantined_not_rewritten() -> None:
    idx = pd.date_range("2025-01-02 09:30", periods=6, freq="min")
    frame = pd.DataFrame(
        {
            "open": [100, 101, 10200, 10300, 104, 105],
            "high": [101, 102, 10201, 10301, 105, 106],
            "low": [99, 100, 10199, 10299, 103, 104],
            "close": [100, 101, 10200, 10300, 104, 105],
            "volume": 1,
        },
        index=idx,
    )
    clean, episodes = _quarantine_scale_anomalies(frame)
    assert len(episodes) == 1
    assert list(clean["close"]) == [100, 101, 104, 105]
    assert episodes[0]["rows"] == 2
