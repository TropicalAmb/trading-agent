"""Bootstrap / Monte Carlo robustness on R returns."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def monte_carlo(pnl_r: Sequence[float], n_sims: int = 10000, seed: int = 7) -> dict[str, Any]:
    if len(pnl_r) < 5:
        return {"n_sims": 0, "status": "INSUFFICIENT"}
    rs = np.asarray(list(pnl_r), dtype=float)
    rng = np.random.default_rng(seed)
    terminals, maxdds, streaks = [], [], []
    for _ in range(n_sims):
        sample = rng.choice(rs, size=len(rs), replace=True)
        eq = np.cumsum(sample)
        terminals.append(float(eq[-1]))
        peak = np.maximum.accumulate(eq)
        maxdds.append(float((eq - peak).min()))
        streak = cur = 0
        for x in sample:
            if x <= 0:
                cur += 1
                streak = max(streak, cur)
            else:
                cur = 0
        streaks.append(streak)
    terminals = np.asarray(terminals)
    maxdds = np.asarray(maxdds)
    streaks = np.asarray(streaks)
    return {
        "n_sims": n_sims,
        "status": "OK",
        "median_terminal_r": round(float(np.median(terminals)), 3),
        "p05_terminal_r": round(float(np.percentile(terminals, 5)), 3),
        "p95_terminal_r": round(float(np.percentile(terminals, 95)), 3),
        "median_max_dd_r": round(float(np.median(maxdds)), 3),
        "p90_max_dd_r": round(float(np.percentile(maxdds, 10)), 3),  # 90th worst ≈ 10th pct of negative DD
        "p95_max_dd_r": round(float(np.percentile(maxdds, 5)), 3),
        "prob_dd_ge_5r": round(float((maxdds <= -5).mean()), 4),
        "prob_dd_ge_10r": round(float((maxdds <= -10).mean()), 4),
        "prob_dd_ge_15r": round(float((maxdds <= -15).mean()), 4),
        "prob_dd_ge_20r": round(float((maxdds <= -20).mean()), 4),
        "median_longest_losing_streak": int(np.median(streaks)),
        "p90_longest_losing_streak": int(np.percentile(streaks, 90)),
        "p95_longest_losing_streak": int(np.percentile(streaks, 95)),
    }
