from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd

from agent.research.broad_strategy_discovery import FAMILY_SPECS, _resample_complete


PASS5_FAMILIES = {
    "nq_opening_shock_reversal",
    "gap_reject_then_go",
    "initial_balance_vwap_retest",
    "volume_climax_rejection",
    "lunch_vwap_reclaim",
    "two_test_range_breakout",
    "nq_post_settlement_alignment",
}


def _synthetic_bars(days: int = 18) -> pd.DataFrame:
    idx = pd.date_range(
        "2026-01-05 00:00",
        periods=days * 24 * 60,
        freq="1min",
        tz="America/New_York",
    )
    x = np.arange(len(idx), dtype=float)
    close = 20000.0 + 0.015 * x + 8.0 * np.sin(x / 43.0) + 3.0 * np.sin(x / 7.0)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 1.0 + 0.2 * np.sin(x / 11.0) ** 2
    low = np.minimum(open_, close) - 1.0 - 0.2 * np.cos(x / 13.0) ** 2
    volume = 100.0 + 30.0 * np.sin(x / 29.0) ** 2
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_pass5_families_are_registered_and_prefix_invariant() -> None:
    registry = {
        family: (generator, specs)
        for family, generator, specs in FAMILY_SPECS
        if family in PASS5_FAMILIES
    }
    assert set(registry) == PASS5_FAMILIES

    full_1m = _synthetic_bars()
    cutoff = full_1m.index[14 * 24 * 60 - 1]
    prefix_1m = full_1m.loc[:cutoff]
    full_5m = _resample_complete(full_1m, "5min")
    prefix_5m = _resample_complete(prefix_1m, "5min")

    for family, (generator, specs) in registry.items():
        spec = specs[0]
        prefix = [asdict(row) for row in generator(prefix_1m, prefix_5m, "NQ", spec)]
        full = [
            asdict(row)
            for row in generator(full_1m, full_5m, "NQ", spec)
            if pd.Timestamp(row.entry_ts) <= cutoff
        ]
        assert full == prefix, family
