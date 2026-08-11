"""Empirical probability + calibration from historical comparable outcomes."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

import numpy as np


def empirical_wr_ci(wins: int, n: int) -> tuple[float, list[float]]:
    if n <= 0:
        return 0.0, [0.0, 0.0]
    wr = wins / n
    # Wilson-ish via bootstrap
    rng = np.random.default_rng(11)
    arr = np.array([1] * wins + [0] * (n - wins))
    boots = [float(rng.choice(arr, size=n, replace=True).mean()) for _ in range(400)]
    return wr, [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]


def calibrate_buckets(
    predicted: Sequence[float],
    outcomes: Sequence[int],
    min_n: int = 30,
) -> dict[str, Any]:
    """predicted in [0,1], outcomes 1=win 0=loss."""
    buckets = [
        (0.50, 0.55, "50-55"),
        (0.55, 0.60, "55-60"),
        (0.60, 0.65, "60-65"),
        (0.65, 0.70, "65-70"),
        (0.70, 0.75, "70-75"),
        (0.75, 0.80, "75-80"),
        (0.80, 1.01, "80+"),
    ]
    out: dict[str, Any] = {}
    abs_err = []
    for lo, hi, name in buckets:
        idx = [i for i, p in enumerate(predicted) if lo <= p < hi]
        if len(idx) < min_n:
            out[name] = {"n": len(idx), "status": "INSUFFICIENT"}
            continue
        pred_mean = float(np.mean([predicted[i] for i in idx]))
        obs = float(np.mean([outcomes[i] for i in idx]))
        err = abs(pred_mean - obs)
        abs_err.append(err)
        out[name] = {
            "n": len(idx),
            "predicted_mean": round(pred_mean, 4),
            "observed_wr": round(obs, 4),
            "abs_error": round(err, 4),
            "status": "OK",
        }
    return {
        "buckets": out,
        "mae": round(float(np.mean(abs_err)), 4) if abs_err else None,
        "min_n_per_bucket": min_n,
    }


def comparable_probability(
    train_trades: list[dict[str, Any]],
    *,
    strategy: str,
    symbol: str,
    session: str | None = None,
    regime: str | None = None,
    min_n: int = 30,
) -> dict[str, Any]:
    """Estimated WR from TRAIN comparable outcomes only (never final test)."""
    pool = [
        t
        for t in train_trades
        if t.get("strategy") == strategy and t.get("symbol") == symbol
    ]
    if session:
        pool = [t for t in pool if t.get("session") == session]
    if regime:
        pool = [t for t in pool if t.get("regime") == regime]
    n = len(pool)
    if n < min_n:
        # loosen filters
        pool = [t for t in train_trades if t.get("strategy") == strategy]
        n = len(pool)
        scope = "strategy_all_symbols"
    else:
        scope = "strategy_symbol" + ("_session" if session else "") + ("_regime" if regime else "")
    if n < min_n:
        return {"n": n, "status": "INSUFFICIENT", "scope": scope}
    wins = sum(1 for t in pool if t.get("pnl_r", 0) > 0)
    wr, ci = empirical_wr_ci(wins, n)
    return {
        "n": n,
        "status": "OK",
        "scope": scope,
        "estimated_wr": round(wr, 4),
        "ci95": [round(ci[0], 4), round(ci[1], 4)],
        "min_n": min_n,
    }
