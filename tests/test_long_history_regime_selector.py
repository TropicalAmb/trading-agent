from __future__ import annotations

import pandas as pd

from agent.research.long_history_regime_selector import _nonoverlap


def test_regime_router_enforces_single_open_position() -> None:
    frame = pd.DataFrame(
        [
            {
                "entry_ts": "2025-01-02 10:00:00",
                "exit_ts": "2025-01-02 11:00:00",
                "probability": 0.80,
            },
            {
                "entry_ts": "2025-01-02 10:30:00",
                "exit_ts": "2025-01-02 10:45:00",
                "probability": 0.90,
            },
            {
                "entry_ts": "2025-01-02 11:05:00",
                "exit_ts": "2025-01-02 11:30:00",
                "probability": 0.70,
            },
        ]
    )
    kept = _nonoverlap(frame, 0.65)
    assert list(kept["probability"]) == [0.80, 0.70]
