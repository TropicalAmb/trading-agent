from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd

from agent.research.broad_strategy_discovery import (
    FAMILY_SPECS,
    _classic_5m_features,
    _resample_complete,
)


PASS7_FAMILIES = {
    "nq_macd_ema_vwap_momentum",
    "nq_flag_ema_vwap_pullback",
    "nq_vwap_ema9_rejection",
    "balanced_keltner_stochastic_reentry",
    "bollinger_keltner_mfi_squeeze",
}


def _synthetic_bars(days: int = 24) -> pd.DataFrame:
    idx = pd.date_range(
        "2026-01-05 00:00",
        periods=days * 24 * 60,
        freq="1min",
        tz="America/New_York",
    )
    x = np.arange(len(idx), dtype=float)
    volatility = 0.20 + 0.12 * np.sin(x / 180.0) ** 2
    delta = 0.025 + volatility * np.sin(x / 11.0) + 0.08 * np.sin(x / 43.0)
    close = 20000.0 + np.cumsum(delta)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.7 + 0.35 * np.sin(x / 17.0) ** 2
    low = np.minimum(open_, close) - 0.7 - 0.35 * np.cos(x / 19.0) ** 2
    volume = 100.0 + 60.0 * np.sin(x / 29.0) ** 2 + 25.0 * np.sin(x / 101.0) ** 2
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_classic_features_are_prefix_invariant_and_bounded() -> None:
    full_1m = _synthetic_bars()
    cutoff = full_1m.index[18 * 24 * 60 - 1]
    prefix_5m = _resample_complete(full_1m.loc[:cutoff], "5min")
    full_5m = _resample_complete(full_1m, "5min")
    prefix = _classic_5m_features(prefix_5m)
    full = _classic_5m_features(full_5m).loc[: prefix.index[-1]]
    pd.testing.assert_frame_equal(full, prefix)
    assert prefix["stoch_k"].dropna().between(0.0, 100.0).all()
    assert prefix["mfi14"].dropna().between(0.0, 100.0).all()
    assert (prefix["adx14"].dropna() >= 0.0).all()
    assert {
        "ema9",
        "ema20",
        "ema21",
        "macd_hist",
        "relative_volume",
        "bb_upper",
        "bb_lower",
    } <= set(prefix.columns)


def test_pass7_families_are_registered_and_candidate_prefix_invariant() -> None:
    registry = {
        family: (generator, specs)
        for family, generator, specs in FAMILY_SPECS
        if family in PASS7_FAMILIES
    }
    assert set(registry) == PASS7_FAMILIES
    full_1m = _synthetic_bars()
    cutoff = full_1m.index[18 * 24 * 60 - 1]
    prefix_1m = full_1m.loc[:cutoff]
    full_5m = _resample_complete(full_1m, "5min")
    prefix_5m = _resample_complete(prefix_1m, "5min")
    for family, (generator, specs) in registry.items():
        prefix = [asdict(row) for row in generator(prefix_1m, prefix_5m, "NQ", specs[0])]
        full = [
            asdict(row)
            for row in generator(full_1m, full_5m, "NQ", specs[0])
            if pd.Timestamp(row.entry_ts) <= cutoff
        ]
        assert full == prefix, family
