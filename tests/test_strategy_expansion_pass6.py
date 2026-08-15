from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd

from agent.research.broad_strategy_discovery import (
    FAMILY_SPECS,
    _microstructure_proxy_5m,
    _resample_complete,
)


PASS6_FAMILIES = {
    "bvc_cvd_divergence",
    "bvc_absorption_reversal",
    "bvc_pressure_breakout",
    "vpin_failed_extension",
    "impact_shock_reversal",
}


def _synthetic_bars(days: int = 18) -> pd.DataFrame:
    idx = pd.date_range(
        "2026-01-05 00:00",
        periods=days * 24 * 60,
        freq="1min",
        tz="America/New_York",
    )
    x = np.arange(len(idx), dtype=float)
    delta = 0.03 + 0.18 * np.sin(x / 9.0) + 0.08 * np.sin(x / 31.0)
    close = 20000.0 + np.cumsum(delta)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.8 + 0.3 * np.sin(x / 13.0) ** 2
    low = np.minimum(open_, close) - 0.8 - 0.3 * np.cos(x / 17.0) ** 2
    volume = 100.0 + 45.0 * np.sin(x / 23.0) ** 2
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_microstructure_proxy_is_bounded_and_prefix_invariant() -> None:
    full = _synthetic_bars()
    cutoff = full.index[14 * 24 * 60 - 1]
    prefix = full.loc[:cutoff]
    prefix_proxy = _microstructure_proxy_5m(prefix)
    full_proxy = _microstructure_proxy_5m(full).loc[: prefix_proxy.index[-1]]
    pd.testing.assert_frame_equal(full_proxy, prefix_proxy)
    pressure = prefix_proxy["signed_pressure_proxy"].dropna()
    assert len(pressure) > 100
    assert pressure.between(-1.0, 1.0).all()
    assert {
        "flow6_proxy",
        "toxicity_proxy",
        "impact_z_proxy",
        "pressure_z_proxy",
    } <= set(prefix_proxy.columns)

    yahoo_like = _resample_complete(prefix, "5min")
    yahoo_proxy = _microstructure_proxy_5m(yahoo_like)
    assert len(yahoo_proxy) == len(yahoo_like)
    assert yahoo_proxy["signed_pressure_proxy"].notna().sum() > 100


def test_pass6_families_are_registered_and_candidate_prefix_invariant() -> None:
    registry = {
        family: (generator, specs)
        for family, generator, specs in FAMILY_SPECS
        if family in PASS6_FAMILIES
    }
    assert set(registry) == PASS6_FAMILIES
    full_1m = _synthetic_bars()
    cutoff = full_1m.index[14 * 24 * 60 - 1]
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
